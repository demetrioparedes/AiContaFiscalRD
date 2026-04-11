"""
auditoria_retenciones.py — Módulo de Auditoría de Retenciones (ISR e ITBIS)
========================================================================
Valida que las retenciones aplicadas en el 606 coincidan con las tasas 
legales de RD (10%, 2%, 1%, 100% ITBIS, 30% ITBIS) incluyendo soporte RST.
"""
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from database import Dgii606, PadronDGII, ValidacionFiscal, Empresa

class AuditoriaRetenciones:
    """
    Módulo de Auditoría de Retenciones (ISR e ITBIS)
    ================================================
    Valida que las retenciones aplicadas en el 606 coincidan con las tasas 
    legales de RD (10%, 2%, 1%, 100% ITBIS, 30% ITBIS) incluyendo soporte RST.
    """
    def __init__(self, db: Session, empresa_id: int, anio: int):
        self.db = db
        self.empresa_id = empresa_id
        self.anio = anio
        self.periodo_prefijo = str(anio)

    def auditar_registro_606(self, reg: Dgii606):
        """
        Analiza un único registro del 606 y devuelve una lista de hallazgos (ValidacionFiscal).
        """
        hallazgos = []
        rnc = reg.rnc_proveedor
        monto = Decimal(str(reg.monto_facturado or 0))
        itbis_fac = Decimal(str(reg.itbis_facturado or 0))
        isr_ret_real = Decimal(str(reg.isr_retenido or 0))
        itbis_ret_real = Decimal(str(reg.itbis_retenido or 0))
        
        if monto <= 0:
            return []

        # 1. Identificar Tipo de Proveedor
        r_clean = rnc.replace("-", "")
        es_persona_fisica = len(r_clean) == 11
        padron = self.db.query(PadronDGII).filter_by(rnc=r_clean).first()
        es_rst = padron and ("RST" in (padron.regimen_pago or "") or "SIMPLIFICADO" in (padron.regimen_pago or ""))

        # 2. Determinar Tasas Esperadas
        tasa_isr_esperada = Decimal("0.00")
        tasa_itbis_ret_esperada = Decimal("0.00")
        
        if es_persona_fisica:
            if reg.tipo_bien_servicio in [2, 3]: # Honorarios o Alquileres
                tasa_isr_esperada = Decimal("0.10")
                tasa_itbis_ret_esperada = Decimal("1.00")
            elif reg.isr_retenido and (Decimal(str(reg.isr_retenido)) / monto).quantize(Decimal("0.01")) == Decimal("0.02"):
                tasa_isr_esperada = Decimal("0.02")
                tasa_itbis_ret_esperada = Decimal("1.00")
        else: # Sociedades
            if reg.tipo_bien_servicio in [2, 3] and itbis_fac > 0:
                tasa_itbis_ret_esperada = Decimal("0.30")

        # 3. Calcular Valores Esperados
        isr_esperado = (monto * tasa_isr_esperada).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        itbis_ret_esperado = (itbis_fac * tasa_itbis_ret_esperada).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # 4. Validar Discrepancias
        if abs(isr_ret_real - isr_esperado) > Decimal("1.00"):
            hallazgos.append(ValidacionFiscal(
                empresa_id=self.empresa_id,
                periodo=reg.periodo,
                tipo_validacion=f"RETENCION_ISR_{reg.ncf}",
                valor_sistema=float(isr_ret_real),
                valor_dgii=float(isr_esperado),
                diferencia=float(abs(isr_ret_real - isr_esperado)),
                estado="ERROR" if es_persona_fisica else "ADVERTENCIA",
                recomendacion_socio=f"Revisar retención NCF {reg.ncf}. Se esperaba {int(tasa_isr_esperada*100)}% de ISR."
            ))

        if abs(itbis_ret_real - itbis_ret_esperado) > Decimal("1.00"):
            hallazgos.append(ValidacionFiscal(
                empresa_id=self.empresa_id,
                periodo=reg.periodo,
                tipo_validacion=f"RETENCION_ITBIS_{reg.ncf}",
                valor_sistema=float(itbis_ret_real),
                valor_dgii=float(itbis_ret_esperado),
                diferencia=float(abs(itbis_ret_real - itbis_ret_esperado)),
                estado="ERROR" if es_persona_fisica else "ADVERTENCIA",
                recomendacion_socio=f"Revisar retención NCF {reg.ncf}. Se esperaba {int(tasa_itbis_ret_esperada*100)}% de ITBIS."
            ))

        return hallazgos

    def ejecutar_auditoria_completa(self):
        """
        Ejecuta la auditoría para todos los registros del año fiscal.
        """
        print(f"  [Auditoria] Analizando retenciones año {self.anio}...")
        registros = self.db.query(Dgii606).filter(
            and_(Dgii606.empresa_id == self.empresa_id, Dgii606.periodo.like(f"{self.periodo_prefijo}%"), Dgii606.anulada == False)
        ).all()
        
        total_red_flags = []
        for reg in registros:
            hallazgos = self.auditar_registro_606(reg)
            for h in hallazgos:
                self.db.add(h)
                total_red_flags.append({
                    "tipo": h.tipo_validacion,
                    "msg": h.recomendacion_socio,
                    "estado": h.estado
                })
                
        self.db.commit()
        return total_red_flags
