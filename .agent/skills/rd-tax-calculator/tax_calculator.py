import json
import os
import sys

# Paths de los datos de entrada y salida
INPUT_DATA_PATH = r"c:\GEMINI\AiContaFiscalRD\data\extracted\db_payload_export.json"
OUTPUT_ANEXOS_PATH = r"c:\GEMINI\AiContaFiscalRD\data\consolidated\anexos_calculados.json"

def calcular_anexo_d(totales):
    """
    Anexo D: Estado de Costos de Ventas
    Calcula el Costo de Ventas según la DGII:
    Inicial + Compras Locales + Importaciones - Inventario Final
    """
    print("  -> Calculando Anexo D (Costo de Ventas)...")
    inv_inicial = totales.get("inventario_final_anterior", 0.0)
    compras_loc = totales.get("compras_gravadas", 0.0)
    importaciones = totales.get("importaciones", 0.0) # Si hay, la metemos aquí
    # Para el final nos hace falta que el usuario lo diga, asumimos 0 si no lo subió aún
    inv_final = totales.get("inventario_final", 0.0)
    
    mercancia_disponible = inv_inicial + compras_loc + importaciones
    costo_ventas = mercancia_disponible - inv_final
    
    return {
        "D_Casilla_1_Inventario_Inicial": inv_inicial,
        "D_Casilla_2_Compras_Locales": compras_loc,
        "D_Casilla_3_Importaciones": importaciones,
        "D_Total_Mercancia_Disponible": mercancia_disponible,
        "D_Casilla_5_Inventario_Final": inv_final,
        "D_Total_Costo_Ventas": costo_ventas
    }

def calcular_anexo_a(totales, anexo_d_calculado):
    """
    Anexo A: Estado de Resultados Fiscal
    Toma los ingresos y resta los costos del Anexo D para obtener la Renta Bruta
    """
    print("  -> Calculando Anexo A (Estado de Resultados)...")
    ingresos = totales.get("ventas_gravadas", 0.0) + totales.get("ventas_exentas", 0.0)
    costo_ventas = anexo_d_calculado.get("D_Total_Costo_Ventas", 0.0)
    
    renta_bruta = ingresos - costo_ventas
    
    # Asumimos que la diferencia del 606 son gastos de servicios y suministros deduciéndolos aquí
    gastos_operativos = totales.get("gastos_operativos_detectados", 0.0)
    
    renta_neta_antes_isr = renta_bruta - gastos_operativos

    return {
        "A_Casilla_1_Ingresos_Operaciones": ingresos,
        "A_Casilla_10_Costo_Ventas": costo_ventas,
        "A_Casilla_11_Renta_Bruta": renta_bruta,
        "A_Casilla_XX_Gastos_Operativos": gastos_operativos,
        "A_Total_Renta_Neta_Antes_ISR": renta_neta_antes_isr
    }

def main():
    print("\n=== AiContaFiscalRD: MOTOR LLENADOR DE ANEXOS ===")
    
    if not os.path.exists(INPUT_DATA_PATH):
         print("ERROR: Falta el JSON con los DatosExtraidos del paso anterior.")
         sys.exit(1)
         
    with open(INPUT_DATA_PATH, "r", encoding='utf-8') as f:
         payload = json.load(f)
         
    datos_extraidos = payload.get("datos_extraidos", [])
    
    # 1. Consolidar los importes por "tipo_dato" agrupándolos
    totales_consolidados = {}
    
    for dato in datos_extraidos:
        # Solo procesamos si no tiene conflicto (los conflictos deben ser resueltos en UI).
        # Por ahora, para la prueba del núcleo, tomaremos el valor más grande si hay conflicto
        # o los sumaremos. En un modelo real, el frontend nos mandaría el confirmado=True.
        # Aquí consolidamos "a lo bruto" como prueba de concepto (Pragmático):
        tipo = dato["tipo_dato"]
        if "inventario_final" in tipo and "2024" in dato.get("periodo", ""):
             totales_consolidados["inventario_final_anterior"] = dato["valor"]
             continue
             
        if tipo not in totales_consolidados:
             totales_consolidados[tipo] = dato["valor"]
        else:
             # Por ser híbridos y prácticos, si hay 2 fuentes de compras, y una es de análisis (excel) y otra del 606 (servicios).
             # La diferencia se la vamos a sumar como gasto operativo.
             if tipo == "compras_gravadas":
                  valor_mayor = max(totales_consolidados[tipo], dato["valor"])
                  valor_menor = min(totales_consolidados[tipo], dato["valor"])
                  # Si el Excel traía las compras contables y 606 traía servicios
                  totales_consolidados["compras_gravadas"] = valor_menor  # Ponemos solo la mercancia como Compras
                  totales_consolidados["gastos_operativos_detectados"] = valor_mayor - valor_menor # El resto al Gasto
             else:
                  totales_consolidados[tipo] += dato["valor"]

    print("\n[Variables Bases Detectadas y Consolidadas]")
    for k, v in totales_consolidados.items():
        print(f"  - {k}: \tRD$ {v:,.2f}")
        
    # 2. Ejecutar Calculadora por Anexo en orden lógico (D primero, luego A)
    print("\n[Ejecutando Arbol de Anexos DGII]")
    anexo_d = calcular_anexo_d(totales_consolidados)
    anexo_a = calcular_anexo_a(totales_consolidados, anexo_d)
    
    # 3. Guardar el paquete de la Declaración final calculada
    declaracion_final = {
        "status": "Calculado Exitosamente",
        "anexo_d": anexo_d,
        "anexo_a": anexo_a,
        "otros_datos_ir2": {
            "anticipos_pagados_para_ir2": totales_consolidados.get("anticipos_isr", 0.0),
            "retenciones_sufridas_para_ir2": totales_consolidados.get("retenciones_sufridas", 0.0)
        }
    }
    
    os.makedirs(os.path.dirname(OUTPUT_ANEXOS_PATH), exist_ok=True)
    with open(OUTPUT_ANEXOS_PATH, "w", encoding='utf-8') as f:
         json.dump(declaracion_final, f, indent=4, ensure_ascii=False)
         
    print(f"\n[OK] Anexos Listos y guardados en: {OUTPUT_ANEXOS_PATH}")
    print("\n[Resumen Rápido del Estado de Resultados (Anexo A)]")
    print(f"  Ventas RD$: {anexo_a['A_Casilla_1_Ingresos_Operaciones']:,.2f}")
    print(f"  Costos RD$:  {anexo_a['A_Casilla_10_Costo_Ventas']:,.2f}")
    print(f"  Gastos RD$:  {anexo_a['A_Casilla_XX_Gastos_Operativos']:,.2f}")
    print(f"  Ganancia (Renta Neta) RD$: {anexo_a['A_Total_Renta_Neta_Antes_ISR']:,.2f}  <--- ¡Base del Impuesto IR-2!")

if __name__ == "__main__":
    main()
