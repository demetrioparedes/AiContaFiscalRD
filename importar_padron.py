import sys
import os
import pandas as pd
from sqlalchemy import create_engine
import time

# Script para importar padrón de RNC de forma masiva y eficiente
def importar_padron(archivo_csv, engine_url):
    print("=====================================================")
    print("   MOTOR DE INGESTA MASIVA: Padrón Contribuyentes")
    print("=====================================================")
    
    print(f"[*] Leyendo archivo CSV: {archivo_csv}")
    start_time = time.time()
    
    # Leer el CSV con Pandas, usando chunks por si la memoria es limitada, aunque 112MB usualmente entra completo
    chunksize = 200000
    engine = create_engine(engine_url)
    
    chunks_procesados = 0
    filas_totales = 0
    
    try:
        # El CSV tiene encoding que puede ser ANSI / latin1 
        for chunk in pd.read_csv(archivo_csv, encoding='latin1', delimiter=',', chunksize=chunksize, dtype=str):
            chunks_procesados += 1
            
            # Limpiar nombres de columnas para que coincidan con la DB
            # RNC,RAZON SOCIAL,ACTIVIDAD ECONOMICA,FECHA DE INICIO OPERACIONES,ESTADO,RÉGIMEN DE PAGO
            chunk.columns = ['rnc', 'razon_social', 'actividad_economica', 'fecha_inicio', 'estado', 'regimen_pago']
            
            # Insertar en DB usando to_sql asimilando append
            chunk.to_sql('padron_dgii', con=engine, if_exists='append', index=False, method='multi', chunksize=5000)
            
            filas = len(chunk)
            filas_totales += filas
            print(f"  [+] Chunk {chunks_procesados} importado ({filas} registros)...")
            
    except Exception as e:
        print(f"[!] Error durante la importación: {e}")
        return

    end_time = time.time()
    print("=====================================================")
    print(f"[OK] Importación Finalizada en {round(end_time - start_time, 2)} segundos.")
    print(f"     Total de RNCs habilitados: {filas_totales}")
    print("=====================================================")

if __name__ == "__main__":
    archivo_origen = r"C:\Users\pgaco\Downloads\RNC_CONTRIBUYENTES\RNC_Contribuyentes_Actualizado_07_Mar_2026.csv"
    bd_url = "sqlite:///c:/GEMINI/AiContaFiscalRD/data/aicontafiscal_core.db"
    importar_padron(archivo_origen, bd_url)
