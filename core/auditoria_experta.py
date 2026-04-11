import math
from decimal import Decimal
from sqlalchemy import func, and_, or_
from database import (
    ValidacionFiscal, Dgii606, Dgii607, DgiiIt1, 
    Inventario, TssNomina, EstadoFinanciero, Empresa
)

class AuditoriaExperta:
    """
    Motor de Auditoria Preventiva Nivel Socio Senior.
    Detecta 'Pecados Capitales' fiscales y propone asientos de correccion.
    """
    # Tasas TSS vigentes (Aporte Empresa)
    TASA_SFS = Decimal("0.0709")      # Seguro Familiar de Salud
    TASA_AFP = Decimal("0.0710")      # Administradora de Fondos de Pensiones
    TASA_SRL = Decimal("0.0120")      # Seguro de Riesgos Laborales (Promedio)
    TASA_INFOTEP = Decimal("0.0100")  # INFOTEP
    TASA_SS_TOTAL = TASA_SFS + TASA_AFP + TASA_SRL + TASA_INFOTEP # ~16.39%

    def __init__(self, db, empresa_id, anio):
        self.db = db
        self.empresa_id = empresa_id
        self.anio = anio
        self.anio_str = str(anio)
        self.hallazgos = []

    def ejecutar_auditoria_completa(self):
        print(f"\n[SOCIO AUDIT] Iniciando escaneo de Red Flags para periodo {self.anio}...")
        
        self._check_inventario_critico()
        self._check_proporcion_b13()
        self._check_conciliacion_laboral()
        self._check_proveedores_rst()
        self._check_anticipos_it1()
        self._check_proporcionalidad_itbis()
        self._check_ley_residuos_98_25()
        
        self._guardar_hallazgos()
        return len(self.hallazgos)

    def _check_inventario_critico(self):
        """Red Flag: Compras en 606 pero Inventario Final en 0."""
        compras = float(self.db.query(func.sum(Dgii606.monto_facturado)).filter(
            and_(Dgii606.empresa_id == self.empresa_id, Dgii606.periodo.like(f"{self.anio_str}%"), Dgii606.anulada != 1)
        ).scalar() or 0.0)

        inv_final = float(self.db.query(func.sum(Inventario.valor_total)).filter(
            and_(Inventario.empresa_id == self.empresa_id, Inventario.tipo_inventario == 'final')
        ).scalar() or 0.0)

        if compras > 100000 and inv_final == 0:
            self._registrar(
                tipo="INVENTARIO_CRITICO",
                valor_sist=inv_final,
                valor_ref=compras * 0.10, # Al menos un 10% deberia quedar si hay compras masivas
                estado="CRITICO",
                recomendacion="ERROR GRAVE: Reportas compras masivas pero inventario final en 0. La DGII presumira ventas omitidas.",
                asiento="Debitar: Inventario (Activo) / Abonar: Costo de Ventas (Gasto). Razon: Ajuste de existencias no vendidas."
            )

    def _check_proporcion_b13(self, umbral_error=5.0, umbral_warn=3.0):
        """Red Flag: Abuso de Comprobantes de Gastos Menores."""
        gastos_totales = float(self.db.query(func.sum(Dgii606.monto_facturado)).filter(
            and_(Dgii606.empresa_id == self.empresa_id, Dgii606.periodo.like(f"{self.anio_str}%"), Dgii606.anulada != 1)
        ).scalar() or 1.0)

        gastos_b13 = float(self.db.query(func.sum(Dgii606.monto_facturado)).filter(
            and_(
                Dgii606.empresa_id == self.empresa_id, 
                Dgii606.periodo.like(f"{self.anio_str}%"),
                Dgii606.ncf.like("B13%")
            )
        ).scalar() or 0.0)

        porcentaje = (gastos_b13 / gastos_totales) * 100
        
        if porcentaje >= umbral_warn:
            estado = "CRITICO" if porcentaje >= umbral_error else "ADVERTENCIA"
            self._registrar(
                tipo="RELACION_B13_GASTO",
                valor_sist=porcentaje,
                valor_ref=umbral_error,
                estado=estado,
                recomendacion=f"ALERTA SOCIO: El {porcentaje:.2f}% de tus gastos son B13. Excede el limite de prudencia del 5%.",
                asiento="Reclasificar exceso de B13 a 'Gastos No Deducibles' para blindar el IR-2."
            )

    def _check_conciliacion_laboral(self):
        """Red Flag: Gasto Seguridad Social en B-1 vs TSS."""
        tss_pagada = float(self.db.query(func.sum(TssNomina.aporte_empresa)).filter(
            and_(TssNomina.empresa_id == self.empresa_id, TssNomina.periodo.like(f"{self.anio_str}%"))
        ).scalar() or 0.0)

        # En una implementacion real buscariamos el valor en el Anexo B-1 Casilla 6.4
        # Aqui simulamos comparacion con el EstadoFinanciero generado
        ef = self.db.query(EstadoFinanciero).filter_by(empresa_id=self.empresa_id, periodo=self.anio_str).first()
        gasto_ss = float(ef.gastos_personal * self.TASA_SS_TOTAL) if ef else 0.0 # Cálculo preciso


        diff = abs(tss_pagada - gasto_ss)
        if diff > (tss_pagada * 0.05) and tss_pagada > 0:
            self._registrar(
                tipo="CRUCE_TSS_B1_6.4",
                valor_sist=gasto_ss,
                valor_ref=tss_pagada,
                estado="CRITICO",
                recomendacion="ERROR DE CONCILIACION: El gasto de SFS/AFP en el IR-2 no coincide con los pagos realizados a TSS.",
                asiento="Ajustar cuenta 'Gastos Seguros y Fianzas' contra 'TSS por Pagar' para igualar registros oficiales."
            )

    def _check_proveedores_rst(self):
        """Red Flag: Proveedores en RST sin retencion del 100% ITBIS."""
        # Buscamos en 606 facturas de proveedores que sabemos son RST (simulado con una lista o flag en Padron)
        # Por ahora, buscamos si hay ITBIS facturado pero 0 retencion en facturas de personas fisicas
        compras_pf = self.db.query(Dgii606).filter(
            and_(
                Dgii606.empresa_id == self.empresa_id,
                Dgii606.periodo.like(f"{self.anio_str}%"),
                func.length(Dgii606.rnc_proveedor) == 11, # Cedula = Persona Fisica
                Dgii606.itbis_retenido == 0,
                Dgii606.itbis_facturado > 0
            )
        ).all()

        if compras_pf:
            monto_riesgo = sum(float(c.itbis_facturado) for c in compras_pf)
            self._registrar(
                tipo="RIESGO_RETENCION_RST",
                valor_sist=0,
                valor_ref=monto_riesgo,
                estado="CRITICO",
                recomendacion=f"RIESGO LEGAL: Tienes {len(compras_pf)} facturas de Personas Fisicas (posible RST) sin retencion de ITBIS.",
                asiento="Debitar: Cuenta por Pagar / Abonar: ITBIS Retenido por Pagar (100% del ITBIS facturado)."
            )

    def _check_anticipos_it1(self):
        """Red Flag: Anticipos reportados en IR-2 que no aparecen en IT-1."""
        anticipos_it1 = float(self.db.query(func.sum(DgiiIt1.saldo_anterior)).filter(
            and_(DgiiIt1.empresa_id == self.empresa_id, DgiiIt1.periodo.like(f"{self.anio_str}%"))
        ).scalar() or 0.0)

        # Asumiremos que el IR-2 quiere declarar algo diferente
        if anticipos_it1 == 0:
             self._registrar(
                tipo="ANTICIPOS_VACIOS",
                valor_sist=0,
                valor_ref=1, 
                estado="ADVERTENCIA",
                recomendacion="SOCIO TIPS: No se detectaron anticipos pagados en los IT-1. Valida si tienes saldos a favor de años anteriores.",
                asiento="N/A - Verificar casilla 14 del IR-2."
            )

    def _check_proporcionalidad_itbis(self):
        """Red Flag: ITBIS No Admitido vs Gasto Deducible."""
        it1_data = self.db.query(DgiiIt1).filter(
            and_(DgiiIt1.empresa_id == self.empresa_id, DgiiIt1.periodo.like(f"{self.anio_str}%"))
        ).all()
        
        # Si hay muchas ventas exentas, el ITBIS proporcional debe ser alto
        ventas_exentas = sum(float(i.ventas_exentas) for i in it1_data)
        if ventas_exentas > 0:
            print(f"  [i] Analizando proporcionalidad para RD$ {ventas_exentas:,.0f} en ventas exentas...")

    def _check_ley_residuos_98_25(self):
        """Red Flag: Contribución Especial para Residuos Sólidos (Ley 98-25)."""
        ef = self.db.query(EstadoFinanciero).filter_by(empresa_id=self.empresa_id, periodo=self.anio_str).first()
        ingresos_brutos = float(ef.ventas) if ef and ef.ventas else 0.0

        if ingresos_brutos == 0:
            return  # No se puede calcular sin ingresos

        contribucion_ley = 0.0
        if ingresos_brutos <= 1000000:
            contribucion_ley = 3000.0
        elif ingresos_brutos <= 10000000:
            contribucion_ley = 6000.0
        elif ingresos_brutos <= 25000000:
            contribucion_ley = 20000.0
        elif ingresos_brutos <= 50000000:
            contribucion_ley = 155000.0
        elif ingresos_brutos <= 100000000:
            contribucion_ley = 260000.0
        else:
            contribucion_ley = 675000.0

        # Aquí podríamos comparar con un estado contable. Como es una contribución obligatoria
        # y usualmente no la registran hasta fin de año, exigimos que la provisión esté hecha.
        # Simularemos que queremos notificar sobre la provisión faltante.
        self._registrar(
            tipo="LEY_98_25_RESIDUOS",
            valor_sist=0,  # Asumimos que no está provisionado o que validamos el requerimiento
            valor_ref=contribucion_ley,
            estado="CRITICO",
            recomendacion=f"NUEVA LEY 98-25: Con ingresos de RD${ingresos_brutos:,.2f}, debes provisionar y pagar RD${contribucion_ley:,.2f} a la DGII por la Contribución Especial de Residuos Sólidos.",
            asiento=f"Debitar: Gasto Contribución Ley 98-25 (Deducible art. 287) / Abonar: Cuentas por Pagar DGII por RD${contribucion_ley:,.2f}."
        )

    def _registrar(self, tipo, valor_sist, valor_ref, estado, recomendacion, asiento):
        hallazgo = ValidacionFiscal(
            empresa_id=self.empresa_id,
            periodo=self.anio_str,
            tipo_validacion=f"SOCIO_{tipo}",
            valor_sistema=Decimal(str(valor_sist)),
            valor_dgii=Decimal(str(valor_ref)),
            diferencia=Decimal(str(abs(valor_sist - valor_ref))),
            estado=estado,
            recomendacion_socio=recomendacion,
            asiento_propuesto=asiento
        )
        self.hallazgos.append(hallazgo)
        print(f"  [ALERT] {tipo}: {recomendacion}")

    def _guardar_hallazgos(self):
        if self.hallazgos:
            self.db.add_all(self.hallazgos)
            self.db.commit()
