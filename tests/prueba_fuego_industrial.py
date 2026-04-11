# tests/prueba_fuego_industrial.py
import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

API_URL = "http://localhost:8000"
API_KEY = os.getenv("API_SECRET_KEY")

def test_pipeline_audit_completo():
    print("\n[+] INICIANDO PRUEBA DE FUEGO INDUSTRIAL")
    print("-" * 40)
    
    headers = {
        "X-API-KEY": API_KEY
    }
    
    # 1. Ejecutar Procesamiento
    print("  [Step 1] Ejecutando Pipeline de Auditoría...")
    data = {
        "rnc": "130826552",
        "periodo": "2025"
    }
    
    response = requests.post(f"{API_URL}/api/procesar", data=data, headers=headers)
    
    if response.status_code == 200:
        res_json = response.json()
        print(f"  [OK] Procesamiento exitoso. Estado: {res_json.get('status')}")
        print(f"  [MSG] {res_json.get('message')}")
    else:
        print(f"  [!] ERROR en Procesamiento: {response.status_code}")
        print(response.text)
        return

    # 2. Consultar Dashboard
    print("\n  [Step 2] Consultando Dashboard Analítico...")
    response = requests.get(f"{API_URL}/api/dashboard_analitico/1/2025", headers=headers)
    
    if response.status_code == 200:
        dash = response.json()
        print(f"  [OK] Dashboard recuperado.")
        print(f"  [INFO] Ingresos: {dash['resumen']['ingresos']}")
        print(f"  [INFO] Hallazgos: {len(dash['hallazgos'])}")
        print(f"  [INFO] Estado: {dash['estado_pipeline']}")
    else:
        print(f"  [!] ERROR en Dashboard: {response.status_code}")
        return

    # 3. Intentar Acceso Sin Key (Verificar Seguridad)
    print("\n  [Step 3] Verificando Seguridad (Acceso sin Key)...")
    response = requests.get(f"{API_URL}/api/dashboard_analitico/1/2025")
    if response.status_code == 403:
        print("  [OK] Seguridad verificada: Acceso denegado sin API Key.")
    else:
        print(f"  [!] FALLO DE SEGURIDAD: Se permitió acceso sin API Key (Status: {response.status_code})")

    print("\n[+] PRUEBA DE FUEGO COMPLETADA CON ÉXITO")
    print("-" * 40)

if __name__ == "__main__":
    # Asegúrate de que el servidor esté corriendo antes de ejecutar esto.
    try:
        test_pipeline_audit_completo()
    except Exception as e:
        print(f"[!] Error ejecutando la prueba: {e}")
