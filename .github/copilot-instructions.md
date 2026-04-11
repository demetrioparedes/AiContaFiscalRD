# Project Guidelines

## Code Style
- Use `Decimal` type for all fiscal monetary values, never `float`. Reference [core/etl_ingesta.py](core/etl_ingesta.py) for `limpiar_monto()` function.
- Follow fuzzy file parsing pattern: accept multiple column name aliases, use try/except for robust parsing.
- NCF format: `[A-Z]{1}[0-9]{2}[0-9]{8}` (e.g., `B0100000001`).
- Use class-based orchestrators for major processors.

## Architecture
Multi-layered processing pipeline: ETL Ingesta → Motor Clasificación → Motor Inventario → Motor Activos → Auditoria Retenciones → Auditoria Experta → Motor Beneficiario Final → Motor Riesgo DGII → Generador Final.

SaaS multi-tenant model with `empresa_id` FK isolation.

SQLite database with WAL mode and concurrency protection.

## Build and Test
- Startup: `python -m uvicorn api.main:app --host 0.0.0.0 --port 8000` or `iniciar.bat`
- Full pipeline: `python core/run_pipeline.py` (interactive) or `python core/run_pipeline.py --config config_elvira_2025.json`
- Test: `pytest tests/ -v`
- Database init: `python core/database.py`

## Conventions
- Period format: Monthly `YYYYMM`, Annual `YYYY`.
- Validation framework: All audit findings persist in `validaciones_fiscales` table.
- Recursive beneficial ownership resolution for H-1/H-2 annexes.

See [docs/CONOCIMIENTO_FISCAL_MAESTRO.md](docs/CONOCIMIENTO_FISCAL_MAESTRO.md) for tax law reference, [docs/GUIA_SOCIO_EXPERTO_FISCAL_RD.md](docs/GUIA_SOCIO_EXPERTO_FISCAL_RD.md) for compliance guide, [PROJECT_AUDIT.md](PROJECT_AUDIT.md) for technical overview.