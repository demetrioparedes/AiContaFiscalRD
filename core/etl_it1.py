"""
etl_it1.py — Módulo 0-B: Ingesta IT-1 (Declaraciones Juradas ITBIS)
====================================================================
Extrae los datos mensuales de declaraciones IT-1 desde:
  - CSV estructurado (formato estándar del sistema)
  - Diccionario inline (para carga manual/API)

Alimenta la tabla DgiiIt1 que usan los Cruces 02, 03 y 08 del Motor BIG4.
"""
import sys
sys.path.insert(0, r"c:\GEMINI\AiContaFiscalRD\core")

import os
import csv
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from database import SessionLocal, Empresa, DgiiIt1

# ===========================================================
# UTILIDAD DECIMAL
# ===========================================================

def _d(valor) -> Decimal:
    """Convierte cualquier valor a Decimal ROUND_HALF_UP."""
    try:
        limpio = str(valor).replace(",", "").replace(" ", "").strip()
        if not limpio or limpio in ("", "None", "nan", "NULL"):
            return Decimal("0.00")
        return Decimal(limpio).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return Decimal("0.00")

# ===========================================================
# CARGA DESDE CSV
# ===========================================================

def cargar_it1_csv(ruta_csv: str, empresa_id: int, db) -> int:
    """
    Lee un CSV con columnas:
      periodo, ventas_gravadas, ventas_exentas, itbis_generado,
      compras_gravadas, itbis_credito, retenciones, itbis_a_pagar

    Inserta en DgiiIt1. Si el periodo ya existe, lo sobreescribe.
    Retorna el número de registros insertados/actualizados.
    """
    if not os.path.exists(ruta_csv):
        print(f"  [!] Archivo IT-1 no encontrado: {ruta_csv}")
        return 0

    insertados = 0
    errores = 0

    with open(ruta_csv, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for fila in reader:
            try:
                periodo = str(fila.get("periodo", "")).strip()
                if len(periodo) != 6 or not periodo.isdigit():
                    errores += 1
                    continue

                # Verificar si ya existe para este periodo y empresa
                existente = db.query(DgiiIt1).filter_by(
                    empresa_id=empresa_id, periodo=periodo
                ).first()

                valores = dict(
                    empresa_id       = empresa_id,
                    periodo          = periodo,
                    ventas_gravadas  = _d(fila.get("ventas_gravadas", 0)),
                    ventas_exentas   = _d(fila.get("ventas_exentas", 0)),
                    itbis_generado   = _d(fila.get("itbis_generado", 0)),
                    compras_gravadas = _d(fila.get("compras_gravadas", 0)),
                    itbis_credito    = _d(fila.get("itbis_credito", 0)),
                    itbis_retenido_terceros = _d(fila.get("retenciones", 0)),
                    itbis_a_pagar   = _d(fila.get("itbis_a_pagar", 0)),
                )

                if existente:
                    for k, v in valores.items():
                        setattr(existente, k, v)
                else:
                    db.add(DgiiIt1(**valores))

                insertados += 1

            except Exception as e:
                print(f"  [!] Error en fila {fila}: {e}")
                errores += 1

    db.commit()
    print(f"    [IT-1] Insertados/Actualizados: {insertados} | Errores: {errores}")
    return insertados


# ===========================================================
# CARGA MANUAL (API / TEST)
# ===========================================================

def cargar_it1_manual(empresa_id: int, registros: list, db) -> int:
    """
    Carga IT-1 desde lista de dicts. Ideal para tests y API.
    Cada dict debe tener: periodo, ventas_gravadas, itbis_generado, itbis_credito,
                          ventas_exentas (opt), compras_gravadas (opt), itbis_a_pagar (opt)
    """
    fake_csv_rows = []
    for r in registros:
        fake_csv_rows.append({
            "periodo":          r.get("periodo", ""),
            "ventas_gravadas":  r.get("ventas_gravadas", 0),
            "ventas_exentas":   r.get("ventas_exentas", 0),
            "itbis_generado":   r.get("itbis_generado", 0),
            "compras_gravadas": r.get("compras_gravadas", 0),
            "itbis_credito":    r.get("itbis_credito", 0),
            "retenciones":      r.get("retenciones", 0),
            "itbis_a_pagar":    r.get("itbis_a_pagar", 0),
        })

    # Escribe un CSV temporal y reutiliza cargar_it1_csv
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False,
                                     encoding="utf-8", newline="") as tmp:
        writer = csv.DictWriter(tmp, fieldnames=fake_csv_rows[0].keys())
        writer.writeheader()
        writer.writerows(fake_csv_rows)
        tmp_path = tmp.name

    count = cargar_it1_csv(tmp_path, empresa_id, db)
    os.unlink(tmp_path)
    return count


# ===========================================================
# TEST STANDALONE
# ===========================================================

if __name__ == "__main__":
    import sys
    rnc = "130826552"
    csv_path = rf"c:\GEMINI\AiContaFiscalRD\data\clientes\{rnc}\01_Formatos_606_607\IT1_{rnc}_2024.csv"

    db = SessionLocal()
    try:
        empresa = db.query(Empresa).filter_by(rnc=rnc).first()
        if not empresa:
            print(f"[!] Empresa {rnc} no encontrada en la BD.")
            sys.exit(1)

        print(f"[IT-1] Cargando declaraciones para {empresa.nombre_empresa} ({rnc})...")
        n = cargar_it1_csv(csv_path, empresa.id, db)
        print(f"[IT-1] Total procesados: {n}")

        # Verificación rápida
        from sqlalchemy import func
        total_ventas = db.query(func.sum(DgiiIt1.ventas_gravadas)).filter_by(empresa_id=empresa.id).scalar()
        total_itbis  = db.query(func.sum(DgiiIt1.itbis_generado)).filter_by(empresa_id=empresa.id).scalar()
        total_credito= db.query(func.sum(DgiiIt1.itbis_credito)).filter_by(empresa_id=empresa.id).scalar()
        print(f"\n  Ventas Gravadas Totales IT-1:  RD$ {float(total_ventas or 0):>15,.2f}")
        print(f"  ITBIS Generado Total IT-1:     RD$ {float(total_itbis or 0):>15,.2f}")
        print(f"  ITBIS Crédito Total IT-1:      RD$ {float(total_credito or 0):>15,.2f}")
    finally:
        db.close()
