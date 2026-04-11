import os
import json
import re
import pandas as pd
from PyPDF2 import PdfReader

RAW_DIR = r"c:\GEMINI\AiContaFiscalRD\data\raw"
EXTRACTED_DIR = r"c:\GEMINI\AiContaFiscalRD\data\extracted"

# --- UTILIDADES PARA LIMPIAR NÚMEROS ---
def clean_amount(text_val):
    if pd.isna(text_val): return 0.0
    s = str(text_val).strip()
    # Eliminar paréntesis para negativos y signos de moneda
    s = s.replace('RD$', '').replace('$', '').replace(' ', '')
    is_negative = False
    if s.startswith('(') and s.endswith(')'):
        is_negative = True
        s = s[1:-1]
    # Quitar comas de miles y convertir
    s = s.replace(',', '')
    try:
        val = float(s)
        return -val if is_negative else val
    except:
        return 0.0

# --- EXTRACTOR: ANALISIS EN EXCEL ---
def extract_analisis_excel(filepath):
    """Extrae las ventas y costos totales sumando mes a mes del ANALISIS 2025.xls"""
    print(f"  -> Extrayendo análisis contable: {os.path.basename(filepath)}")
    data = {"ingresos": 0.0, "itbis_ventas": 0.0, "compras_locales": 0.0, "importaciones": 0.0, "anticipos_pagados": 0.0, "retenciones_0804": 0.0}
    try:
        engine = 'xlrd' if filepath.endswith('.xls') else 'openpyxl'
        df = pd.read_excel(filepath, engine=engine, sheet_name=0) # Leer primera hoja, omitiendo headers para buscar por indice
        
        # Iterar filas 10 a la 21 (Enero a Diciembre según inspección)
        for idx in range(10, 22):
            if idx < len(df):
                # Columna Unnamed: 4 (Ventas Grabadas)
                data["ingresos"] += clean_amount(df.iloc[idx, 4])
                # Columna Unnamed: 5 (ITBIS en Ventas)
                data["itbis_ventas"] += clean_amount(df.iloc[idx, 5])
                # Columna Unnamed: 6 (Compras)
                data["compras_locales"] += clean_amount(df.iloc[idx, 6])
                # Columna Unnamed: 7 (Importacion)
                data["importaciones"] += clean_amount(df.iloc[idx, 7])
                # Columna Unnamed: 10 (Norma 08-04 - Retenciones)
                data["retenciones_0804"] += clean_amount(df.iloc[idx, 10])

        # Buscar el total de anticipos (suele estar al final, fila 41 col 8)
        # Haremos una búsqueda para ser resilientes si cambia de fila
        for index, row in df.iterrows():
            row_str = str(row.values).lower()
            if "declaracion" in row_str or "i12" in row_str:
                 # buscar en columnas 8 o 9
                 val = clean_amount(row.get(8))
                 if val > 0: data["anticipos_pagados"] += val
                 val2 = clean_amount(row.get(9))
                 if val2 > 0: data["anticipos_pagados"] += val2
                 
    except Exception as e:
        print(f"Error en {os.path.basename(filepath)}: {e}")
    return data

# --- EXTRACTOR: ANEXOS ANTERIORES (PDF) ---
def extract_anexo_pdf(filepath):
    """Extrae datos de inventario e ingresos reportados en Anexos del año previo"""
    filename = os.path.basename(filepath).upper()
    print(f"  -> Extrayendo datos del Anexo previo: {filename}")
    data = {}
    try:
        reader = PdfReader(filepath)
        text = " ".join([page.extract_text() for page in reader.pages])
        
        # Extraer según el tipo de anexo en el nombre del archivo
        if "ANEXO A" in filename:
            # Buscar ingresos
            match_ing = re.search(r"Ingresos por Operaciones[\D]+([\d\,\.]+)", text)
            if match_ing: data["ingresos_operaciones_previo"] = clean_amount(match_ing.group(1))
            
            # Buscar inventario inicial (que luego será usado como inicial del año que sigue)
            match_inv_final = re.search(r"Inventario Final[\D]+([\d\,\.]+)", text)
            if match_inv_final: data["inventario_final_previo"] = clean_amount(match_inv_final.group(1))
            
        elif "ANEXO B" in filename:
            match_res = re.search(r"Resultado del Ejercicio[\D]+([\d\,\.]+)", text)
            if match_res: data["resultado_fiscal_previo"] = clean_amount(match_res.group(1))
            
        elif "ANEXO D" in filename: # Inventario
            match_inv = re.search(r"Inventario Final[\D]+([\d\,\.]+)", text)
            if match_inv: data["inventario_final_anexod"] = clean_amount(match_inv.group(1))

    except Exception as e:
         print(f"Error en {filename}: {e}")
    return data

