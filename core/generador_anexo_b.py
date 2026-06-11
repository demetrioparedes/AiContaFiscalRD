"""
generador_anexo_b.py — Motor 1: Reporte Consolidado del Anexo B (Estado de Costos y Gastos)
============================================================================================
Lee los registros del 606 ya clasificados en la BD y genera el Resumen del Anexo B-1
listo para llenar el formulario IR-2 de la DGII.

Categorías Oficiales del Anexo B-1 (DGII):
  B1  - Gastos de Personal
  B2  - Gastos por Trabajos, Suministros y Servicios
  B3  - Arrendamientos
  B4  - Gastos de Activos Fijos (Depreciación)
  B5  - Gastos de Representación
  B6  - Otras Deducciones Admitidas
  B7  - Gastos Financieros
  B8  - Gastos Extraordinarios
  B9  - Compras / Costos de Ventas
  B10 - Adquisición de Activos (no deducible directamente)
  B11 - Gastos de Seguros
"""
import sys, os

# Resolución dinámica de ruta del proyecto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from database import SessionLocal, Empresa, Dgii606
from sqlalchemy import func, and_
from motor_clasificacion import mapear_anexo_b_general

# Mapa de sub-cuentas IA => Casilla Anexo B Oficial
MAPA_CUENTA_A_ANEXO_B = {
    "Gastos de Personal":                   "B1 - Gastos de Personal",
    "Seguros Obra y Vida":                  "B11 - Gastos de Seguros",
    "Telecomunicaciones":                   "B2 - Suministros y Servicios",
    "Combustibles y Lubricantes":           "B2 - Suministros y Servicios",
    "Materiales de Oficina":                "B2 - Suministros y Servicios",
    "Gastos de Limpieza":                   "B2 - Suministros y Servicios",
    "Agua y Basura":                        "B2 - Suministros y Servicios",
    "Reparaciones y Mantenimiento":         "B2 - Suministros y Servicios",
    "Energía Eléctrica":                    "B2 - Suministros y Servicios",
    "Suministros Informáticos / Software":  "B2 - Suministros y Servicios",
    "Honorarios Profesionales":             "B2 - Suministros y Servicios",
    "Arrendamientos":                       "B3 - Arrendamientos",
    "Gastos de Activos Fijos (Depreciación)": "B4 - Activos Fijos / Deprec.",
    "Dietas y Gastos de Viaje":             "B5 - Gastos de Representación",
    "Publicidad y Mercadeo":                "B5 - Gastos de Representación",
    "Gastos Financieros":                   "B7 - Gastos Financieros",
    "Comisiones e Intereses Bancarios":     "B7 - Gastos Financieros",
    "Compras para Costo de Venta":          "B9 - Compras / Costo de Ventas",
    "Activos Capitalizables":               "B10 - Adquisición de Activos",
    "Otras deducciones / Gastos Generales": "B6 - Otras Deducciones",
}

def generar_reporte_anexo_b(rnc_empresa: str, anio: int):
    """Agrupa los gastos del 606 por categoría y genera el Resumen del Anexo B."""
    db = SessionLocal()
    anio_str = str(anio)
    
    empresa = db.query(Empresa).filter_by(rnc=rnc_empresa).first()
    if not empresa:
        print(f"  [!] Empresa RNC {rnc_empresa} no encontrada.")
        db.close()
        return {}

    # Agrupar por cuenta_contable
    resultado = db.query(
        Dgii606.cuenta_contable, 
        func.sum(Dgii606.monto_facturado).label("total")
    ).filter(
        and_(
            Dgii606.empresa_id == empresa.id,
            Dgii606.periodo.like(f"{anio_str}%"),
            Dgii606.anulada != 1
        )
    ).group_by(Dgii606.cuenta_contable).all()

    db.close()
    
    # Consolida al nivel del Anexo B oficial
    anexo_b = {}
    for cuenta, total in resultado:
        if not cuenta:
            cuenta = "Otras deducciones / Gastos Generales"
        categoria_oficial = MAPA_CUENTA_A_ANEXO_B.get(cuenta, "B6 - Otras Deducciones")
        anexo_b[categoria_oficial] = anexo_b.get(categoria_oficial, 0.0) + float(total or 0)

    return dict(sorted(anexo_b.items()))

def imprimir_anexo_b(rnc_empresa: str, anio: int):
    """Imprime el Resumen del Anexo B en consola (para auditoría y revisión)."""
    print("=" * 70)
    print(f"  ANEXO B - ESTADO DE COSTOS Y GASTOS | RNC: {rnc_empresa} | Año: {anio}")
    print("=" * 70)
    
    reporte = generar_reporte_anexo_b(rnc_empresa, anio)
    total_general = 0.0
    
    if not reporte:
        print("  [!] Sin datos clasificados en la BD. Procesa el 606 primero.")
        return {}
    
    for casilla, monto in reporte.items():
        total_general += monto
        print(f"  {casilla:<40}  RD$ {monto:>14,.2f}")
    
    print("-" * 70)
    print(f"  {'TOTAL GASTOS Y COSTOS DECLARABLES':<40}  RD$ {total_general:>14,.2f}")
    print("=" * 70)
    
    return reporte

if __name__ == "__main__":
    imprimir_anexo_b("130826552", 2025)
