#!/usr/bin/env python
"""
Migración SQLite → PostgreSQL para AiContaFiscalRD.
====================================================
Uso:
    python scripts/migrar_a_postgresql.py          # Migra datos de SQLite a PostgreSQL
    python scripts/migrar_a_postgresql.py --export  # Solo exporta SQLite a JSON (backup)

Requiere DATABASE_URL en .env apuntando a Supabase PostgreSQL.
"""
import sys, os, json, argparse
from datetime import date, datetime
from decimal import Decimal

# Asegurar que el proyecto está en el path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)

from core.database import (
    Base, engine as engine_sqlite, SessionLocal as SessionSQLite,
    _ENGINE, DATABASE_URL
)
from sqlalchemy import inspect, text


# ─── Serializador JSON para tipos especiales ────────────────────
class FiscalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


# ─── Paso 1: Exportar SQLite a JSON ────────────────────────────
def exportar_sqlite(output_path: str) -> dict:
    """Lee todas las tablas desde SQLite y las exporta a un dict."""
    # Forzar engine SQLite conectándose directo al archivo
    from sqlalchemy import create_engine
    db_path = os.path.join(BASE_DIR, "data", "aicontafiscal_core.db")
    if not os.path.exists(db_path):
        print(f"[!] No se encontró BD SQLite en: {db_path}")
        return None

    engine_src = create_engine(f"sqlite:///{db_path}")
    db = SessionSQLite(bind=engine_src)

    tablas = [
        "empresas", "dgii_606", "dgii_607", "dgii_it1", "dgii_ir17",
        "activos", "inventarios", "prestamos", "estados_financieros",
        "validaciones_fiscales", "tss_nomina", "ir18_retenciones",
        "socios", "clasificacion_fiscal", "padron_dgii",
        "planificacion_scenarios"
    ]

    data = {}
    for tabla in tablas:
        rows = db.execute(text(f"SELECT * FROM \"{tabla}\"")).fetchall()
        columns = [col["name"] for col in inspect(engine_src).get_columns(tabla)]
        records = [dict(zip(columns, row)) for row in rows]
        data[tabla] = records
        print(f"  [SQLite] {tabla}: {len(records)} registros")

    db.close()

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, cls=FiscalEncoder, ensure_ascii=False, indent=2)

    print(f"\n✅ Exportación completada: {output_path}")
    return data


# ─── Paso 2: Importar a PostgreSQL ─────────────────────────────
def importar_a_postgresql(data: dict):
    """Inserta los datos exportados en PostgreSQL vía SQLAlchemy."""
    from core.database import engine as engine_pg, SessionLocal as SessionPG

    # Verificar que estamos en PostgreSQL
    if _ENGINE != "postgresql":
        # Forzar conexión PostgreSQL desde DATABASE_URL
        print(f"\n[!] No hay DATABASE_URL configurada. Usando SQLite como destino.")
        print("    Configurala en .env para migrar a PostgreSQL.")
        return False

    print(f"\n{'='*60}")
    print(f"  Conectando a PostgreSQL: {DATABASE_URL[:50]}...")
    print(f"{'='*60}")

    # Crear tablas (idempotente)
    Base.metadata.create_all(bind=engine_pg)
    print("  [PG] Tablas creadas/verificadas.")

    db = SessionPG()

    # Mapa de modelos para inserción
    from core.database import (
        Empresa, Dgii606, Dgii607, DgiiIt1, DgiiIr17,
        ActivoFijo, Inventario, Prestamo, EstadoFinanciero,
        ValidacionFiscal, TssNomina, Ir18Retenciones, Socio,
        ClasificacionFiscal, PadronDGII, PlanificacionScenario
    )
    MODELOS = {
        "padron_dgii": PadronDGII,
        "empresas": Empresa,
        "dgii_606": Dgii606,
        "dgii_607": Dgii607,
        "dgii_it1": DgiiIt1,
        "dgii_ir17": DgiiIr17,
        "activos": ActivoFijo,
        "inventarios": Inventario,
        "prestamos": Prestamo,
        "estados_financieros": EstadoFinanciero,
        "validaciones_fiscales": ValidacionFiscal,
        "tss_nomina": TssNomina,
        "ir18_retenciones": Ir18Retenciones,
        "socios": Socio,
        "clasificacion_fiscal": ClasificacionFiscal,
        "planificacion_scenarios": PlanificacionScenario,
    }

    total = 0
    for tabla, records in data.items():
        if not records:
            continue
        modelo = MODELOS.get(tabla)
        if not modelo:
            print(f"  [?] {tabla}: sin modelo, saltando")
            continue

        # Limpiar destino
        db.query(modelo).delete()
        db.flush()

        # Insertar en lotes (evita memory overflow con miles de registros)
        batch = []
        for r in records:
            # Filtrar solo columnas que existen en el modelo
            clean = {k: v for k, v in r.items()
                     if hasattr(modelo, k) and v is not None}
            batch.append(modelo(**clean))

            if len(batch) >= 500:
                db.add_all(batch)
                db.commit()
                total += len(batch)
                batch = []

        if batch:
            db.add_all(batch)
            db.commit()
            total += len(batch)

        print(f"  [PG] {tabla}: {len(records)} registros insertados")

    db.close()
    print(f"\n✅ Migración completada: {total} registros migrados a PostgreSQL.")
    return True


# ─── Main ──────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrar datos de SQLite a PostgreSQL")
    parser.add_argument("--export", action="store_true", help="Solo exportar SQLite a JSON")
    parser.add_argument("--output", default="data/migracion_backup.json",
                        help="Archivo de salida para exportación (default: data/migracion_backup.json)")
    args = parser.parse_args()

    print("=" * 60)
    print("  AiContaFiscalRD — Migración SQLite → PostgreSQL")
    print("=" * 60)

    output_path = os.path.join(BASE_DIR, args.output)

    # 1. Exportar desde SQLite
    data = exportar_sqlite(output_path)
    if data is None:
        sys.exit(1)

    # 2. Si es solo export, terminar
    if args.export:
        print("\n✅ Exportación completada. Para migrar, ejecuta sin --export")
        sys.exit(0)

    # 3. Importar a PostgreSQL
    importar_a_postgresql(data)
