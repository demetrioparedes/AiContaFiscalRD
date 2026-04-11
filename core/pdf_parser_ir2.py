import os
import re

def extraer_datos_ir2(file_paths: list):
    """
    Intenta leer una lista de PDFs o Excel de un IR-2 / Anexos del año anterior
    y extraer Inventario Final y Retenciones.
    """
    inventario = 0.0
    retenciones = 0.0
    
    for file_path in file_paths:
        ext = file_path.lower()
        if ext.endswith('.pdf'):
            try:
                import PyPDF2
                with open(file_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    text = ""
                    for p in reader.pages:
                        text += p.extract_text() + "\n"
                    
                    m_inv = re.search(r'Inventario\s*Final.*?(\d{1,3}(?:,\d{3})*(?:\.\d{2}))', text, re.IGNORECASE | re.DOTALL)
                    if m_inv:
                        val = float(m_inv.group(1).replace(',',''))
                        if val > inventario: inventario = val
                    
                    m_ret = re.search(r'Retenciones.*?(\d{1,3}(?:,\d{3})*(?:\.\d{2}))', text, re.IGNORECASE | re.DOTALL)
                    if m_ret:
                        val = float(m_ret.group(1).replace(',',''))
                        if val > retenciones: retenciones = val
            except Exception as e:
                print(f"Error parseando PDF {file_path}: {e}")
                
        elif ext.endswith('.xls') or ext.endswith('.xlsx'):
            try:
                import pandas as pd
                df = pd.read_excel(file_path, sheet_name=None, header=None)
                for sheet_name, sheet_df in df.items():
                    for i, row in sheet_df.iterrows():
                        row_str = " ".join([str(x) for x in row.values]).lower()
                        if "inventario" in row_str and "final" in row_str:
                            nums = set(re.findall(r'\d+(?:\.\d+)?', str(row.values)))
                            nums = [float(n) for n in nums if float(n)>0]
                            if nums and max(nums) > inventario: inventario = max(nums)
                        if "retenciones" in row_str and "ley" in row_str:
                            nums = set(re.findall(r'\d+(?:\.\d+)?', str(row.values)))
                            nums = [float(n) for n in nums if float(n)>0]
                            if nums and max(nums) > retenciones: retenciones = max(nums)
            except Exception as e:
                print(f"Error parseando Excel {file_path}: {e}")
                
    # Fallback: No inyectamos valores artificiales para garantizar integridad.
    if inventario == 0.0 and retenciones == 0.0:
        print("[!] Advertencia: No se detectaron valores legibles en los archivos provistos.")

        
    return {
        "status": "success",
        "inventario_final_anterior": inventario,
        "retenciones_saldo_favor": retenciones
    }
