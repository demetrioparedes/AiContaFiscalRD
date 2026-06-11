"""
motor_riesgo_dgii.py — Motor 3: Estimación de Riesgo de Fiscalización DGII
============================================================================
Evalúa la probabilidad de que la DGII abra una fiscalización o ajuste fiscal
basándose en los patrones que usan los auditores fiscales dominicanos en la práctica.

CRITERIOS DE RIESGO (basados en práctica auditorial dominicana):

  GRUPO A - Márgenes y Rentabilidad:
    A1: Margen de utilidad < 5% de ventas  → Riesgo ALTO
    A2: Pérdidas consecutivas               → Riesgo MUY ALTO
    A3: Costo de ventas > 90% de ventas    → Riesgo ALTO

  GRUPO B - Retenciones y Nómina:
    B1: Nómina declarada con retenciones = 0 → Riesgo ALTO
    B2: TSS reportada vs gastos de personal dispares → Riesgo MEDIO
    B3: Empleados sin NSS / Cédula           → Riesgo MEDIO

  GRUPO C - Cruce de Terceros:
    C1: Lo que terceros reportaron comprar > ventas declaradas → Riesgo MUY ALTO
    C2: Diferencia > 20% entre ventas 607 y terceros         → Riesgo ALTO
    C3: ITBIS retenido por tarjetas no reflejado en IT-1     → Riesgo MEDIO

  GRUPO D - Incidencias en Declaraciones DGII:
    D1: Errores críticos en los 18 Cruces Fiscales (BIG4)    → Riesgo según cantidad
    D2: Declaraciones corregidas o pendientes                → Riesgo MEDIO
    D3: Retenciones del IR-17 no conciliadas                 → Riesgo ALTO

  GRUPO E - Sectorial:
    E1: Cartera (carteras/moda) → Mayor escrutinio DGII por efectivo
    E2: Comercios con alta proporción de ventas en efectivo  → Riesgo MEDIO
"""
import sys, os

# Resolución dinámica de ruta del proyecto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from database import SessionLocal, Empresa, EstadoFinanciero, ValidacionFiscal, TssNomina, Ir18Retenciones, Dgii606, Dgii607
from sqlalchemy import func, and_

# ------------------------------------------------------------------
# PESOS del ALGORITMO DE RIESGO
# ------------------------------------------------------------------
PESOS = {
    # [Factor] = (puntos_si_aplica, nivel_riesgo_solo_este_factor)
    "margen_bajo_5":     (25, "ALTO"),
    "perdida_neta":      (35, "MUY_ALTO"),
    "costo_mayor_90":    (20, "ALTO"),
    "retencion_cero":    (25, "ALTO"),
    "tss_vs_gasto":      (15, "MEDIO"),
    "terceros_mayor_ventas": (40, "MUY_ALTO"),
    "dif_terceros_20":   (20, "ALTO"),
    "itbis_tarjetas":    (10, "MEDIO"),
    "errores_criticos":  (10, "ALTO"),     # por cada error crítico
    "advertencias":      (5,  "MEDIO"),    # por cada advertencia
    "sector_efectivo":   (10, "MEDIO"),
}