# --- EXTRACTOR: FORMULARIOS DGII (606 / IT-1) ---
def extract_dgii_forms(filepath):
    """Extrae el total de ITBIS y Gastos de acuses de la DGII"""
    print(f"  -> Extrayendo formato DGII: {os.path.basename(filepath)}")
    data = {}
    try:
        reader = PdfReader(filepath)
        text = "".join([page.extract_text() for page in reader.pages]).lower()
        
        if "606" in os.path.basename(filepath).lower():
            # Buscar totales en el texto
            match = re.search(r"monto[\s\w]+ncf[\s\n]*totales:[\s]*([\d\,\.]+)", text)
            if match: data["compras_reportadas_606"] = clean_amount(match.group(1))
            
        elif "itbis" in os.path.basename(filepath).lower():
            # Total de operaciones (Casilla 1 IT-1 usualmente)
            match = re.search(r"total de operaciones[\s]*([\,\d\.]+)", text)
            if match: data["operaciones_reportadas_itbis"] = clean_amount(match.group(1))
            
    except Exception as e:
        print(f"Error en {os.path.basename(filepath)}: {e}")
    return data

import uuid
from datetime import datetime

# --- UTILIDADES PARA JSON ---
def create_dato_extraido(tipo_dato, valor, descripcion, fuente, periodo="2025", is_conflicto=False):
    """Fábrica de objetos que cumplen con el esquema de la BD del usuario"""
    return {
        "empresa_id": "EMP-001", # Placeholder
        "archivo_id": f"FILE-{uuid.uuid4().hex[:8].upper()}",
        "tipo_dato": tipo_dato,
        "descripcion": descripcion,
        "valor": valor,
        "periodo": periodo,
        "fuente": fuente,
        "confirmado": False,
        "conflicto": is_conflicto
    }

# --- EXTRACTOR: ANALISIS EN EXCEL ---
def extract_analisis_excel(filepath):
    print(f"  -> Extrayendo análisis contable: {os.path.basename(filepath)}")
    datos = []
    try:
        engine = 'xlrd' if filepath.endswith('.xls') else 'openpyxl'
        df = pd.read_excel(filepath, engine=engine, sheet_name=0)
        
        ingresos, itbis_ventas, compras, importaciones, anticipos, retenciones_0804 = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        
        for idx in range(10, 22):
            if idx < len(df):
                ingresos += clean_amount(df.iloc[idx, 4])
                itbis_ventas += clean_amount(df.iloc[idx, 5])
                compras += clean_amount(df.iloc[idx, 6])
                importaciones += clean_amount(df.iloc[idx, 7])
                retenciones_0804 += clean_amount(df.iloc[idx, 10])

        for index, row in df.iterrows():
            row_str = str(row.values).lower()
            if "declaracion" in row_str or "i12" in row_str:
                 val = clean_amount(row.get(8))
                 if val > 0: anticipos += val
                 val2 = clean_amount(row.get(9))
                 if val2 > 0: anticipos += val2
                 
        # Mapeando al nuevo esquema de base de datos
        datos.append(create_dato_extraido("ventas_gravadas", ingresos, "Total Ventas Grabadas (Análisis)", os.path.basename(filepath)))
        datos.append(create_dato_extraido("itbis_cobrado", itbis_ventas, "Total ITBIS en Ventas", os.path.basename(filepath)))
        datos.append(create_dato_extraido("compras_gravadas", compras, "Compras Locales (Contabilidad)", os.path.basename(filepath)))
        datos.append(create_dato_extraido("anticipos_isr", anticipos, "Total Anticipos Pagados", os.path.basename(filepath)))
        datos.append(create_dato_extraido("retenciones_sufridas", retenciones_0804, "Retenciones Norma 08-04", os.path.basename(filepath)))
        
    except Exception as e:
        print(f"Error en {os.path.basename(filepath)}: {e}")
    return datos

