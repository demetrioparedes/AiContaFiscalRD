"""
Exporta datos de SQLite a JSON para migración a PostgreSQL.
"""
import sys, os, json
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

from sqlalchemy import create_engine, inspect
from datetime import date, datetime
from decimal import Decimal

DB_PATH = "C:/GEMINI/AiContaFiscalRD/data/aicontafiscal_core.db"
engine_src = create_engine(f"sqlite:///{DB_PATH}")

from sqlalchemy.orm import sessionmaker
Session = sessionmaker(bind=engine_src)
db_src = Session()

TABLAS = [
    "empresas", "padron_dgii", "dgii_606", "dgii_607", "dgii_it1", "dgii_ir17",
    "clasificacion_fiscal", "activos", "inventarios", "prestamos",
    "estados_financieros", "validaciones_fiscales", "tss_nomina",
    "ir18_retenciones", "socios", "planificacion_scenarios"
]

class FiscalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

export = {}
total = 0
for tabla in TABLAS:
    inspector = inspect(engine_src)
    try:
        columns = [col["name"] for col in inspector.get_columns(tabla)]
    except:
        print(f"  [!] Tabla {tabla} no existe en SQLite, saltando")
        continue

    from sqlalchemy import text
    rows = db_src.execute(text(f'SELECT * FROM "{tabla}"')).fetchall()
    records = []
    for row in rows:
        r = {}
        for i, col in enumerate(columns):
            val = row[i]
            if val is not None:
                r[col] = val
        records.append(r)
    export[tabla] = records
    total += len(records)
    print(f"  [SQLite] {tabla}: {len(records)} registros")

db_src.close()

output = "C:/GEMINI/AiContaFiscalRD/data/migracion_backup.json"
with open(output, "w", encoding="utf-8") as f:
    json.dump(export, f, cls=FiscalEncoder, ensure_ascii=False, indent=2)

print(f"\n[OK] Exportacion completada: {output}")
print(f"[OK] Total registros: {total}")
