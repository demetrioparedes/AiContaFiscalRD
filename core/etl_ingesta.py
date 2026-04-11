"""
etl_ingesta.py — Módulo 0: Data Cleansing + Normalización (SaaS Big4)
========================================================================
Lee archivos del 606 y 607 de la DGII (TXT, CSV, Excel)
y los carga en la nueva base de datos SQL de producción.
"""
import re
import os
import sys
import pandas as pd
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from datetime import datetime
from database import SessionLocal, Empresa, Dgii606, Dgii607, ClasificacionFiscal
from motor_clasificacion import clasificar_factura_ia
try:
    from etl_it1 import cargar_it1_csv
except ImportError:
    cargar_it1_csv = None

# ===========================================================
# UTILIDADES DE NORMALIZACIÓN
# ===========================================================

def normalizar_rnc(rnc_raw):
    if pd.isna(rnc_raw) or str(rnc_raw).strip() == "": return None
    rnc = re.sub(r"[^0-9]", "", str(rnc_raw))
    if len(rnc) < 8 or len(rnc) > 11: return None
    return rnc

def parsear_ncf(ncf_raw):
    if pd.isna(ncf_raw) or str(ncf_raw).strip() == "": return None, None
    ncf = re.sub(r"[^A-Z0-9]", "", str(ncf_raw).upper())
    match = re.match(r"^([A-Z]\d{2})(\d+)$", ncf)
    if match: return match.group(1), match.group(2)
    return None, None

def limpiar_monto(valor) -> Decimal:
    """
    Convierte cualquier valor monetario a Decimal con 2 decimales.
    Usa ROUND_HALF_UP — el mismo criterio que usa la DGII.
    NUNCA usa float para valores fiscales.
    """
    try:
        # Limpia el string: quita comas, espacios, y caracteres raros
        limpio = str(valor).replace(",", "").replace(" ", "").strip()
        
        # Cadena vacía o nula → cero exacto
        if not limpio or limpio in ("", "None", "nan", "NULL"):
            return Decimal("0.00")
        
        # Conversión segura: pasar por string evita errores de float binario
        return Decimal(limpio).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    except InvalidOperation:
        # Si el valor es basura (letras, símbolos), devuelve cero y no explota
        return Decimal("0.00")

def normalizar_fecha(fecha_raw):
    if pd.isna(fecha_raw) or str(fecha_raw).strip() == "": return None
    fecha_str = str(fecha_raw).strip()
    formatos = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y%m", "%Y-%m", "%Y%m%d"]
    for fmt in formatos:
        try:
            return datetime.strptime(fecha_str, fmt).date()
        except ValueError:
            continue
    return None

def detectar_periodo(fecha_date):
    if fecha_date:
        return fecha_date.strftime("%Y%m")
    return datetime.now().strftime("%Y%m")

# ===========================================================
# MAPEO FLEXIBLE DE COLUMNAS (diferentes versiones DGII)
# ===========================================================

COLUMNAS_606 = {
    "rnc_proveedor":  ["RNC Proveedor", "rnc_proveedor", "RNC/Cédula", "RNC"],
    "ncf":            ["NCF", "ncf", "Número Comprobante", "No. Comprobante"],
    "fecha":          ["Fecha", "fecha", "Fecha NCF", "FECHA"],
    "monto":          ["Monto Facturado", "monto_facturado", "Valor", "MONTO"],
    "itbis":          ["ITBIS", "itbis", "ITBIS Facturado", "Monto ITBIS"],
    "tipo_bien":      ["Tipo Bien", "tipo_bien", "Tipo de Bien/Servicio"],
    "nombre_proveedor": ["Nombre", "nombre", "Razón Social", "Razon Social", "Razon", "Nombre Empresa"]
}

COLUMNAS_607 = {
    "rnc_cliente":    ["RNC Cliente", "rnc_cliente", "RNC/Cédula Cliente"],
    "ncf":            ["NCF", "ncf", "Número Comprobante"],
    "fecha":          ["Fecha", "fecha", "Fecha NCF"],
    "monto":          ["Monto Facturado", "monto_facturado", "Valor"],
    "itbis":          ["ITBIS Facturado", "itbis_facturado", "ITBIS"],
    "monto_exento":   ["Monto Exento", "monto_exento"],
    "retencion_isr":  ["Retención ISR", "retencion_isr"],
    "retencion_itbis":["Retención ITBIS", "retencion_itbis"],
}

def resolver_columna(df, candidatos):
    for candidato in candidatos:
        if candidato in df.columns: return candidato
    return None

