"""
generador_ir2_oficial.py — Módulo de Inyección al Master Template Oficial DGII
================================================================================
Clona la plantilla oficial IR-2-2018.xls suministrada por la DGII, inyecta
los datos calculados por nuestro motor fiscal (EstadoFinanciero) en las celdas
exactas del formulario, y entrega un (.xls) listo para imprimir y firmar.
"""
import os
import shutil
import xlrd
import xlwt
from xlutils.copy import copy as xl_copy
from sqlalchemy.orm import Session
from database import SessionLocal, Empresa, EstadoFinanciero

# Configuración Dinámica e Industrial
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_XLS = os.path.join(BASE_DIR, "templates", "IR-2-2018.xls")
OUTPUT_DIR   = os.path.join(BASE_DIR, "data", "output")

# Mapa de celdas (IR-2 Versión 2018)
MAPA_IR2 = {
    # DATOS GENERALES
    "rnc":              ("IR-2", 9,   7),
    "razon_social":     ("IR-2", 9,  14),
    "anio_fiscal":      ("IR-2",  3,  19),
    # DETERMINACIÓN RENTA
    "cs_A_ingresos":      ("IR-2", 17, 26),
    "cs_1_beneficio":     ("IR-2", 19, 26),
    "cs_7_renta_neta":    ("IR-2", 25, 26),
    "cs_9_renta_impon":   ("IR-2", 27, 26),
    "cs_11_renta_final":  ("IR-2", 29, 26),
    "cs_12_isr":          ("IR-2", 30, 26),
    "cs_23_diff_pagar":   ("IR-2", 41, 26),
    # B-1: ESTADO DE RESULTADOS
    "rnc_b1":               ("B-1",  8,  4),
    "razon_social_b1":      ("B-1",  8, 10),
    "anio_b1":              ("B-1",  3,  9),
    "b1_ingresos_ventas":   ("B-1", 13,  8),
    "b1_costo_venta":       ("B-1", 33,  8),
}

def fmt(valor):
    try:
        return float(valor or 0)
    except (TypeError, ValueError):
        return 0.0

def generar_ir2_oficial(rnc: str, anio: int, db: Session = None):
    """
    Genera el archivo XLS oficial inyectando datos de la base de datos.
    Soporta inyección de sesión externa para cumplimiento industrial.
    """
    local_db = False
    if db is None:
        db = SessionLocal()
        local_db = True

    try:
        # 1. Recuperar datos
        cliente = db.query(Empresa).filter_by(rnc=rnc).first()
        if not cliente:
            raise ValueError(f"Empresa RNC {rnc} no encontrada.")

        er = db.query(EstadoFinanciero).filter(
            EstadoFinanciero.empresa_id == cliente.id,
            EstadoFinanciero.periodo == str(anio)
        ).order_by(EstadoFinanciero.id.desc()).first()
        
        if not er:
            raise ValueError(f"No hay registros financieros para {rnc} en {anio}")

        # 2. Clonación
        if not os.path.exists(TEMPLATE_XLS):
            # Fallback a la ruta de descarga si la normalizada no existe (para desarrollo)
            # Pero en producción DEBE estar en templates/
            alt_path = r"C:\Users\pgaco\Downloads\IR-2-2018\IR-2-2018\IR-2-2018.xls"
            if os.path.exists(alt_path):
                shutil.copy(alt_path, TEMPLATE_XLS)
            else:
                raise FileNotFoundError(f"Plantilla no encontrada en {TEMPLATE_XLS}")

        rb = xlrd.open_workbook(TEMPLATE_XLS, formatting_info=True)
        wb = xl_copy(rb)

        # 3. Datos
        valores = {
            "rnc": rnc,
            "razon_social": cliente.nombre_empresa,
            "anio_fiscal": str(anio),
            "cs_A_ingresos": fmt(er.ventas_totales),
            "cs_1_beneficio": fmt(er.utilidad_bruta),
            "cs_7_renta_neta": fmt(er.renta_imponible),
            "cs_9_renta_impon": fmt(er.renta_imponible),
            "cs_11_renta_final": fmt(er.renta_imponible),
            "cs_12_isr": fmt(er.isr_calcular),
            "cs_23_diff_pagar": fmt(er.isr_pagar),
            "rnc_b1": rnc,
            "razon_social_b1": cliente.nombre_empresa,
            "anio_b1": str(anio),
            "b1_ingresos_ventas": fmt(er.ventas_totales),
            "b1_costo_venta": fmt(er.costo_ventas),
        }

        # 4. Inyección
        hojas_por_nombre = {rb.sheet_names()[i]: i for i in range(rb.nsheets)}
        for campo, (hoja_nombre, fila, col) in MAPA_IR2.items():
            if hoja_nombre in hojas_por_nombre:
                idx = hojas_por_nombre[hoja_nombre]
                ws = wb.get_sheet(idx)
                ws.write(fila, col, valores.get(campo, ""))

        # 5. Guardar
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        filename = f"IR2_OFICIAL_{anio}_{rnc}.xls"
        ruta_salida = os.path.join(OUTPUT_DIR, filename)
        wb.save(ruta_salida)
        return ruta_salida

    finally:
        if local_db:
            db.close()

if __name__ == "__main__":
    # Prueba rápida
    try:
        ruta = generar_ir2_oficial("130826552", 2025)
        print(f"[OK] Generado en: {ruta}")
    except Exception as e:
        print(f"[!] Error: {e}")
