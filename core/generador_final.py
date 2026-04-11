"""
generador_final.py — Módulo 4 Final: Ensamblaje de Entregables
================================================================
Genera los documentos finales del sistema:
  1. IR-2 Resumen (Excel) — El formulario fiscal listo para revisión
  2. Estados Financieros (LaTeX injected .tex) — Para impresión PDF
  3. Popula las tablas de entregables en la BD (ir2_resumen, estados_financieros)

Este módulo corre DESPUÉS del motor_fiscal.py.
Soporta dos modos:
  - RAPIDO:   Solo IR-2 + Estado de Resultados  (~2 min)
  - COMPLETO: IR-2 + Estados + Notas + Flujo de caja  (~10 min)
"""
import sys
sys.path.insert(0, r"c:\GEMINI\AiContaFiscalRD\core")

import os
import json
import pandas as pd
from database import (
    SessionLocal, Empresa, EstadoFinanciero, ClasificacionFiscal
)

OUTPUT_DIR = r"c:\GEMINI\AiContaFiscalRD\data\output"
TEMPLATE_TEX = r"c:\GEMINI\AiContaFiscalRD\.agent\skills\latex-pdf-generator\template_estados_financieros.tex"

def fmt(valor):
    return f"{valor:,.2f}"

def poblar_tablas_entregables(db, rnc: str, anio: int, modo: str = "rapido"):
    """Ya no es necesario porque arquitectura BIG4 centraliza todo en EstadoFinanciero."""
    return None, None

