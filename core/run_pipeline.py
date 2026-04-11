"""
run_pipeline.py — Orquestador Principal AiContaFiscalRD
=========================================================
UN SOLO COMANDO para procesar un cliente completo.

Uso:
    python run_pipeline.py

O en modo silencioso (sin preguntas interactivas), pasando un JSON de configuración:
    python run_pipeline.py --config config_elvira.json

Flujo:
  1. Solicita los 4 datos manuales que la DGII no provee
  2. Corre ETL de 606 y 607 (archivos DGII)
  3. Corre ETL del ANALISIS IT-1 (Excel del despacho)
  4. Ejecuta el Motor Fiscal SQL
  5. Ejecuta las 10 Validaciones
  6. Genera Excel IR-2 y LaTeX de Estados Financieros
"""
import sys
import os
import json
import argparse

# Ruta relativa dinámica
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "core"))

from database import SessionLocal, init_db, Empresa, Inventario, Prestamo
from etl_ingesta import ejecutar_etl
from motor_fiscal import OrquestadorFiscal
from etl_ir17 import procesar_ir17_mensual
from generador_ir17_reporte import generar_reporte_visual_ir17
from generador_final import main as generar_final

# ===========================================================
# BANNER
# ===========================================================

BANNER = """
==========================================================
  AiContaFiscalRD - Motor de Preparacion Fiscal
  Motor de Preparacion Fiscal Automatica RD
==========================================================
"""

# ===========================================================
# PASO 0: REGISTRO DEL CLIENTE Y 4 INPUTS MANUALES
# ===========================================================

def solicitar_datos_cliente():
    """Solicita los datos del cliente y los 4 inputs manuales que la DGII no provee."""
    print("\n--- PASO 1: DATOS DEL CLIENTE ---")
    rnc = input("  RNC de la empresa (sin guiones): ").strip()
    nombre = input("  Razón Social: ").strip()
    anio = int(input("  Año Fiscal (ej: 2025): ").strip())
    regimen = input("  Régimen (ordinario/simplificado): ").strip() or "ordinario"

    print("\n--- PASO 2: DATOS MANUALES (no disponibles en DGII) ---")
    print("  [i] Estos 4 datos son necesarios para completar el IR-2 al 100%")

    inv_inicial = float(input("\n  1. Inventario INICIAL del año (del IR-2 anterior): RD$ ").strip() or "0")
    inv_final   = float(input("  2. Inventario FINAL del año (conteo físico): RD$ ").strip() or "0")

    print("\n  3. Activos Fijos nuevos adquiridos este año:")
    print("     (Presiona ENTER para saltar si no hubo compras de activos)")
    activos = []
    while True:
        nombre_activo = input("     Nombre del activo (o ENTER para terminar): ").strip()
        if not nombre_activo:
            break
        valor = float(input(f"     Valor de '{nombre_activo}': RD$ ").strip() or "0")
        vida_util = int(input("     Vida útil (años): ").strip() or "5")
        activos.append({"nombre": nombre_activo, "valor": valor, "vida_util": vida_util})

    print("\n  4. Préstamos o Financiamientos:")
    prestamos = []
    while True:
        banco = input("     Nombre del banco/entidad (o ENTER para terminar): ").strip()
        if not banco:
            break
        saldo_ini = float(input(f"     Saldo INICIAL '{banco}': RD$ ").strip() or "0")
        nuevos    = float(input("     Nuevos préstamos del año: RD$ ").strip() or "0")
        pagos     = float(input("     Pagos realizados: RD$ ").strip() or "0")
        intereses = float(input("     Gastos de intereses: RD$ ").strip() or "0")
        prestamos.append({
            "entidad": banco, "saldo_inicial": saldo_ini,
            "nuevos": nuevos, "pagos": pagos,
            "saldo_final": saldo_ini + nuevos - pagos,
            "intereses": intereses
        })

    print("\n--- PASO 3: ARCHIVOS A PROCESAR ---")
    directorio = input("  Directorio con los archivos 606/607 del cliente: ").strip()
    analisis_xls = input("  Ruta del archivo ANALISIS XXXX.xls: ").strip()
    retenciones = float(input("  Total de Retenciones Sufridas (IR-17/IR-18): RD$ ").strip() or "0")

    return {
        "rnc": rnc, "nombre": nombre, "anio": anio, "regimen": regimen,
        "inv_inicial": inv_inicial, "inv_final": inv_final,
        "activos": activos, "prestamos": prestamos,
        "directorio": directorio, "analisis_xls": analisis_xls,
        "retenciones": retenciones
    }

