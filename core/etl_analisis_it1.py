"""
etl_analisis_it1.py — Extractor de IT-1 y Anticipos desde el Excel de Análisis
================================================================================
Lee el archivo estándar "ANALISIS XXXX.xls" que usa el Despacho PGA para cada cliente.
Este archivo tiene dos fuentes de datos críticas:
  1. Resumen mensual del IT-1 (Filas 12-23 de la Hoja del año):
     Mes | Total Ventas | Exentas | Grabadas | ITBIS Ventas | Adel.Compras | Adel.Import | ITBIS Pagar
  2. Tabla de Anticipos IR-2 pagados (Filas 30-41 en adelante):
     NCF pago | Período | NCF Empresa | Tipo | Formulario | Estado | Fecha | Monto

Es universal: funciona para CUALQUIER cliente que tenga el mismo formato de análisis.
"""
import sys, os

# Resolución dinámica de ruta del proyecto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import xlrd
import re
from datetime import datetime, date
from database import SessionLocal, DgiiIt1, AjustesFiscales

# ===========================================================
# MAPEO DE SERIAL DE EXCEL A FECHA YYYYMM
# ===========================================================

def serial_excel_a_fecha(serial):
    """Convierte el serial numérico de Excel (ej: 45658) a mes YYYY-MM."""
    try:
        if serial == 0 or serial == "":
            return None
        # Excel cuenta días desde 1900-01-01 (con bug del año bisiesto 1900)
        dt = xlrd.xldate_as_datetime(float(serial), 0)
        return dt.strftime("%Y-%m")
    except Exception:
        return None

# ===========================================================
# EXTRACTOR DE DATOS MENSUALES IT-1
# ===========================================================

def extraer_it1_mensual(hoja, rnc_empresa, anio):
    """
    Extrae los datos mensuales del IT-1 desde la hoja del año.
    Estructura detectada en ANALISIS 2025.xls de Elvira:
      Col 1: Mes (serial Excel)
      Col 2: Total Ventas
      Col 3: Ventas Exentas
      Col 4: Ventas Grabadas
      Col 5: ITBIS Ventas (cobrado)
      Col 6: Adelantos ITBIS Compras locales
      Col 7: Adelantos ITBIS Importaciones
      Col 8: ITBIS a Pagar (resultado)
    """
    registros = []

    for r in range(hoja.nrows):
        row = hoja.row_values(r)

        # Detectar filas de datos: col[1] es serial Excel de fecha (número > 40000)
        col_mes = row[1] if len(row) > 1 else ""
        if not isinstance(col_mes, float) or col_mes < 40000 or col_mes > 50000:
            continue

        mes = serial_excel_a_fecha(col_mes)
        if not mes or not mes.startswith(str(anio)):
            continue

        total_ventas     = float(row[2]) if len(row) > 2 and row[2] else 0.0
        ventas_exentas   = float(row[3]) if len(row) > 3 and row[3] else 0.0
        ventas_grabadas  = float(row[4]) if len(row) > 4 and row[4] else 0.0
        itbis_cobrado    = float(row[5]) if len(row) > 5 and row[5] else 0.0
        adel_compras     = float(row[6]) if len(row) > 6 and row[6] else 0.0
        adel_import      = float(row[7]) if len(row) > 7 and row[7] else 0.0
        itbis_pagar      = float(row[8]) if len(row) > 8 and row[8] else 0.0

        itbis_deducible  = adel_compras + adel_import
        saldo_favor      = (-itbis_pagar) if itbis_pagar < 0 else 0.0

        registros.append({
            "mes": mes,
            "rnc_empresa": rnc_empresa,
            "ventas": total_ventas,
            "itbis_cobrado": itbis_cobrado,
            "itbis_deducible": itbis_deducible,
            "saldo_itbis": itbis_pagar
        })

        print(f"  [IT1] {mes}: Ventas={total_ventas:>14,.2f} | ITBIS={itbis_cobrado:>12,.2f} | Adel.={itbis_deducible:>12,.2f} | Pagar={itbis_pagar:>12,.2f}")

    return registros

# ===========================================================
# EXTRACTOR DE ANTICIPOS IR-2
# ===========================================================

def extraer_anticipos(hoja, rnc_empresa, anio):
    """
    Extrae la tabla de anticipos pagados del IR-2.
    Estructura detectada en Elvira:
      Col 1: NCF del pago
      Col 2: Período cubierto (YYYYMM)
      Col 3: NCF referencia empresa
      Col 4: Literal 'Declaracion'
      Col 5: Literal 'I12'
      Col 6: Estado ('Declarado')
      Col 7: Fecha de pago (serial Excel)
      Col 8: Monto del anticipo
    """
    anticipos = []
    total_anticipos = 0.0

    for r in range(hoja.nrows):
        row = hoja.row_values(r)

        # Detectar filas de anticipos: col[4] == 'Declaracion'
        if len(row) < 9 or str(row[4]).strip() != "Declaracion":
            continue

        periodo_raw = row[2] if row[2] else ""  # Col 2: período YYYYMM
        monto = float(row[8]) if row[8] else 0.0  # Col 8: monto del pago
        fecha_pago = serial_excel_a_fecha(row[7]) if row[7] else None  # Col 7: fecha

        periodo_str = str(int(periodo_raw)) if periodo_raw else ""
        if len(periodo_str) == 6:
            anio_periodo = int(periodo_str[:4])
            # Incluimos el anticipo de diciembre del año anterior (pagado en enero del año fiscal)
            if anio_periodo in [anio - 1, anio]:
                anticipos.append({
                    "periodo": periodo_str,
                    "monto": monto,
                    "fecha": fecha_pago
                })
                total_anticipos += monto
                print(f"  [ATC] Período {periodo_str}: RD$ {monto:>12,.2f} pagado {fecha_pago or 'N/A'}")

    return anticipos, total_anticipos