# ===========================================================
# MOTOR DE CLASIFICACIÓN
# ===========================================================

def asignar_cuenta_contable(tipo_ncf, db):
    regla = db.query(ClasificacionFiscal).filter_by(tipo_ncf=tipo_ncf).first()
    return regla.cuenta_contable if regla else "sin_clasificar"

# ===========================================================
# CARGADORES POR TIPO DE ARCHIVO
# ===========================================================

def cargar_606(ruta_archivo, empresa_id, anio_requerido, db):
    print(f"  [606] Analizando: {os.path.basename(ruta_archivo)}")
    ext = os.path.splitext(ruta_archivo)[1].lower()
    df = None
    es_txt = False

    if ext in [".txt", ".csv"]:
        try:
            with open(ruta_archivo, 'r', encoding='latin1') as f:
                primera_linea = f.readline()
            sep = '|' if '|' in primera_linea else ','
            
            # Si es pipeline asumo que NO tiene header (formato DGII TXT oficial)
            if sep == '|':
                df_raw = pd.read_csv(ruta_archivo, sep=sep, encoding='latin1', header=None, dtype=str, skiprows=1)
                # Forzar un pseudo-header para que el loop de abajo no rompa
                # Posiciones: 0:RNC, 3:NCF, 5:Fecha, 7:Servicios, 8:Bienes, 10:ITBIS, 2:TipoBien
                df_raw.rename(columns={0: "RNC Proveedor", 3: "NCF", 5: "Fecha", 7: "Monto Serv", 8: "Monto Bienes", 10: "ITBIS", 2: "Tipo Bien"}, inplace=True)
                # Combinar monto facturado
                df_raw["Monto Facturado"] = pd.to_numeric(df_raw["Monto Serv"].fillna(0), errors='coerce').fillna(0) + pd.to_numeric(df_raw["Monto Bienes"].fillna(0), errors='coerce').fillna(0)
                df = df_raw
            else:
                # Es un CSV normal con headers (Elvira style)
                df = pd.read_csv(ruta_archivo, sep=sep, encoding='latin1', dtype=str)
        except Exception as e:
            print(f"  [!] Error leyendo CSV/TXT: {e}")
            return 0
        
    elif ext in [".xls", ".xlsx"]:
        try:
            df_raw = pd.read_excel(ruta_archivo, dtype=str, header=None)
            idx_header = -1
            for i in range(min(20, len(df_raw))):
                if any("NCF" in str(x).upper() for x in df_raw.iloc[i].values):
                    idx_header = i; break
            if idx_header >= 0:
                df = df_raw.iloc[idx_header+1:].copy()
                df.columns = df_raw.iloc[idx_header].values
            else: df = df_raw
        except Exception as e:
            if "BOF" in str(e) or "style" in str(e).lower() or "html" in str(e).lower():
                df = pd.read_html(ruta_archivo)[0].astype(str)
            else: return 0

    if df is None or df.empty: return 0
    insertados = 0; errores = 0

    for _, row in df.iterrows():
        rnc_raw   = row.get(resolver_columna(df, COLUMNAS_606["rnc_proveedor"]))
        ncf_raw   = row.get(resolver_columna(df, COLUMNAS_606["ncf"]))
        fecha_raw = row.get(resolver_columna(df, COLUMNAS_606["fecha"]))
        monto_raw = row.get(resolver_columna(df, COLUMNAS_606["monto"]))
        itbis_raw = row.get(resolver_columna(df, COLUMNAS_606["itbis"]))
        tbien_raw = row.get(resolver_columna(df, COLUMNAS_606["tipo_bien"]))
        nombre_prv= row.get(resolver_columna(df, COLUMNAS_606["nombre_proveedor"])) if resolver_columna(df, COLUMNAS_606["nombre_proveedor"]) else ""

        tipo_ncf, secuencia = parsear_ncf(ncf_raw)
        rnc = normalizar_rnc(rnc_raw)
        fecha_obj = normalizar_fecha(fecha_raw)
        monto = limpiar_monto(monto_raw)
        itbis = limpiar_monto(itbis_raw)

        # DGII Nota: Las Notas de Crédito (B04, E34) ingresan positivas en TXT pero fungen como reversos.
        anulada = 1 if (monto < 0 or tipo_ncf in ["B04", "E34"]) else 0
        if anulada:
            monto = abs(monto)
            itbis = abs(itbis)

        if not tipo_ncf or not rnc:
            errores += 1; continue

        periodo = detectar_periodo(fecha_obj)
        if anio_requerido and not periodo.startswith(str(anio_requerido)):
            errores += 1; continue # Filtro paramétrico por año
        
        try: tipo_bien_int = int(tbien_raw)
        except: tipo_bien_int = 0

        # Llama a la Inteligencia Artificial (Motor 1)
        clasificacion_ia = clasificar_factura_ia(nombre_prv, tipo_bien_int)
        cuenta = clasificacion_ia["cuenta_contable"]

        registro = Dgii606(
            empresa_id=empresa_id, rnc_proveedor=rnc,
            ncf=f"{tipo_ncf}{secuencia}",
            fecha_comprobante=fecha_obj, periodo=periodo, monto_facturado=monto, 
            itbis_facturado=itbis, tipo_bien_servicio=tipo_bien_int, 
            anulada=anulada, cuenta_contable=cuenta
        )
        db.add(registro)
        insertados += 1

    db.commit()
    print(f"    [OK] Insertados: {insertados} | Invalidos/Saltados: {errores}")
    return insertados

