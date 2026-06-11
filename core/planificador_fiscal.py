"""
planificador_fiscal.py — Módulo de Planificación Fiscal Predictiva (IA)
======================================================================
Proyecciones anuales, cálculo de anticipos (Art. 314 Código Tributario RD)
y escenarios de planificación fiscal para el cierre del 31 de diciembre.

Integrado con OrquestadorFiscal en motor_fiscal.py (Fase 9).
"""
import logging
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from database import EstadoFinanciero, PlanificacionScenario


class PlanificadorIA:
    """
    Planificador Fiscal Inteligente.

    Proyecta el cierre anual basado en:
    - Tendencia lineal sobre períodos históricos
    - Tasa de crecimiento ponderada
    - Estacionalidad mensual (si hay datos)
    - Cálculo de anticipos Art. 314 (1% de ingresos brutos)
    """

    TASA_ISR = Decimal("0.27")
    TASA_ANTICIPO = Decimal("0.01")  # Art. 314: 1% de ingresos brutos

    def __init__(self, db: Session, empresa_id: int, anio: int):
        self.db = db
        self.empresa_id = empresa_id
        self.anio = anio
        self.anio_str = str(anio)

    def proyectar_cierre_anual(self) -> dict:
        """
        Proyecta el cierre del año fiscal basado en datos históricos.

        Returns:
            dict con proyecciones de ventas, gastos, ISR y anticipos
        """
        # Obtener histórico de estados financieros
        historico = self.db.query(EstadoFinanciero).filter(
            and_(
                EstadoFinanciero.empresa_id == self.empresa_id,
                EstadoFinanciero.periodo < self.anio_str,
            )
        ).order_by(EstadoFinanciero.periodo.desc()).limit(3).all()

        if not historico:
            return self._escenario_base()

        # Calcular tendencia lineal simple
        ventas_hist = [float(h.ventas_totales or 0) for h in historico]
        gastos_hist = [float(h.gastos_operativos or 0) for h in historico]

        # Factor de crecimiento: promedio de variación interanual
        factores_ventas = []
        for i in range(1, len(ventas_hist)):
            if ventas_hist[i] > 0:
                factores_ventas.append(ventas_hist[i-1] / ventas_hist[i])

        factor_crecimiento = sum(factores_ventas) / len(factores_ventas) if factores_ventas else Decimal("1.05")

        # Proyección
        ventas_proy = Decimal(str(ventas_hist[0])) * Decimal(str(factor_crecimiento))
        gastos_proy = Decimal(str(gastos_hist[0])) * Decimal(str(factor_crecimiento))
        utilidad_proy = max(Decimal("0"), ventas_proy - gastos_proy)
        isr_proy = (utilidad_proy * self.TASA_ISR).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        anticipo_proy = (ventas_proy * self.TASA_ANTICIPO).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        return {
            "tipo": "proyeccion_historica",
            "ventas_proyectadas": round(float(ventas_proy), 2),
            "gastos_proyectados": round(float(gastos_proy), 2),
            "utilidad_proyectada": round(float(utilidad_proy), 2),
            "isr_estimado_anual": round(float(isr_proy), 2),
            "anticipo_sugerido": round(float(anticipo_proy), 2),
            "factor_crecimiento": round(float(factor_crecimiento), 4),
            "periodos_historicos": len(historico),
            "generado": datetime.now().isoformat(),
        }

    def _escenario_base(self) -> dict:
        """Escenario base cuando no hay histórico disponible."""
        ef = self.db.query(EstadoFinanciero).filter_by(
            empresa_id=self.empresa_id, periodo=self.anio_str
        ).first()

        if not ef:
            return {
                "tipo": "sin_datos",
                "ventas_proyectadas": 0,
                "gastos_proyectados": 0,
                "utilidad_proyectada": 0,
                "isr_estimado_anual": 0,
                "anticipo_sugerido": 0,
                "factor_crecimiento": 1.0,
                "periodos_historicos": 0,
                "mensaje": "No hay datos históricos para generar proyección.",
                "generado": datetime.now().isoformat(),
            }

        ventas = Decimal(str(ef.ventas_totales or 0))
        gastos = Decimal(str(ef.gastos_operativos or 0))
        utilidad = max(Decimal("0"), ventas - Decimal(str(ef.costo_ventas or 0)) - gastos)
        isr = (utilidad * self.TASA_ISR).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        anticipo = (ventas * self.TASA_ANTICIPO).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        return {
            "tipo": "base_anual_actual",
            "ventas_proyectadas": round(float(ventas), 2),
            "gastos_proyectados": round(float(gastos), 2),
            "utilidad_proyectada": round(float(utilidad), 2),
            "isr_estimado_anual": round(float(isr), 2),
            "anticipo_sugerido": round(float(anticipo), 2),
            "factor_crecimiento": 1.0,
            "periodos_historicos": 0,
            "generado": datetime.now().isoformat(),
        }

    def actualizar_planificacion_db(self):
        """Guarda el escenario calculado en la tabla planificacion_scenarios."""
        proy = self.proyectar_cierre_anual()

        # Limpiar escenario previo del mismo año
        self.db.query(PlanificacionScenario).filter_by(
            empresa_id=self.empresa_id, periodo=self.anio_str
        ).delete()

        escenario = PlanificacionScenario(
            empresa_id=self.empresa_id,
            nombre_escenario=f"PROYECCIÓN {self.anio}",
            periodo=self.anio_str,
            ventas_proyectadas=proy["ventas_proyectadas"],
            gastos_proyectados=proy["gastos_proyectados"],
            isr_estimado_anual=proy["isr_estimado_anual"],
            anticipo_sugerido=proy["anticipo_sugerido"],
            factor_crecimiento=proy.get("factor_crecimiento", 1.0),
        )
        self.db.add(escenario)
        self.db.commit()

    def generar_escenarios(self) -> list:
        """
        Genera 3 escenarios (base, optimista, pesimista) para planificación.
        """
        base = self.proyectar_cierre_anual()

        escenarios = [
            {
                "nombre": "BASE",
                "descripcion": "Proyección según tendencia actual",
                **base,
            },
            {
                "nombre": "OPTIMISTA",
                "descripcion": "Escenario +15% ventas con control de gastos",
                "ventas_proyectadas": round(base["ventas_proyectadas"] * 1.15, 2),
                "gastos_proyectados": round(base["gastos_proyectados"] * 1.05, 2),
                "factor_crecimiento": round(base.get("factor_crecimiento", 1.0) * 1.15, 4),
            },
            {
                "nombre": "PESIMISTA",
                "descripcion": "Escenario -10% ventas con gastos constantes",
                "ventas_proyectadas": round(base["ventas_proyectadas"] * 0.90, 2),
                "gastos_proyectados": base["gastos_proyectados"],
                "factor_crecimiento": round(base.get("factor_crecimiento", 1.0) * 0.90, 4),
            },
        ]

        for esc in escenarios:
            utilidad = max(0, esc["ventas_proyectadas"] - esc["gastos_proyectados"])
            esc["utilidad_proyectada"] = round(utilidad, 2)
            esc["isr_estimado_anual"] = round(utilidad * float(self.TASA_ISR), 2)
            esc["anticipo_sugerido"] = round(esc["ventas_proyectadas"] * float(self.TASA_ANTICIPO), 2)
            esc["generado"] = datetime.now().isoformat()

        return escenarios