# --- EXTRACTOR: ANEXOS ANTERIORES (PDF) ---
def extract_anexo_pdf(filepath):
    filename = os.path.basename(filepath).upper()
    print(f"  -> Extrayendo Anexo previo: {filename}")
    datos = []
    try:
        reader = PdfReader(filepath)
        text = " ".join([page.extract_text() for page in reader.pages])
        
        if "ANEXO B" in filename:
            match_res = re.search(r"Resultado del Ejercicio[\D]+([\d\,\.]+)", text)
            if match_res: 
                val = clean_amount(match_res.group(1))
                datos.append(create_dato_extraido("otro", val, "Resultado Fiscal Anterior", os.path.basename(filepath), "2024"))
                
        elif "ANEXO D" in filename: # Inventario
            match_inv = re.search(r"Inventario Final[\D]+([\d\,\.]+)", text)
            if match_inv: 
                val = clean_amount(match_inv.group(1))
                datos.append(create_dato_extraido("inventario_final", val, "Inventario Final Año Anterior (Inicial Actual)", os.path.basename(filepath), "2024"))

    except Exception as e:
         print(f"Error en {filename}: {e}")
    return datos

# --- EXTRACTOR: FORMULARIOS DGII (606 / IT-1) ---
def extract_dgii_forms(filepath):
    print(f"  -> Extrayendo reporte DGII: {os.path.basename(filepath)}")
    datos = []
    try:
        reader = PdfReader(filepath)
        text = "".join([page.extract_text() for page in reader.pages]).lower()
        
        if "606" in os.path.basename(filepath).lower():
            match = re.search(r"monto[\s\w]+ncf[\s\n]*totales:[\s]*([\d\,\.]+)", text)
            if match:
                val = clean_amount(match.group(1))
                # Creamos el dato, el validador cruzado le pondrá conflicto si no cuadra
                datos.append(create_dato_extraido("compras_gravadas", val, "Compras Reportadas en 606 (Acuses)", os.path.basename(filepath)))
            
    except Exception as e:
        print(f"Error en {os.path.basename(filepath)}: {e}")
    return datos

# --- ORQUESTADOR PRINCIPAL ---
def main():
    print("Iniciando Extractor Universal (Generador esquema BD)...")
    
    database_payload = {
        "archivos_fuente_detectados": [],
        "datos_extraidos": []
    }
    
    for filename in os.listdir(RAW_DIR):
        filepath = os.path.join(RAW_DIR, filename)
        if not os.path.isfile(filepath): continue
        lower_name = filename.lower()
        
        # Registrar el archivo en nuestra pseudo-BD
        database_payload["archivos_fuente_detectados"].append({
            "empresa_id": "EMP-001",
            "nombre_archivo": filename,
            "estado_extraccion": "procesando"
        })
        
        # Ejecutar lógica Mapeadora
        extracciones = []
        if "analisis" in lower_name and filepath.endswith((".xls", ".xlsx")):
            extracciones = extract_analisis_excel(filepath)
        elif "anexo" in lower_name and lower_name.endswith(".pdf") and "itbis" not in lower_name:
            extracciones = extract_anexo_pdf(filepath)
        elif "606" in lower_name or "itbis" in lower_name:
            extracciones = extract_dgii_forms(filepath)
            
        database_payload["datos_extraidos"].extend(extracciones)

    # El Auditor: Evaluar Conflictos 
    # Mapear todos los 'compras_gravadas'
    compras_list = [d for d in database_payload["datos_extraidos"] if d["tipo_dato"] == "compras_gravadas"]
    if len(compras_list) > 1:
        # Existe más de una fuente de compras, marcar ambos como conflicto para la UI de React
        for c in compras_list:
            c["conflicto"] = True
            c["descripcion"] = f"[CONFLICTO DETECTADO] {c['descripcion']}"

    # Output JSON estandarizado para la API
    output_path = os.path.join(EXTRACTED_DIR, "db_payload_export.json")
    with open(output_path, "w", encoding='utf-8') as f:
        json.dump(database_payload, f, indent=4, ensure_ascii=False)
        
    print(f"\n[OK] Extracción Homogeneizada de {len(database_payload['datos_extraidos'])} datos completada.")
    print(f"Archivo listo para insertar en BBDD React: {output_path}")

if __name__ == "__main__":
    main()