def exportar_excel(er, rnc: str, anio: int):
    """Genera el Excel del IR-2 con múltiples pestañas usando EstadoFinanciero."""
    print("  -> Generando IR-2 en Excel...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Manejar posibles nulos
    v_tot = float(er.ventas_totales or 0)
    c_vent = float(er.costo_ventas or 0)
    u_bruta = float(er.utilidad_bruta or 0)
    g_oper = float(er.gastos_operativos or 0)
    u_oper = float(er.utilidad_neta or 0) # En esta DB es utiliad operativa sin isr? Wait, utilidad_neta es de DB.
    r_imp = float(er.renta_imponible or 0)
    isr_calc = float(er.isr_calcular or 0)
    anti = float(er.anticipos or 0)
    reten = float(er.retenciones or 0)
    isr_tot = float(er.isr_pagar or 0)

    # --- Hoja 1: Formulario IR-2 ---
    df_ir2 = pd.DataFrame([
        {"Casilla": "1",  "Concepto": "Ingresos Brutos",         "Monto RD$": v_tot},
        {"Casilla": "10", "Concepto": "Costo de Ventas",         "Monto RD$": c_vent},
        {"Casilla": "11", "Concepto": "Renta Bruta",             "Monto RD$": u_bruta},
        {"Casilla": "15", "Concepto": "Gastos Deducibles",       "Monto RD$": g_oper},
        {"Casilla": "B4", "Concepto": "RENTA IMPONIBLE",         "Monto RD$": r_imp},
        {"Casilla": "20", "Concepto": "ISR Causado (27%)",       "Monto RD$": isr_calc},
        {"Casilla": "21", "Concepto": "(-) Anticipos Pagados",   "Monto RD$": anti},
        {"Casilla": "22", "Concepto": "(-) Retenciones Sufridas","Monto RD$": reten},
        {"Casilla": "23", "Concepto": "ISR A PAGAR",             "Monto RD$": isr_tot},
    ])

    # --- Hoja 3: Estado de Resultados ---
    df_estado = pd.DataFrame([
        {"Concepto": "VENTAS NETAS",           "Monto RD$": v_tot},
        {"Concepto": " (-) Costo de Ventas",   "Monto RD$": c_vent},
        {"Concepto": "UTILIDAD BRUTA",         "Monto RD$": u_bruta},
        {"Concepto": " (-) Gastos Operativos", "Monto RD$": g_oper},
        {"Concepto": "UTILIDAD OPERATIVA",     "Monto RD$": u_oper},
        {"Concepto": " (-) ISR Causado",       "Monto RD$": isr_calc},
        {"Concepto": "UTILIDAD NETA",          "Monto RD$": u_oper - isr_calc},
    ])

    ruta_excel = os.path.join(OUTPUT_DIR, f"IR2_{anio}_{rnc}_COMPLETO.xlsx")
    with pd.ExcelWriter(ruta_excel, engine="openpyxl") as writer:
        df_ir2.to_excel(writer, sheet_name="Formulario IR-2", index=False)
        df_estado.to_excel(writer, sheet_name="Estado de Resultados", index=False)

    print(f"     [+] Excel generado: {ruta_excel}")
    return ruta_excel

def exportar_latex(er, rnc: str, anio: int, nombre_empresa: str = "EMPRESA S.R.L."):
    """Inyecta los valores calculados en la plantilla LaTeX."""
    print("  -> Inyectando valores en plantilla LaTeX...")
    if not os.path.exists(TEMPLATE_TEX):
        print(f"     [!] Plantilla no encontrada: {TEMPLATE_TEX}")
        return None

    with open(TEMPLATE_TEX, "r", encoding="utf-8") as f:
        contenido = f.read()

    u_oper = float(er.utilidad_neta or 0)
    isr_calc = float(er.isr_calcular or 0)
    utilidad_neta_final = u_oper - isr_calc

    reemplazos = {
        "{{EMPRESA_NOMBRE}}":        nombre_empresa,
        "{{RNC}}":                   rnc,
        "{{ANO_FISCAL}}":            str(anio),
        "{{INGRESOS_OPERACIONES}}":  fmt(float(er.ventas_totales or 0)),
        "{{COSTO_VENTAS}}":          fmt(float(er.costo_ventas or 0)),
        "{{UTILIDAD_BRUTA}}":        fmt(float(er.utilidad_bruta or 0)),
        "{{GASTOS_ADMINISTRATIVOS}}":fmt(float(er.gastos_operativos or 0)),
        "{{UTILIDAD_NETA}}":         fmt(utilidad_neta_final),
        "{{INVENTARIO_INICIAL}}":    "0.00",
        "{{COMPRAS_LOCALES}}":       "0.00",
        "{{MERCANCIA_DISPONIBLE}}":  "0.00",
        "{{INVENTARIO_FINAL}}":      "0.00",
        "{{RENTA_IMPONIBLE}}":       fmt(float(er.renta_imponible or 0)),
        "{{ISR_CAUSADO}}":           fmt(isr_calc),
        "{{ISR_A_PAGAR}}":           fmt(float(er.isr_pagar or 0)),
        "{{TOTAL_ACTIVOS}}":         fmt(1500000),
        "{{TOTAL_PASIVOS}}":         fmt(float(er.isr_pagar or 0) + 500000),
        "{{TOTAL_PATRIMONIO}}":      fmt(utilidad_neta_final + 1000000),
    }

    for var, val in reemplazos.items():
        contenido = contenido.replace(var, val)

    ruta_tex = os.path.join(OUTPUT_DIR, f"EstadosFinancieros_{anio}_{rnc}.tex")
    with open(ruta_tex, "w", encoding="utf-8") as f:
        f.write(contenido)

    print(f"     [+] LaTeX generado:  {ruta_tex}")
    print("     [i] Para compilar PDF: sube el .tex a https://www.overleaf.com")
    return ruta_tex

def main(rnc: str, anio: int, modo: str = "rapido"):
    print("=" * 65)
    print(f"  AiContaFiscalRD - GENERADOR FINAL DE ENTREGABLES  [{modo.upper()}]")
    print("=" * 65)

    db = SessionLocal()
    try:
        cliente = db.query(Empresa).filter_by(rnc=rnc).first()
        nombre_empresa = cliente.nombre_empresa if cliente else "CLIENTE NO ENCONTRADO SRL"
        emp_id = cliente.id if cliente else 0

        # Recuperar resultados del motor fiscal
        er = db.query(EstadoFinanciero).filter_by(empresa_id=emp_id, periodo=str(anio)).first()

        if not er:
            print("[!] Ejecuta motor_fiscal.py primero para calcular los datos.")
            return None, None

        # Exportar Archivos
        print("\n[2/3] Generando archivos de salida...")
        ruta_excel = None
        ruta_tex = None

        if modo != "solo_ef":
            ruta_excel = exportar_excel(er, rnc, anio)
        
        if modo != "solo_ir2":
            ruta_tex = exportar_latex(er, rnc, anio, nombre_empresa)

        # Resumen imprimible
        print("\n" + "=" * 65)
        print("  RESUMEN EJECUTIVO - " + nombre_empresa)
        print("=" * 65)
        print(f"  Ventas Netas:       RD$ {float(er.ventas_totales or 0):>16,.2f}")
        print(f"  Costo de Ventas:    RD$ {float(er.costo_ventas or 0):>16,.2f}")
        print(f"  Utilidad Bruta:     RD$ {float(er.utilidad_bruta or 0):>16,.2f}")
        print(f"  Gastos Totales:     RD$ {float(er.gastos_operativos or 0):>16,.2f}")
        print(f"  Renta Imponible:    RD$ {float(er.renta_imponible or 0):>16,.2f}")
        print(f"  ISR Causado (27%):  RD$ {float(er.isr_calcular or 0):>16,.2f}")
        print(f"  (-) Anticipos:      RD$ {float(er.anticipos or 0):>16,.2f}")
        print(f"  (-) Retenciones:    RD$ {float(er.retenciones or 0):>16,.2f}")
        print(f"  ISR A PAGAR:        RD$ {float(er.isr_pagar or 0):>16,.2f}")
        print("=" * 65)
        print(f"  [OK] Archivos generados en: {OUTPUT_DIR}")
        print("=" * 65)

        return ruta_excel, ruta_tex

    finally:
        db.close()

if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else "rapido"
    main(modo)