def cargar_607(ruta_archivo, empresa_id, anio_requerido, db):
    print(f"  [607] Analizando: {os.path.basename(ruta_archivo)}")
    ext = os.path.splitext(ruta_archivo)[1].lower()
    df = None
    es_txt = False

    if ext in [".txt", ".csv"]:
        try:
            with open(ruta_archivo, 'r', encoding='latin1') as f:
                primera_linea = f.readline()
            sep = '|' if '|' in primera_linea else ','
            
            if sep == '|':
                df_raw = pd.read_csv(ruta_archivo, sep=sep, encoding='latin1', header=None, dtype=str, skiprows=1)
                # Posiciones TXT 607: 0:RNC, 2:NCF, 5:Fecha, 7:Monto, 8:ITBIS, 10:RetISR, 11:RetITBIS
                df_raw.rename(columns={0: "RNC Cliente", 2: "NCF", 5: "Fecha", 7: "Monto Facturado", 8: "ITBIS Facturado", 10: "Retención ISR", 11: "Retención ITBIS"}, inplace=True)
                df = df_raw
            else:
                df = pd.read_csv(ruta_archivo, sep=sep, encoding='latin1', dtype=str)
        except Exception as e:
            print(f"  [!] Error leyendo CSV/TXT: {e}")
            return 0
        
    elif ext in [".xls", ".xlsx"]:
        try:
            df_raw = pd.read_excel(ruta_archivo, dtype=str, header=None)
            idx_header = -1
            for i in range(min(20, len(df_raw))):
                if any("NCF" in str(x).upper() for x in df_raw.iloc[i].values):
                    idx_header = i; break
            if idx_header >= 0:
                df = df_raw.iloc[idx_header+1:].copy()
                df.columns = df_raw.iloc[idx_header].values
            else: df = df_raw
        except Exception as e:
            if "BOF" in str(e) or "style" in str(e).lower() or "html" in str(e).lower():
                df = pd.read_html(ruta_archivo)[0].astype(str)
            else: return 0

    if df is None or df.empty: return 0
    insertados = 0; errores = 0

    for _, row in df.iterrows():
        rnc_cli_raw = row.get(resolver_columna(df, COLUMNAS_607["rnc_cliente"]))
        ncf_raw     = row.get(resolver_columna(df, COLUMNAS_607["ncf"]))
        fecha_raw   = row.get(resolver_columna(df, COLUMNAS_607["fecha"]))
        monto_raw   = row.get(resolver_columna(df, COLUMNAS_607["monto"]))
        itbis_raw   = row.get(resolver_columna(df, COLUMNAS_607["itbis"]))
        exento_raw  = row.get(resolver_columna(df, COLUMNAS_607["monto_exento"]))
        ret_isr_raw = row.get(resolver_columna(df, COLUMNAS_607["retencion_isr"]))
        ret_itb_raw = row.get(resolver_columna(df, COLUMNAS_607["retencion_itbis"]))

        tipo_ncf, secuencia = parsear_ncf(ncf_raw)
        rnc_cli = normalizar_rnc(rnc_cli_raw)
        fecha_obj = normalizar_fecha(fecha_raw)
        monto = limpiar_monto(monto_raw)
        
        # Manejo de NCF Anulados o Notas de Crédito
        anulada = 1 if (monto < 0 or tipo_ncf in ["B04", "E34"]) else 0
        if anulada: monto = abs(monto)

        if not tipo_ncf:
            errores += 1; continue

        periodo = detectar_periodo(fecha_obj)
        if anio_requerido and not periodo.startswith(str(anio_requerido)):
            errores += 1; continue # Filtrado estricto por periodo
        
        registro = Dgii607(
            empresa_id=empresa_id, rnc_cliente=rnc_cli,
            ncf=f"{tipo_ncf}{secuencia}",
            fecha_comprobante=fecha_obj, periodo=periodo, monto_facturado=monto, 
            itbis_facturado=itbis, monto_exento=limpiar_monto(exento_raw), 
            retencion_isr=limpiar_monto(ret_isr_raw), 
            anulada=anulada
        )
        db.add(registro)
        insertados += 1

    db.commit()
    print(f"    [OK] Insertados: {insertados} | Invalidos/Saltados: {errores}")
    return insertados

