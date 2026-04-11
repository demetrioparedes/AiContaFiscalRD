"""
motor_fiscal.py — Orquestador Fiscal Principal (Nivel Socio Senior)
===================================================================
Orquestador que ejecuta TODO el pipeline desde la carga de 606/607 
hasta la generación del IR-2 con validaciones de bloqueo.
"""
import sys
import os
import logging
from typing import Dict, List, Any
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from database import (
    SessionLocal, Empresa, Dgii606, Dgii607, DgiiIt1, ClasificacionFiscal,
    EstadoFinanciero, ValidacionFiscal, TssNomina, ActivoFijo, Ir18Retenciones, Socio
)

# Importamos motores refinados como Clases
from motor_inventario import MotorInventario
from motor_activos import MotorActivosFijos
from auditoria_retenciones import AuditoriaRetenciones
from auditoria_experta import AuditoriaExperta
from motor_beneficiario_final import MotorBeneficiarioFinal
from validador_rnc import ValidadorRNC
from etl_ir17 import procesar_ir17_mensual

class OrquestadorFiscal:
    """
    Orquestador Fiscal - Nivel Socio Senior (BIG-4 Analytics).
    Ejecuta el pipeline secuencial con bloqueo fuerte ante inconsistencias críticas.
    """

    def __init__(self, db: Session, rnc_empresa: str, anio_fiscal: int):
        self.db = db
        self.anio_fiscal = anio_fiscal
        self.anio_str = str(anio_fiscal)
        
        self.empresa = db.query(Empresa).filter_by(rnc=rnc_empresa).first()
        if not self.empresa:
            raise ValueError(f"Empresa con RNC {rnc_empresa} no encontrada.")
        
        self.empresa_id = self.empresa.id
        self.asientos_propuestos: List[Dict] = []

    def ejecutar_auditoria_fiscal_completa(self) -> Dict[str, Any]:
        """Pipeline completo y secuencial de auditoría y cálculo."""
        logging.info(f"[ORQUESTADOR] Iniciando Pipeline Senior para {self.empresa.nombre_empresa} ({self.anio_fiscal})...")
        
        resultados = {
            "estado": "En proceso",
            "bloqueos": [],
            "red_flags": [],
            "asientos_propuestos": [],
            "resumen": {},
            "anexos_h": {},
            "ir2_data": None
        }

        # Limpiar hallazgos previos en la base de datos (con flush, no commit aún)
        self.db.query(ValidacionFiscal).filter_by(empresa_id=self.empresa_id, periodo=self.anio_str).delete()
        self.db.flush()

        # ==================== FASE 1: ESTADO DE RESULTADOS BASE ====================
        logging.info("  [Fase 1] Generando ER Base...")
        er_base = self._generar_er_base()

        # ==================== FASE 2: MOTOR INVENTARIO (Anexo B) ====================
        logging.info("  [Fase 2] Motor Inventario...")
        motor_inv = MotorInventario(self.db, self.empresa_id, self.anio_fiscal)
        costo_ventas = motor_inv.calcular_costo_ventas()
        resultados["resumen"]["costo_ventas"] = costo_ventas

        # ==================== FASE 3: MOTOR ACTIVOS FIJOS (Anexo D) ====================
        logging.info("  [Fase 3] Motor Activos Fijos...")
        motor_act = MotorActivosFijos(self.db, self.empresa_id, self.anio_fiscal)
        depreciacion = motor_act.calcular_depreciacion_anual()
        resultados["resumen"]["depreciacion"] = depreciacion

        # ==================== FASE 4: AUDITORÍA DE RETENCIONES ====================
        logging.info("  [Fase 4] Auditoría Retenciones...")
        motor_ret = AuditoriaRetenciones(self.db, self.empresa_id, self.anio_fiscal)
        ret_flags = motor_ret.ejecutar_auditoria_completa()
        resultados["red_flags"].extend(ret_flags)

        # ==================== FASE 5: AUDITORÍA EXPERTA SOCIO SENIOR ====================
        logging.info("  [Fase 5] Auditoría Experta (Cruces)...")
        socio_audit = AuditoriaExperta(self.db, self.empresa_id, self.anio_fiscal)
        socio_audit.ejecutar_auditoria_completa()
        # Recuperamos hallazgos guardados en BD por consistencia
        experta_hallazgos = self.db.query(ValidacionFiscal).filter(
            and_(ValidacionFiscal.empresa_id == self.empresa_id, 
                 ValidacionFiscal.periodo == self.anio_str,
                 ValidacionFiscal.tipo_validacion.like("CRUCE_%"))
        ).all()
        
        for h in experta_hallazgos:
            if h.estado != "OK":
                resultados["red_flags"].append({
                    "tipo": h.tipo_validacion,
                    "msg": h.recomendacion_socio,
                    "estado": h.estado
                })
                if h.asiento_propuesto:
                    self.asientos_propuestos.append({"origen": h.tipo_validacion, "asiento": h.asiento_propuesto})

        # ==================== FASE 6: MOTOR BENEFICIARIO FINAL (H-1 / H-2) ====================
        logging.info("  [Fase 6] Motor Beneficiario Final...")
        motor_bf = MotorBeneficiarioFinal(self.db, self.empresa_id, self.anio_fiscal)
        
        # Validación de integridad para bloqueo
        integridad = motor_bf.validar_integridad_accionaria()
        if integridad.get("estado") == "Bloqueado":
            resultados["bloqueos"].append(integridad)

        # Socios y Red Flags de lavado/RNC
        motor_bf.ejecutar_auditoria_socios()
        resultados["anexos_h"] = {
            "socios": [{"identificador": s.identificador, "nombre": s.nombre_razon_social, "pct": float(s.porcentaje_participacion)} for s in self.db.query(Socio).filter_by(empresa_id=self.empresa_id).all()]
        }

        # ==================== FASE 7: VALIDACIÓN RNC PROACTIVA (PADRÓN DGII) ====================
        logging.info("  [Fase 7] Validación RNC Padrón DGII...")
        validador_rnc = ValidadorRNC(self.db)
        
        # 1. Validar Socios (Bloqueo si inactivos)
        riesgos_socios = validador_rnc.validar_socios(self.empresa_id)
        for r in riesgos_socios:
            if r["tipo"] == "BLOQUEO":
                resultados["bloqueos"].append(r)
                resultados["estado"] = "Bloqueado"
            else:
                resultados["red_flags"].append(r)
                
        # 2. Validar Proveedores Críticos (Advertencia)
        riesgos_prov = validador_rnc.validar_proveedores_criticos(self.empresa_id, self.anio_str)
        resultados["red_flags"].extend(riesgos_prov)

        # ==================== FASE 8: GENERACIÓN MENSUAL IR-17 ====================
        logging.info("  [Fase 8] Generando registros mensuales IR-17...")
        try:
            procesar_ir17_mensual(self.db, self.empresa.rnc, self.anio_fiscal)
        except Exception as e:
            logging.warning(f"  [!] Fallo no crítico en IR-17: {e}")

        # ==================== FASE 9: CONSOLIDACIÓN Y CÁLCULO FINAL IR-2 ====================
        logging.info("  [Fase 9] Consolidación Final...")
        try:
            if resultados["bloqueos"]:
                resultados["estado"] = "Bloqueado"
                resultados["mensaje"] = "El proceso se detuvo por inconsistencias críticas."
            else:
                self._consolidar_resultados(er_base, costo_ventas, depreciacion)
                resultados["ir2_data"] = {
                    "ventas": er_base.ventas_totales,
                    "utilidad_bruta": er_base.utilidad_bruta,
                    "renta_neta_imponible": er_base.renta_imponible,
                    "isr_pagar": er_base.isr_calcular
                }
                resultados["estado"] = "Listo"
            
            # ATOMICIDAD: Un solo commit para todo el pipeline
            self.db.commit()
            logging.info(f"[ORQUESTADOR] Pipeline completado. Estado: {resultados['estado']}")

        except Exception as e:
            self.db.rollback()
            logging.error(f"[!] Error en pipeline: {e}")
            resultados["estado"] = "Error"
            resultados["mensaje"] = str(e)
            raise e

        resultados["asientos_propuestos"] = self.asientos_propuestos
        return resultados

    def _generar_er_base(self):
        """Calcula ventas y gastos base desde 606/607."""
        er_prev = self.db.query(EstadoFinanciero).filter_by(empresa_id=self.empresa_id, periodo=self.anio_str).first()
        if er_prev: self.db.delete(er_prev)
        
        ventas = float(self.db.query(func.sum(Dgii607.monto_facturado)).filter(
            and_(Dgii607.empresa_id == self.empresa_id, Dgii607.periodo.like(f"{self.anio_str}%"), Dgii607.anulada != 1)
        ).scalar() or 0.0)

        ventas_exentas = float(self.db.query(func.sum(Dgii607.monto_exento)).filter(
            and_(Dgii607.empresa_id == self.empresa_id, Dgii607.periodo.like(f"{self.anio_str}%"), Dgii607.anulada != 1)
        ).scalar() or 0.0)

        gastos = float(self.db.query(func.sum(Dgii606.monto_facturado)).filter(
            and_(Dgii606.empresa_id == self.empresa_id, Dgii606.periodo.like(f"{self.anio_str}%"), 
                 Dgii606.anulada != 1, Dgii606.tipo_bien_servicio != 2)
        ).scalar() or 0.0)

        er = EstadoFinanciero(
            empresa_id=self.empresa_id, periodo=self.anio_str,
            ventas_totales=ventas, ventas_exentas=ventas_exentas, 
            costo_ventas=0.0, gastos_operativos=gastos,
            renta_imponible=0.0, isr_calcular=0.0
        )
        self.db.add(er)
        self.db.flush()
        return er

    def _consolidar_resultados(self, er, costo_ventas, depreciacion):
        """Calcula el ISR final al 27%."""
        er.costo_ventas = costo_ventas
        er.utilidad_bruta = er.ventas_totales - costo_ventas
        u_operativa = Decimal(str(er.utilidad_bruta)) - Decimal(str(er.gastos_operativos))
        renta_imponible = max(Decimal("0.0"), u_operativa - Decimal(str(depreciacion)))
        
        er.renta_imponible = float(renta_imponible)
        er.isr_calcular = float(renta_imponible * Decimal("0.27"))
        er.utilidad_neta = float(renta_imponible - Decimal(str(er.isr_calcular)))
        self.db.flush()

    def obtener_dashboard_data(self) -> Dict:
        """
        Consolida y formatea datos para el Dashboard Premium del Frontend.
        Ejecuta el pipeline si es necesario y devuelve estructura limpia.
        """
        res = self.ejecutar_auditoria_fiscal_completa()
        
        # Sincronización con campos esperados en app.js
        hallazgos = []
        
        # Recuperar todas las validaciones de la base de datos para este periodo
        validaciones = self.db.query(ValidacionFiscal).filter_by(
            empresa_id=self.empresa_id, periodo=self.anio_str
        ).all()

        for v in validaciones:
            if v.estado != "OK":
                hallazgos.append({
                    "tipo": v.tipo_validacion.replace("CRUCE_", "Cruce ").title(),
                    "descripcion": v.recomendacion_socio or "Se detectó una discrepancia que requiere revisión.",
                    "estado": "CRITICO" if v.estado == "ROJO" else "ADVERTENCIA",
                    "valor_dgii": float(v.valor_dgii or 0),
                    "valor_auditoria": float(v.valor_sistema or 0)
                })

        # Estructura final optimizada para app.js
        return {
            "resumen": {
                "ingresos": res["ir2_data"]["ventas"] if res["ir2_data"] else 0,
                "costos": res["resumen"].get("costo_ventas", 0),
                "renta_neta": res["ir2_data"]["renta_neta_imponible"] if res["ir2_data"] else 0,
                "isr_estimado": res["ir2_data"]["isr_pagar"] if res["ir2_data"] else 0
            },
            "accionistas": res["anexos_h"].get("socios", []),
            "hallazgos": hallazgos,
            "asientos": res.get("asientos_propuestos", []),
            "estado_pipeline": res["estado"]
        }

def main():
    db = SessionLocal()
    try:
        orquestador = OrquestadorFiscal(db, "130826552", 2025)
        res = orquestador.ejecutar_auditoria_fiscal_completa()
        print(f"\n[OK] Pipeline Ejecutado. Estado: {res['estado']}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