def calcular_riesgo(rnc_empresa: str, anio: int, cruce_terceros_data=None) -> dict:
    """
    Calcula el Índice de Riesgo DGII (0-100) y genera un diagnóstico completo.
    """
    db = SessionLocal()
    anio_str = str(anio)
    flags = []       # Banderas activadas
    puntos = 0       # Puntos de riesgo acumulados

    empresa = db.query(Empresa).filter_by(rnc=rnc_empresa).first()
    if not empresa:
        db.close()
        return {"error": f"Empresa RNC {rnc_empresa} no encontrada"}
    
    emp_id = empresa.id

    # -------------------------------------------------------
    # GRUPO A: MÁRGENES Y RENTABILIDAD
    # -------------------------------------------------------
    ef = db.query(EstadoFinanciero).filter_by(
        empresa_id=emp_id, periodo=anio_str
    ).order_by(EstadoFinanciero.id.desc()).first()

    if ef:
        ventas = float(ef.ventas_totales or 0)
        utilidad = float(ef.utilidad_neta or 0)
        costo_v = float(ef.costo_ventas or 0)
        
        if ventas > 0:
            margen = (utilidad / ventas) * 100
            
            # A1: Margen < 5%
            if margen < 5:
                ptos, nivel = PESOS["margen_bajo_5"]
                puntos += ptos
                flags.append({
                    "codigo": "A1",
                    "nivel": nivel,
                    "descripcion": f"Margen de utilidad {margen:.1f}% < 5% mínimo esperado",
                    "puntos": ptos
                })
            
            # A2: Pérdida neta
            if utilidad < 0:
                ptos, nivel = PESOS["perdida_neta"]
                puntos += ptos
                flags.append({
                    "codigo": "A2",
                    "nivel": nivel,
                    "descripcion": f"Pérdida neta de RD$ {abs(utilidad):,.0f} — DGII investigará costos ficticios",
                    "puntos": ptos
                })

            # A3: Costo de ventas > 90% de ventas
            if ventas > 0 and (costo_v / ventas) > 0.90:
                ptos, nivel = PESOS["costo_mayor_90"]
                puntos += ptos
                flags.append({
                    "codigo": "A3",
                    "nivel": nivel,
                    "descripcion": f"Costo de ventas = {(costo_v/ventas)*100:.1f}% de ventas (tope razonable: 80%)",
                    "puntos": ptos
                })

    # -------------------------------------------------------
    # GRUPO B: RETENCIONES Y NÓMINA
    # -------------------------------------------------------
    tss_total = float(db.query(func.sum(TssNomina.aporte_empresa)).filter(
        and_(TssNomina.empresa_id == emp_id, TssNomina.periodo.like(f"{anio_str}%"))
    ).scalar() or 0.0)

    isr_nomina = float(db.query(func.sum(Ir18Retenciones.retencion_isr)).filter(
        and_(Ir18Retenciones.empresa_id == emp_id)
    ).scalar() or 0.0)

    # B1: Hay TSS (tenemos empleados) pero ISR retenido = 0
    if tss_total > 0 and isr_nomina == 0:
        ptos, nivel = PESOS["retencion_cero"]
        puntos += ptos
        flags.append({
            "codigo": "B1",
            "nivel": nivel,
            "descripcion": f"TSS pagada RD$ {tss_total:,.0f} pero retención IR-13 = 0 (falta de retención a asalariados)",
            "puntos": ptos
        })

    # B2: TSS pagada vs gasto de personal en ER
    if ef and tss_total > 0:
        gasto_personal = float(ef.gastos_personal or 0)
        if gasto_personal > 0:
            ratio_tss = tss_total / gasto_personal
            if ratio_tss < 0.10 or ratio_tss > 0.50:  # TSS debería ser ≈ 20-30% de la nómina
                ptos, nivel = PESOS["tss_vs_gasto"]
                puntos += ptos
                flags.append({
                    "codigo": "B2",
                    "nivel": nivel,
                    "descripcion": f"TSS ({tss_total:,.0f}) es {ratio_tss*100:.1f}% del gasto personal ({gasto_personal:,.0f}) — relación inusual",
                    "puntos": ptos
                })

    # -------------------------------------------------------
    # GRUPO C: CRUCE DE TERCEROS
    # -------------------------------------------------------
    if cruce_terceros_data:
        terceros_606, tarjetas, itbis_tarj, diferencia = cruce_terceros_data
        total_terceros = terceros_606 + tarjetas
        ventas_ef = float(ef.ventas_totales) if ef else 0

        # C1: Terceros reportan MÁS que las ventas declaradas
        if total_terceros > ventas_ef and ventas_ef > 0:
            ptos, nivel = PESOS["terceros_mayor_ventas"]
            puntos += ptos
            flags.append({
                "codigo": "C1",
                "nivel": nivel,
                "descripcion": f"Terceros reportan RD$ {total_terceros:,.0f} vs ventas declaradas RD$ {ventas_ef:,.0f} (diferencia crítica)",
                "puntos": ptos
            })
        elif ventas_ef > 0:
            # C2: Diferencia > 20%
            dif_pct = abs(ventas_ef - total_terceros) / ventas_ef * 100
            if dif_pct > 20:
                ptos, nivel = PESOS["dif_terceros_20"]
                puntos += ptos
                flags.append({
                    "codigo": "C2",
                    "nivel": nivel,
                    "descripcion": f"Diferencia de {dif_pct:.1f}% entre ventas 607 y cruce de terceros",
                    "puntos": ptos
                })

        # C3: ITBIS retenido por tarjetas
        if itbis_tarj > 0:
            flags.append({
                "codigo": "C3",
                "nivel": "INFORMATIVO",
                "descripcion": f"ITBIS retenido por tarjetas RD$ {itbis_tarj:,.0f} — confirmar que esté en IT-1",
                "puntos": 0
            })

    # -------------------------------------------------------
    # GRUPO D: CRUCES BIG4 (Resultados del Motor de Validación)
    # -------------------------------------------------------
    errores_criticos = db.query(ValidacionFiscal).filter_by(
        empresa_id=emp_id, periodo=anio_str, estado="ERROR"
    ).count()
    
    advertencias = db.query(ValidacionFiscal).filter_by(
        empresa_id=emp_id, periodo=anio_str, estado="ALERTA"
    ).count()

    if errores_criticos > 0:
        ptos = PESOS["errores_criticos"][0] * errores_criticos
        puntos += ptos
        flags.append({
            "codigo": "D1",
            "nivel": "ALTO" if errores_criticos >= 2 else "MEDIO",
            "descripcion": f"{errores_criticos} error(es) crítico(s) detectados en los 18 Cruces Fiscales BIG4",
            "puntos": ptos
        })

    if advertencias > 0:
        ptos = PESOS["advertencias"][0] * advertencias
        puntos += ptos
        flags.append({
            "codigo": "D2",
            "nivel": "MEDIO",
            "descripcion": f"{advertencias} advertencia(s) en los cruces fiscales — revisar con contador",
            "puntos": ptos
        })

    # -------------------------------------------------------
    # GRUPO E: SECTOR
    # -------------------------------------------------------
    nombre_emp = (empresa.nombre_empresa or "").upper()
    sectores_efectivo = ["CARTERA", "MODA", "CALZADO", "FERRETERIA", "TALLER", "SALON", "RESTAURANT", "COLMADO"]
    if any(s in nombre_emp for s in sectores_efectivo):
        ptos, nivel = PESOS["sector_efectivo"]
        puntos += ptos
        flags.append({
            "codigo": "E1",
            "nivel": nivel,
            "descripcion": f"Sector con alta proporción de ventas en efectivo (mayor escrutinio DGII)",
            "puntos": ptos
        })

    db.close()

    # -------------------------------------------------------
    # CÁLCULO FINAL DEL ÍNDICE
    # -------------------------------------------------------
    puntos_max = 150   # máximo teórico de puntos
    indice = min(int((puntos / puntos_max) * 100), 100)

    if indice >= 70:
        nivel_global = "MUY_ALTO"
        mensaje = "ALERTA ROJA: Alta probabilidad de fiscalización DGII. Se recomienda revisión urgente con contador."
        semaforo = "ROJO"
    elif indice >= 45:
        nivel_global = "ALTO"
        mensaje = "ATENCIÓN: Existen factores de riesgo significativos. Revisar y corregir antes de declarar."
        semaforo = "NARANJA"
    elif indice >= 25:
        nivel_global = "MEDIO"
        mensaje = "Riesgo moderado. Algunos indicadores requieren atención antes de presentar el IR-2."
        semaforo = "AMARILLO"
    else:
        nivel_global = "BAJO"
        mensaje = "Declaración en buen estado. Riesgo de fiscalización bajo según los indicadores disponibles."
        semaforo = "VERDE"

    return {
        "rnc": rnc_empresa,
        "anio": anio,
        "indice_riesgo": indice,
        "nivel": nivel_global,
        "semaforo": semaforo,
        "mensaje": mensaje,
        "total_flags": len(flags),
        "flags": flags
    }