# ===========================================================
# INSERCIÓN EN BASE DE DATOS
# ===========================================================

def guardar_it1(registros, db):
    """Inserta o actualiza los registros IT-1 en la BD."""
    insertados = 0
    for r in registros:
        # Eliminar si ya existe para ese mes y reemplazar
        db.query(DgiiIt1).filter_by(rnc_empresa=r["rnc_empresa"], mes=r["mes"]).delete()
        db.add(DgiiIt1(
            rnc_empresa=r["rnc_empresa"],
            mes=r["mes"],
            ventas=r["ventas"],
            itbis_cobrado=r["itbis_cobrado"],
            itbis_deducible=r["itbis_deducible"],
            saldo_itbis=r["saldo_itbis"]
        ))
        insertados += 1
    db.commit()
    return insertados

def actualizar_anticipos_en_ajustes(total_anticipos, rnc, anio, db):
    """Actualiza el campo anticipos_pagados en la tabla ajustes_fiscales."""
    aj = db.query(AjustesFiscales).filter_by(rnc_empresa=rnc, anio_fiscal=anio).first()
    if aj:
        aj.anticipos_pagados = total_anticipos
        isr_bruto = aj.isr_causado
        aj.isr_a_pagar = max(isr_bruto - total_anticipos - aj.retenciones_sufridas, 0)
        db.commit()
        print(f"\n  [BD] Anticipos actualizados: RD$ {total_anticipos:,.2f}")
        print(f"  [BD] ISR a Pagar recalculado: RD$ {aj.isr_a_pagar:,.2f}")
    else:
        print(f"\n  [!] No se encontraron ajustes_fiscales para {rnc}/{anio}. Ejecuta motor_fiscal.py primero.")


# ===========================================================
# PUNTO DE ENTRADA UNIVERSAL (Cualquier cliente)
# ===========================================================

def procesar_analisis(ruta_archivo, rnc_empresa, anio):
    """
    Función principal — funciona para CUALQUIER cliente con el formato estándar.
    Parámetros:
      ruta_archivo: Ruta al Excel de análisis (ej: ANALISIS 2025.xls)
      rnc_empresa:  RNC del cliente (sin guiones)
      anio:         Año fiscal a procesar
    """
    print("=" * 65)
    print(f"  ETL IT-1 + Anticipos: {ruta_archivo}")
    print(f"  RNC: {rnc_empresa} | Año: {anio}")
    print("=" * 65)

    wb = xlrd.open_workbook(ruta_archivo)

    # Detectar la hoja del año (puede llamarse '2025', '2024', etc.)
    nombre_hoja = str(anio)
    if nombre_hoja not in wb.sheet_names():
        # Fallback: tomar la primera hoja
        nombre_hoja = wb.sheet_names()[0]
        print(f"  [i] Hoja '{anio}' no encontrada, usando: {nombre_hoja}")

    hoja = wb.sheet_by_name(nombre_hoja)
    print(f"  [i] Procesando hoja '{nombre_hoja}' ({hoja.nrows} filas)\n")

    # Extraer datos
    print("--- IT-1 MENSUAL ---")
    registros_it1 = extraer_it1_mensual(hoja, rnc_empresa, anio)

    print("\n--- ANTICIPOS IR-2 ---")
    anticipos, total_anticipos = extraer_anticipos(hoja, rnc_empresa, anio)

    # Guardar en BD
    db = SessionLocal()
    try:
        n_it1 = guardar_it1(registros_it1, db)
        actualizar_anticipos_en_ajustes(total_anticipos, rnc_empresa, anio, db)
    finally:
        db.close()

    # Resumen
    total_ventas_it1  = sum(r["ventas"] for r in registros_it1)
    total_itbis_it1   = sum(r["itbis_cobrado"] for r in registros_it1)

    print("\n" + "=" * 65)
    print("  RESUMEN IT-1 EXTRAÍDO:")
    print(f"  Meses procesados:     {len(registros_it1)}")
    print(f"  Total Ventas IT-1:    RD$ {total_ventas_it1:>14,.2f}")
    print(f"  Total ITBIS IT-1:     RD$ {total_itbis_it1:>14,.2f}")
    print(f"  Anticipos pagados:    RD$ {total_anticipos:>14,.2f}  ({len(anticipos)} pagos)")
    print("=" * 65)
    return registros_it1, anticipos, total_anticipos


if __name__ == "__main__":
    # Test con cliente de ejemplo
    procesar_analisis(
        ruta_archivo=os.path.join(BASE_DIR, "data", "clientes", "130826552", "03_Estados_Financieros", "ANALISIS 2025.xls"),
        rnc_empresa="130826552",
        anio=2025
    )
