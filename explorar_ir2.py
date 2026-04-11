import pandas as pd
import sys

try:
    file_path = r"c:\GEMINI\AiContaFiscalRD\data\raw\IR-2-2018.xls"
    
    # xlrd is often required for older .xls files
    try:
        xls = pd.ExcelFile(file_path, engine='xlrd')
    except Exception as e:
        print(f"Error con xlrd, intentando sin engine: {e}")
        xls = pd.ExcelFile(file_path)
    
    print("=== HOJAS DISPONIBLES EN EL IR-2 ===")
    for sheet_name in xls.sheet_names:
        print(f"- {sheet_name}")
        
    print("\n=== MUESTRA DE LA PRIMERA HOJA (Primeras 10 filas) ===")
    df = pd.read_excel(file_path, sheet_name=xls.sheet_names[0], engine='xlrd' if 'xlrd' in sys.modules else None)
    print(df.head(10))

except Exception as e:
    print(f"Error procesando el archivo: {e}")
