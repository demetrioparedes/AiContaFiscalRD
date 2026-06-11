"""
seed_maestras.py
Pobla las tablas maestras del sistema con las reglas normativas.
Solo se ejecuta una vez (o cuando se actualicen las reglas fiscales de la DGII).
"""
import sys, os

# Resolución dinámica de ruta del proyecto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from database import SessionLocal, ClasificacionFiscal, CorrespondenciaIr2

def seed_clasificacion(db):
    print("[*] Sembrando tabla clasificacion_fiscal...")
    db.query(ClasificacionFiscal).delete()

    # Reglas oficiales de la DGII basadas en tipo de NCF
    reglas = [
        {"tipo_ncf": "B01", "naturaleza": "gasto deducible",  "cuenta_contable": "gastos_operativos",       "tratamiento": "deducible",   "deducible": True,  "inventario": False, "activo_fijo": False},
        {"tipo_ncf": "B02", "naturaleza": "gasto personal",   "cuenta_contable": "gastos_no_deducibles",     "tratamiento": "no_deducible","deducible": False, "inventario": False, "activo_fijo": False},
        {"tipo_ncf": "B04", "naturaleza": "activo fijo",      "cuenta_contable": "propiedad_planta_equipo",  "tratamiento": "depreciable", "deducible": True,  "inventario": False, "activo_fijo": True},
        {"tipo_ncf": "B11", "naturaleza": "inventario",       "cuenta_contable": "inventario",               "tratamiento": "costo",       "deducible": True,  "inventario": True,  "activo_fijo": False},
        {"tipo_ncf": "B13", "naturaleza": "servicios",        "cuenta_contable": "gastos_servicios",         "tratamiento": "deducible",   "deducible": True,  "inventario": False, "activo_fijo": False},
        {"tipo_ncf": "B14", "naturaleza": "gastos menores",   "cuenta_contable": "gastos_menores",           "tratamiento": "deducible",   "deducible": True,  "inventario": False, "activo_fijo": False},
        {"tipo_ncf": "B15", "naturaleza": "gubernamental",    "cuenta_contable": "otros_gastos",             "tratamiento": "exento",      "deducible": False, "inventario": False, "activo_fijo": False},
        {"tipo_ncf": "E31", "naturaleza": "exterior",         "cuenta_contable": "gastos_importacion",       "tratamiento": "deducible",   "deducible": True,  "inventario": False, "activo_fijo": False},
    ]

    for r in reglas:
        db.add(ClasificacionFiscal(
            tipo_ncf=r["tipo_ncf"], naturaleza=r["naturaleza"],
            cuenta_contable=r["cuenta_contable"], tratamiento=r["tratamiento"],
            deducible=r["deducible"],
            afecta_inventario=r["inventario"],
            afecta_activo_fijo=r["activo_fijo"]
        ))
        print(f"     + {r['tipo_ncf']}  ->  {r['cuenta_contable']}  ({r['tratamiento']})")

    db.commit()
    print("  [OK] Clasificacion Fiscal lista.\n")

def seed_correspondencia_ir2(db):
    print("[*] Sembrando tabla correspondencia_ir2 (Mapa Normativo DGII)...")
    db.query(CorrespondenciaIr2).delete()

    # Mapa exacto de cada casilla del formulario IR-2 a su fuente de datos
    correspondencias = [
        # Anexo A - Estado de Resultados
        {"campo": "Casilla 1 - Ingresos Brutos",            "tabla": "estado_resultados",  "campo_db": "total_ingresos",          "anexo": "A", "casilla": "1"},
        {"campo": "Casilla 10 - Costo de Ventas",           "tabla": "estado_resultados",  "campo_db": "costo_ventas",            "anexo": "A", "casilla": "10"},
        {"campo": "Casilla 11 - Renta Bruta",               "tabla": "estado_resultados",  "campo_db": "utilidad_bruta",          "anexo": "A", "casilla": "11"},
        {"campo": "Casilla 15 - Gastos Deducibles",         "tabla": "estado_resultados",  "campo_db": "total_gastos",            "anexo": "A", "casilla": "15"},
        {"campo": "Casilla 16 - Utilidad Operativa",        "tabla": "estado_resultados",  "campo_db": "utilidad_operativa",      "anexo": "A", "casilla": "16"},
        # Anexo B - Conciliación Fiscal
        {"campo": "Casilla B1 - Utilidad Contable",         "tabla": "ajustes_fiscales",   "campo_db": "utilidad_contable",       "anexo": "B", "casilla": "B1"},
        {"campo": "Casilla B2 - Gastos No Deducibles",      "tabla": "ajustes_fiscales",   "campo_db": "gastos_no_deducibles",    "anexo": "B", "casilla": "B2"},
        {"campo": "Casilla B3 - Ingresos Exentos",          "tabla": "ajustes_fiscales",   "campo_db": "ingresos_exentos",        "anexo": "B", "casilla": "B3"},
        {"campo": "Casilla B4 - Renta Imponible",           "tabla": "ajustes_fiscales",   "campo_db": "renta_imponible",         "anexo": "B", "casilla": "B4"},
        # Formulario IR-2 Principal
        {"campo": "ISR Causado",                            "tabla": "ajustes_fiscales",   "campo_db": "isr_causado",             "anexo": "IR2", "casilla": "20"},
        {"campo": "Anticipos Pagados",                      "tabla": "ajustes_fiscales",   "campo_db": "anticipos_pagados",       "anexo": "IR2", "casilla": "21"},
        {"campo": "Retenciones Sufridas",                   "tabla": "ajustes_fiscales",   "campo_db": "retenciones_sufridas",    "anexo": "IR2", "casilla": "22"},
        {"campo": "ISR a Pagar",                            "tabla": "ajustes_fiscales",   "campo_db": "isr_a_pagar",             "anexo": "IR2", "casilla": "23"},
        # Anexo D - Inventario
        {"campo": "Inventario Inicial",                     "tabla": "estado_resultados",  "campo_db": "inventario_inicial",      "anexo": "D", "casilla": "D1"},
        {"campo": "Compras",                                "tabla": "estado_resultados",  "campo_db": "compras_mercancia",       "anexo": "D", "casilla": "D2"},
        {"campo": "Inventario Final",                       "tabla": "estado_resultados",  "campo_db": "inventario_final",        "anexo": "D", "casilla": "D5"},
    ]

    for c in correspondencias:
        db.add(CorrespondenciaIr2(
            campo_ir2=c["campo"],
            descripcion=c["campo"],
            fuente_tabla=c["tabla"],
            fuente_campo=c["campo_db"],
            anexo=c["anexo"],
            casilla_numero=c["casilla"]
        ))
    
    db.commit()
    print(f"  [OK] {len(correspondencias)} correspondencias del IR-2 registradas.\n")

def main():
    print("=== AiContaFiscalRD: Sembrando Tablas Maestras ===\n")
    db = SessionLocal()
    try:
        seed_clasificacion(db)
        seed_correspondencia_ir2(db)
        print("[OK] Todas las tablas maestras han sido pobladas.")
        print("     El Motor de Clasificacion y el Mapa del IR-2 estan operativos.")
    finally:
        db.close()

if __name__ == "__main__":
    main()
