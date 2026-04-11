"""
etl_cruce_terceros.py — Motor de Cruce de Terceros DGII
=========================================================
Lee los archivos del OFV DGII de cruce de terceros (formato HTML disfrazado de XLS):
  1. Terceros_XXXXXX_YYYY_606.xls  — Lo que los clientes reportaron comprar de nosotros
  2. Terceros_XXXXXX_YYYY_Tarjetas.xls — Ventas pagadas con tarjeta (CARDNET, Scotiabank)

Cruces que genera el sistema:
  - Ventas 607 declaradas vs ventas según terceros -> detecta omisiones
  - ITBIS retenido por tarjetas -> alimenta Casilla 22 del IR-2
  - Top clientes del cruce -> verifica CxC
"""
import sys, os, glob
sys.path.insert(0, r"c:\GEMINI\AiContaFiscalRD\core")

import pandas as pd
from database import SessionLocal
from sqlalchemy import and_

BASE_ELVIRA = r"G:\Mi unidad\Backup NAS (NO TOCAR)\PGA\13 DECLARACION IR-2 2025\IR-2 2025 ELVIRA"

def cargar_cruce_606(directorio):
    """Carga el archivo de ingresos según terceros (cruce 606)."""
    archivos = [f for f in os.listdir(directorio)
                if 'Terceros' in f and '606' in f and f.endswith('.xls')]
    if not archivos:
        print("  [!] No se encontro archivo de Cruce Terceros 606.")
        return None
    ruta = os.path.join(directorio, archivos[0])
    print(f"  -> Leyendo: {archivos[0]}")
    return pd.read_html(ruta)[0]

def cargar_cruce_tarjetas(directorio):
    """Carga el archivo de ventas con tarjetas."""
    archivos = [f for f in os.listdir(directorio)
                if 'Terceros' in f and 'Tarjetas' in f and f.endswith('.xls')]
    if not archivos:
        print("  [!] No se encontro archivo de Cruce Tarjetas.")
        return None
    ruta = os.path.join(directorio, archivos[0])
    print(f"  -> Leyendo: {archivos[0]}")
    return pd.read_html(ruta)[0]

def analizar_cruce(df606, dft, ventas_declaradas, rnc, anio, db):
    """Calcula el cruce completo y actualiza retenciones si aplica."""

    total_terceros = df606['MONTO_FACTURADO'].sum() if df606 is not None else 0
    itbis_terceros = df606['ITBIS_FACTURADO'].sum() if df606 is not None else 0
    total_tarjetas = dft['MONTO_FACTURADO'].sum() if dft is not None else 0
    itbis_retenido_tarj = dft['ITBIS_RETENIDO'].sum() if dft is not None else 0
    total_cruce_combinado = total_terceros + total_tarjetas
    diferencia = ventas_declaradas - total_cruce_combinado

    print("\n" + "=" * 65)
    print("  CRUCE DE VALIDACION DE VENTAS 2025")
    print("=" * 65)
    print(f"  Ventas Declaradas (IT-1 / 607):  RD$ {ventas_declaradas:>14,.2f}")
    print(f"  Segun Terceros (606 DGII):       RD$ {total_terceros:>14,.2f}")
    print(f"  Segun Tarjetas (CARDNET/Banco):  RD$ {total_tarjetas:>14,.2f}")
    print(f"  Suma Terceros + Tarjetas:        RD$ {total_cruce_combinado:>14,.2f}")
    print(f"  Diferencia (Efectivo/No cruce):  RD$ {diferencia:>14,.2f}")

    if diferencia < 0:
        print(f"\n  [!!ALERTA] Los terceros reportan MAS ventas que lo declarado.")
        print(f"             Riesgo de ajuste por parte de la DGII.")
    elif diferencia > 0:
        pct = (diferencia / ventas_declaradas * 100) if ventas_declaradas > 0 else 0
        print(f"\n  [OK] Diferencia: {pct:.1f}% de las ventas no cubierta por el cruce.")
        print(f"       Probable fuente: ventas en efectivo al detalle (normal en carteras).")

    print(f"\n  ITBIS Retenido por Tarjetas:     RD$ {itbis_retenido_tarj:>14,.2f}")

    # Se omitió el guardado en AjustesFiscales porque el Motor Big4 
    # usa EstadoFinanciero centralizado y lo gestiona allí.
    if df606 is not None:
        print("\n  TOP 10 CLIENTES SEGUN DGII (cruce 606):")
        top = df606.groupby('NOMBRE')['MONTO_FACTURADO'].sum().sort_values(ascending=False).head(10)
        for nombre, monto in top.items():
            print(f"    {nombre[:40]:40s} RD$ {monto:>12,.2f}")

    # Por período
    if df606 is not None:
        print("\n  VENTAS POR MES SEGUN TERCEROS:")
        por_mes = df606.groupby('PERIODO')['MONTO_FACTURADO'].sum()
        for periodo, monto in por_mes.items():
            mes = str(int(periodo))
            print(f"    {mes[:4]}-{mes[4:]}:  RD$ {monto:>12,.2f}")

    print("=" * 65)
    return total_terceros, total_tarjetas, itbis_retenido_tarj, diferencia


def procesar_cruce_terceros(directorio, rnc_empresa, anio, ventas_declaradas):
    """Función principal universal."""
    print("=" * 65)
    print(f"  ETL CRUCE DE TERCEROS | RNC: {rnc_empresa} | Año: {anio}")
    print("=" * 65)

    df606 = cargar_cruce_606(directorio)
    dft   = cargar_cruce_tarjetas(directorio)

    db = SessionLocal()
    try:
        resultados = analizar_cruce(df606, dft, ventas_declaradas, rnc_empresa, anio, db)
    finally:
        db.close()

    return resultados


if __name__ == "__main__":
    procesar_cruce_terceros(
        directorio=BASE_ELVIRA,
        rnc_empresa="130826552",
        anio=2025,
        ventas_declaradas=16355367.70  # Total IT-1 real de Elvira
    )
