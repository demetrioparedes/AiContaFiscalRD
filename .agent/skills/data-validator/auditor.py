import sys
import json
import os

EXTRACTED_DATA = r"c:\GEMINI\AiContaFiscalRD\data\extracted\datos_validados.json"

def main():
    print("=== AiContaFiscalRD: AUDITOR DE RIESGOS FISCALES ===")
    
    if not os.path.exists(EXTRACTED_DATA):
        print("ERROR: No se encontró el archivo de datos extraídos.")
        sys.exit(1)
        
    with open(EXTRACTED_DATA, "r", encoding='utf-8') as f:
        datos = json.load(f)

    analisis = datos.get("analisis_contable_excel", {})
    dgii = datos.get("cruces_dgii", {})
    
    alertas = []

    # REGLA 1: Cruce de Compras Locales vs Reporte 606 DGII
    # Las compras de análisis deberian cuadrar o estar contenidas en el 606 (más servicios).
    # Compras locales en este caso de excel ($152,344) parece ser solo mercancía. 
    # Compras totales 606: $929,698.35
    compras_analisis = analisis.get("compras_locales", 0)
    compras_606 = dgii.get("compras_reportadas_606", 0)
    
    print(f"\nCRUCE 1: Compras Locales vs Formato 606")
    print(f"  -> Compras en Análisis: RD$ {compras_analisis:,.2f}")
    print(f"  -> Compras en F.606:    RD$ {compras_606:,.2f}")
    
    if compras_606 > compras_analisis:
        diff = compras_606 - compras_analisis
        alertas.append({
            "nivel": "AMARILLA",
            "mensaje": f"El Formato 606 (RD$ {compras_606:,.2f}) incluye RD$ {diff:,.2f} más que la columna 'Compras' del Análisis. Asumiremos que esta diferencia corresponde a GASTOS OPERATIVOS o SERVICIOS para los anexos."
        })
    elif compras_analisis > compras_606:
        alerta_msg = f"RIESGO FISCAL: Registraste más compras locales (RD$ {compras_analisis:,.2f}) que las reportadas a DGII (RD$ {compras_606:,.2f})."
        alertas.append({"nivel": "ROJA", "mensaje": alerta_msg})
        
    # REGLA 2: Lógica de Inventario
    inv_inicial = datos.get("anexos_año_anterior", {}).get("inventario_final_anexod", 0)
    print(f"\nCRUCE 2: Inventarios")
    print(f"  -> Inventario Inicial Extraído (Final 2024): RD$ {inv_inicial:,.2f}")
    
    # REGLA 3: Anticipos Pagados
    anticipos = analisis.get("anticipos_pagados", 0)
    print(f"\nCRUCE 3: Anticipos Pagados en el Año")
    print(f"  -> Anticipos detectados en Excel: RD$ {anticipos:,.2f}")

    print("\n\n=== REPORTE DE ALERTAS ===")
    if not alertas:
         print("✅ Todo parece consistente. Ninguna alerta fiscal grave detectada.")
    else:
        for alerta in alertas:
            icono = "[OK]"
            if alerta["nivel"] == "AMARILLA": icono = "[!]"
            if alerta["nivel"] == "ROJA": icono = "[X]"
            print(f"{icono} {alerta['mensaje']}")

if __name__ == "__main__":
    main()