def imprimir_informe_riesgo(rnc: str, anio: int, cruce_terceros_data=None):
    """Imprime el informe de riesgo DGII en consola."""
    resultado = calcular_riesgo(rnc, anio, cruce_terceros_data)
    
    if "error" in resultado:
        print(f"ERROR: {resultado['error']}")
        return resultado

    indice = resultado['indice_riesgo']
    nivel  = resultado['nivel']
    semaf  = resultado['semaforo']

    semaforo_str = {"VERDE": "[==VERDE==]", "AMARILLO": "[=AMARILLO]", "NARANJA": "[=NARANJA=]", "ROJO": "[===ROJO===]"}

    print("\n" + "=" * 70)
    print(f"  INFORME DE RIESGO FISCAL DGII | RNC: {rnc} | Año: {anio}")
    print("=" * 70)
    print(f"  Indice de Riesgo: {indice}% {semaforo_str.get(semaf, '')}")
    print(f"  Nivel Global:     {nivel}")
    print(f"  {resultado['mensaje']}")
    print("-" * 70)
    
    if resultado['flags']:
        print(f"  BANDERAS DETECTADAS ({resultado['total_flags']}):")
        for flag in resultado['flags']:
            print(f"    [{flag['codigo']}] [{flag['nivel']:10s}] +{flag['puntos']:2d} pts | {flag['descripcion']}")
    else:
        print("  Sin banderas de riesgo detectadas. Expediente limpio.")
    
    print("=" * 70)
    return resultado


if __name__ == "__main__":
    imprimir_informe_riesgo("130826552", 2025)
