import requests
import os

BASE_URL = "http://localhost:8000"
API_KEY = "AiConta_Secure_Key_2026_RD"

def test_blindaje():
    print("--- INICIANDO AUDITORÍA DE SEGURIDAD (OPERACIÓN ESCUDO) ---")
    
    # 1. Health Check Pro
    print("[1/5] Verificando Salud Avanzada...")
    try:
        r = requests.get(f"{BASE_URL}/api/health")
        print(f"Respuesta: {r.status_code} - {r.json()}")
    except Exception as e:
        print(f"ERROR: API no responde. ¿Está encendida?")
        return

    # 2. Acceso no autorizado
    print("\n[2/5] Probando Bloqueo de Acceso (Sin API Key)...")
    r = requests.get(f"{BASE_URL}/api/clientes")
    if r.status_code == 403:
        print("EXITO: Acceso bloqueado correctamente.")
    else:
        print(f"FALLA: Se permitió acceso o error distinto: {r.status_code}")

    # 3. Path Traversal
    print("\n[3/5] Probando Protección Path Traversal (../../.env)...")
    headers = {"X-API-KEY": API_KEY}
    r = requests.get(f"{BASE_URL}/api/descargar/../../.env", headers=headers)
    if r.status_code in [403, 404]:
        print(f"EXITO: Bloqueado/No encontrado (Status: {r.status_code})")
    else:
        print(f"FALLA: Posible vulnerabilidad detectada: {r.status_code}")

    # 4. Global Exception Handler (Trigger fake error)
    print("\n[4/5] Probando Global Exception Handler (Error Controlado)...")
    # Intentamos buscar en padrón con algo que rompa o un endpoint inexistente
    r = requests.get(f"{BASE_URL}/api/clientes/999999", headers=headers)
    if r.status_code == 404:
        print("Info: Endpoint funciona normal (404 esperado).")
    
    # Triggering a real server error if possible (e.g. malformed JSON to a POST)
    print("Simulando error interno...")
    r = requests.post(f"{BASE_URL}/api/clientes", headers=headers, json={"rnc": None}) # Esto debería romper validación Pydantic o DB
    data = r.json()
    if "error_id" in data:
        print(f"EXITO: Error capturado por el Escudo Fiscal. ID: {data['error_id']}")
        print(f"Mensaje limpio: {data['message']}")
    else:
        print("FALLA: El error crudo se filtró al cliente.")

    # 5. Verificación de Servicios
    print("\n[5/5] Verificando Integridad de Datos...")
    r = requests.get(f"{BASE_URL}/api/clientes", headers=headers)
    if r.status_code == 200:
        print(f"EXITO: Conexión a DB estable. Clientes encontrados: {r.json().get('total')}")

if __name__ == "__main__":
    test_blindaje()
