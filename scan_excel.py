import pandas as pd
import warnings
import os
warnings.filterwarnings('ignore')

ruta = r'C:\Users\pgaco\OneDrive\Desktop\FilePGA\Backup NAS (NO TOCAR)\PGA\12 DECLARACION IR-2 2024\IR-2 2024 ELVIRA\IR-2  2024 ELVIRA CARTERA.xlsx'
xl = pd.ExcelFile(ruta)
print('Hojas:', xl.sheet_names)
print()

for hoja in xl.sheet_names:
    df = pd.read_excel(ruta, sheet_name=hoja, header=None)
    texto = ' '.join([str(v) for v in df.values.flatten()])
    encontrado = '202401' in texto or '202402' in texto or 'ITBIS' in texto.upper()
    if encontrado:
        nombre_out = f'debug_{hoja.replace("/","-").replace(" ","_")}.txt'
        out_path = os.path.join('C:/GEMINI/AiContaFiscalRD', nombre_out)
        with open(out_path, 'w', encoding='utf-8') as f:
            for i in range(len(df)):
                row = df.iloc[i]
                vals = [str(v).strip() for v in row.tolist()]
                f.write(f'F{i:02d}: {vals}\n')
        print(f'>>> Guardado: {nombre_out} ({df.shape})')

print('Escaneo completo.')