# ===========================================================
# PUNTO DE ENTRADA PRINCIPAL (MULTI-TENANT SAAS)
# ===========================================================

def ejecutar_etl(directorio_empresa: str, rnc_empresa: str, anio_requerido: int):
    print("=" * 60)
    print("  AiContaFiscalRD — MOTOR ETL (Arquitectura Big4)")
    print("=" * 60)
    print(f"  Ingestando Carpeta: {directorio_empresa} | Periodo: {anio_requerido}\n")

    db = SessionLocal()
    
    # Garantizar Empresa Multi-Tenant
    empresa = db.query(Empresa).filter_by(rnc=rnc_empresa).first()
    if not empresa:
        print(f"  [i] Registrando nueva Empresa SaaS (RNC: {rnc_empresa})")
        empresa = Empresa(rnc=rnc_empresa, nombre_empresa=f"Cliente {rnc_empresa}")
        db.add(empresa)
        db.commit()
        db.refresh(empresa)
    
    # Explorar recursivamente las carpetas del Expediente Digital
    archivos_pendientes = []
    for root, d_names, f_names in os.walk(directorio_empresa):
        for f in f_names:
            archivos_pendientes.append(os.path.join(root, f))
            
    cargados_606 = 0
    cargados_607 = 0
    cargados_it1 = 0

    for ruta in archivos_pendientes:
        nombre = os.path.basename(ruta).upper()
        if nombre.startswith("IT1_") or nombre.startswith("IT-1_"):
            if cargar_it1_csv:
                try: cargados_it1 += cargar_it1_csv(ruta, empresa.id, db)
                except Exception as e: print(f"  [X] Falla IT-1 {nombre}: {e}")
        elif "606" in nombre:
            try: cargados_606 += cargar_606(ruta, empresa.id, anio_requerido, db)
            except Exception as e: print(f"  [X] Falla 606 {nombre}: {e}")
        elif "607" in nombre:
            try: cargados_607 += cargar_607(ruta, empresa.id, anio_requerido, db)
            except Exception as e: print(f"  [X] Falla 607 {nombre}: {e}")
    db.close()
    print("\n" + "=" * 60)
    print(f"  RESUMEN FINAL ETL (Empresa ID {empresa.id}):")
    print(f"  - Registros DGII 606 insertados: {cargados_606}")
    print(f"  - Registros DGII 607 insertados: {cargados_607}")
    print(f"  - Declaraciones IT-1 cargadas:   {cargados_it1}")
    print("=" * 60)

if __name__ == "__main__":
    # Test de sanidad — corre con: python core/etl_ingesta.py
    casos = [
        ("4474.43",   "4474.43"),
        ("800.57",    "800.57"),
        ("1,270.62",  "1270.62"),   # con coma de miles
        ("7764.9",    "7764.90"),   # sin segundo decimal
        ("",          "0.00"),      # vacío
        ("None",      "0.00"),      # nulo
        ("abc",       "0.00"),      # basura
        ("0.005",     "0.01"),      # prueba ROUND_HALF_UP
        ("0.004",     "0.00"),      # prueba ROUND_HALF_UP
    ]
    print("\n=== TEST limpiar_monto() ===")
    todos_ok = True
    for entrada, esperado in casos:
        resultado = str(limpiar_monto(entrada))
        estado = "OK" if resultado == esperado else "FALLO"
        if estado == "FALLO":
            todos_ok = False
        print(f"  {estado}  entrada={repr(entrada):<12} esperado={esperado:<10} obtenido={resultado}")
    
    print(f"\n{'TODOS LOS CASOS PASAN' if todos_ok else '*** HAY FALLOS — REVISAR ***'}\n")
