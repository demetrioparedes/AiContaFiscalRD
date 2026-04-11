import os
import json
import re
import pandas as pd
from PyPDF2 import PdfReader

# --- Configuración ---
RAW_DIR = r"c:\GEMINI\AiContaFiscalRD\data\raw"
EXTRACTED_DIR = r"c:\GEMINI\AiContaFiscalRD\data\extracted"

# --- Funciones de Extracción ---

def extract_from_excel(filepath):
    """Extrae datos de archivos Excel como los Análisis o IR-13."""
    data = {}
    try:
        # xlrd is required for .xls
        engine = 'xlrd' if filepath.endswith('.xls') else 'openpyxl'
        df = pd.read_excel(filepath, engine=engine)
        # Buscar palabras clave en las celdas (simplificado por ahora)
        text_content = df.to_string()
        
        if "ITBIS" in text_content or "606" in text_content:
            data['tipo_excel'] = "Itbis/Compras"
            
        data['raw_preview'] = df.head(5).to_dict()
    except Exception as e:
        data['error'] = str(e)
    return data

def extract_from_pdf(filepath):
    """Extrae texto de archivos PDF (Anexos anteriores, acuses 606)."""
    data = {}
    try:
        reader = PdfReader(filepath)
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() + "\n"
        
        # Identificar tipo de documento
        lower_text = full_text.lower()
        if "anexo a" in lower_text:
            data['tipo_doc'] = "IR-2 Anexo A"
            # Ejemplo de Regex para buscar casillas (depende del formato exacto del texto)
            # Buscar algo como "Ingresos por Operaciones... 1,000,000.00"
            ingresos_match = re.search(r"ingresos[\s\w]*operaciones[\.\s]*([\d,\.]+)", lower_text)
            if ingresos_match:
                data['ingresos_operaciones'] = ingresos_match.group(1).strip()
                
        elif "formato 606" in lower_text:
            data['tipo_doc'] = "Formato 606"
        else:
            data['tipo_doc'] = "Otro PDF"
            
        data['text_preview'] = full_text[:500] # Primeros 500 caracteres
    except Exception as e:
        data['error'] = str(e)
    return data

# --- Orquestador Principal de Ingesta ---

def main():
    print("Iniciando Ingesta de Datos (El Archivista)...")
    consolidated_data = {}
    
    for filename in os.listdir(RAW_DIR):
        filepath = os.path.join(RAW_DIR, filename)
        
        if not os.path.isfile(filepath) or filename.endswith('.md'):
            continue
            
        print(f"Procesando: {filename}")
        
        if filename.endswith(('.xls', '.xlsx')):
            result = extract_from_excel(filepath)
            consolidated_data[filename] = result
        elif filename.endswith('.pdf'):
            result = extract_from_pdf(filepath)
            consolidated_data[filename] = result
        else:
            print(f"Ignorando formato no soportado: {filename}")
            
    # Guardar resultados
    output_path = os.path.join(EXTRACTED_DIR, "extraccion_inicial.json")
    with open(output_path, "w", encoding='utf-8') as f:
        json.dump(consolidated_data, f, indent=4, ensure_ascii=False)
        
    print(f"\nExtracción completada. Resultados en: {output_path}")

if __name__ == "__main__":
    main()