def cargar_config_json(ruta_json):
    """Carga la configuración desde un archivo JSON (modo no interactivo)."""
    with open(ruta_json, "r", encoding="utf-8") as f:
        return json.load(f)

# ===========================================================
# PASO 1: REGISTRAR CLIENTE EN BD
# ===========================================================

def registrar_cliente(config, db):
    print(f"\n[1/6] Registrando empresa: {config['nombre']} (RNC: {config['rnc']})...")
    empresa = db.query(Empresa).filter_by(rnc=config["rnc"]).first()
    if not empresa:
        empresa = Empresa(
            rnc=config["rnc"],
            nombre_empresa=config["nombre"]
        )
        db.add(empresa)
        db.commit()
        db.refresh(empresa)
        print(f"     [+] Empresa creada (ID: {empresa.id})")
    else:
        print(f"     [i] Empresa ya existe (ID: {empresa.id})")
    return empresa



# ===========================================================
# ORQUESTADOR PRINCIPAL
# ===========================================================

def ejecutar_pipeline(config):
    print(BANNER)
    print(f"  Cliente: {config['nombre']}")
    print(f"  RNC:     {config['rnc']}")
    print(f"  Año:     {config['anio']}")
    print()

    rnc  = config["rnc"]
    anio = config["anio"]
    retenciones = config.get("retenciones", 0.0)
    inv_inicial = config.get("inv_inicial", 0.0)

    # Asegurar tablas existen
    init_db()

    db = SessionLocal()
    try:
        # PASO 1: Registrar cliente y datos manuales
        registrar_cliente(config, db)
    finally:
        db.close()

    # PASO 2: ETL 606 + 607
    print(f"\n[2/6] Ingesta 606/607 desde: {config.get('directorio', '')}")
    if config.get("directorio") and os.path.isdir(config["directorio"]):
        ejecutar_etl(config["directorio"], rnc)
    else:
        print("     [i] Directorio no especificado o no existe. Usando datos existentes en BD.")

    # PASO 3: ETL IT-1 + Anticipos
    print(f"\n[3/6] Procesando IT-1 y Anticipos...")
    print("     [i] Módulo IT-1 y Anticipos ahora son procesados automáticamente por el Motor BIG4.")

    # PASO 4: Motor Fiscal (Estado de Resultados e ISR)
    print(f"\n[4/6] Ejecutando Motor Fiscal Senior (Orquestador)...")
    db = SessionLocal()
    try:
        orquestador = OrquestadorFiscal(db, rnc, anio)
        res_pipeline = orquestador.ejecutar_auditoria_fiscal_completa()
        
        # PASO 4.5: Motor IR-17 (Retenciones Mensuales)
        print(f"\n[4.5/6] Generando Declaraciones IR-17...")
        procesar_ir17_mensual(db, rnc, anio)
        
    finally:
        db.close()

    # PASO 6: Generar entregables
    print(f"\n[6/6] Generando documentos finales...")
    
    # Generar Reporte Visual IR-17
    generar_reporte_visual_ir17(rnc, anio)
    
    # Otros entregables (IR-2, LaTeX)
    modo = config.get("modo", "rapido")
    generar_final(modo)

    print("\n" + "=" * 60)
    print("  PIPELINE COMPLETADO EXITOSAMENTE")
    print("  Revisa los resultados en:")
    output_path = os.path.join(BASE_DIR, "data", "output")
    print(f"  {output_path}")
    print("=" * 60)


# ===========================================================
# PUNTO DE ENTRADA
# ===========================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AiContaFiscalRD — Pipeline Fiscal")
    parser.add_argument("--config", help="Ruta al archivo JSON de configuración (modo no interactivo)")
    args = parser.parse_args()

    if args.config:
        config = cargar_config_json(args.config)
    else:
        config = solicitar_datos_cliente()

    ejecutar_pipeline(config)
