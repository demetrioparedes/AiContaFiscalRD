# Memoria de Optimización — AiContaFiscalRD

**Versión:** 1.0 | **Fecha:** 2026-06-10/11
**Analista:** Claude Code (Solución Architect)
**Repositorio:** https://github.com/demetrioparedes/AiContaFiscalRD

---

## Índice

1. [Resumen Ejecutivo](#1-resumen-ejecutivo)
2. [Línea Base (antes)](#2-línea-base-antes)
3. [Bloque 1: Rutas Absolutas y Portabilidad](#3-bloque-1-rutas-absolutas-y-portabilidad)
4. [Bloque 2: Tests Automatizados](#4-bloque-2-tests-automatizados)
5. [Bloque 3: Base de Datos Dual (SQLite + PostgreSQL)](#5-bloque-3-base-de-datos-dual-sqlite--postgresql)
6. [Bloque 4: Migración de Datos](#6-bloque-4-migración-de-datos)
7. [Bloque 5: BackgroundTasks (Pipeline Async)](#7-bloque-5-backgroundtasks-pipeline-async)
8. [Bloque 6: Paginación en API](#8-bloque-6-paginación-en-api)
9. [Bloque 7: Planificador Fiscal](#9-bloque-7-planificador-fiscal)
10. [Bloque 8: Clasificación de Gastos Expandida](#10-bloque-8-clasificación-de-gastos-expandida)
11. [Bloque 9: Seguridad (API Key)](#11-bloque-9-seguridad-api-key)
12. [Bloque 10: Frontend Separado](#12-bloque-10-frontend-separado)
13. [Bloque 11: ETL Restringido](#13-bloque-11-etl-restringido)
14. [Bloque 12: Corrección Motor de Auditoría](#14-bloque-12-corrección-motor-de-auditoría)
15. [Bloque 13: Deploy en Render.com](#15-bloque-13-deploy-en-rendercom)
16. [Estado Final](#16-estado-final)
17. [Próximos Pasos Recomendados](#17-próximos-pasos-recomendados)

---

## 1. Resumen Ejecutivo

AiContaFiscalRD pasó de ser un proyecto funcional pero **atado a una máquina específica con deuda técnica crítica** a un sistema **portable, testeado, escalable y listo para producción en la nube**.

### Logros clave

| Métrica | Antes | Después |
|---------|-------|---------|
| Tests pasando | 0 (errores de import) | 27/27 (SQLite + PostgreSQL) |
| Rutas absolutas hardcodeadas | 17+ archivos | 0 |
| Base de datos | SQLite (sin concurrencia) | SQLite + PostgreSQL dual (auto-detect) |
| Registros migrados | — | 773,636 (SQLite → PostgreSQL) |
| Pipeline | Síncrono (timeout) | Async + BackgroundTasks + polling |
| API clientes | Sin paginación | page/per_page/total/pages |
| Planificador fiscal | No existía | Proyecciones + 3 escenarios + Art. 314 |
| Frontend | 1736 líneas monolíticas | 306 líneas + 2 assets externos |
| RNCs clasificados | ~70 | 150+ (18 categorías) |
| Repositorio | Local | GitHub público |
| Deploy | Localhost | Preparado para Render.com |

---

## 2. Línea Base (antes)

### Problemas detectados al inicio

```
CRITICOS:
  - Rutas absolutas hardcodeadas en 17+ archivos (sys.path.insert con r"c:\GEMINI\...")
  - 0 tests funcionales (8 errores de import, 4 tests con API rota)
  - core/__init__.py no configuraba sys.path (ModuleNotFoundError en cascada)
  - API key hardcodeada con fallback en main.py
  - Pipeline POST /api/procesar sincrónico (timeout en prod)

ALTOS:
  - ETL hacía os.walk sobre TODO el directorio del cliente (procesaba nóminas como facturas)
  - 4 tests importaban funciones refactorizadas dentro de clases (API antigua)
  - 2+ endpoints de IR-2 compitiendo, algunos con métodos que no existen
  - motor_fiscal.py importaba planificador_fiscal.py que nunca fue creado
  - auditoria_experta.py referenciaba ef.ventas (inexistente) en vez de ef.ventas_totales

MEDIOS:
  - Frontend index.html de 1736 líneas con CSS+JS embebidos
  - RNC_CONOCIDOS con solo ~70 entradas
  - Sin paginación en endpoints de listado
  - seguridad: security_shield_test.py hardcodeaba API key
```

---

## 3. Bloque 1: Rutas Absolutas y Portabilidad

### Problema

17 archivos usaban `sys.path.insert(0, r"c:\GEMINI\AiContaFiscalRD\core")` o rutas absolutas como `r"G:\Mi unidad\Backup NAS\..."`. El proyecto no podía ejecutarse en otra máquina.

### Solución

**3.1.** `core/__init__.py` — Configuración central de sys.path:

```python
_core_dir = os.path.dirname(os.path.abspath(__file__))
if _core_dir not in sys.path:
    sys.path.insert(0, _core_dir)
BASE_DIR = os.path.dirname(_core_dir)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
```

**3.2.** Archivos corregidos (17):

| Archivo | Cambio |
|---------|--------|
| `core/etl_cruce_terceros.py` | sys.path absoluto → dinámico + BASE_ELVIRA eliminado |
| `core/etl_tss_ir13.py` | sys.path absoluto → dinámico |
| `core/etl_it1.py` | sys.path absoluto → dinámico |
| `core/etl_analisis_it1.py` | sys.path absoluto → dinámico + ruta test relativa |
| `core/motor_riesgo_dgii.py` | sys.path absoluto → dinámico |
| `core/generador_final.py` | sys.path absoluto → dinámico + OUTPUT_DIR relativo |
| `core/generador_ir17_reporte.py` | sys.path absoluto → dinámico + OUTPUT_DIR relativo |
| `core/generador_anexo_b.py` | sys.path absoluto → dinámico |
| `core/generador_ir2_oficial.py` | Fallback ruta usuario eliminado |
| `core/seed_maestras.py` | sys.path absoluto → dinámico |
| `core/etl_ir17.py` | `from core.database` → `from database` |
| `core/validador_rnc.py` | `from core.database` → `from database` |
| `core/motor_beneficiario_final.py` | `from core.database` → `from database` |
| `core/utils/importador_socios.py` | Ruta absoluta template → relativa |
| `core/utils/generate_template.py` | Ruta absoluta output → relativa |
| `test_humo.py` | sys.path absoluto → dinámico |
| `test_report.py` | sys.path absoluto → dinámico |
| `test_visual_report.py` | sys.path absoluto → dinámico |

---

## 4. Bloque 2: Tests Automatizados

### Problema

0 tests funcionales. 8 errores de import, 4 tests con API rota (importaban funciones refactorizadas dentro de clases).

### Solución

**4.1.** Tests reescritos para usar API de clases moderna:

| Test | Antes | Después |
|------|-------|---------|
| `test_activos_fijos.py` | `from motor_activos import calcular_depreciacion_anual` (no existe) | `MotorActivosFijos(db, id, anio).calcular_depreciacion_anual()` |
| `test_inventario.py` | `from motor_inventario import calcular_costo_ventas` (no existe) | `MotorInventario(db, id, anio).calcular_costo_ventas()` |
| `test_auditoria_socio.py` | `from motor_fiscal import calcular_estado_resultados` (no existe) | `OrquestadorFiscal(db, rnc, anio).ejecutar_auditoria_fiscal_completa()` |
| `test_maestro_fiscal.py` | `from motor_fiscal import calcular_estado_resultados` (no existe) | `OrquestadorFiscal(db, rnc, anio).ejecutar_auditoria_fiscal_completa()` |

**4.2.** Importaciones corregidas: `from database` → `from core.database` en 4 tests.

**4.3.** `security_shield_test.py` — usa `pytest.importorskip("requests")` en vez de fallar si no está instalado.

**4.4.** `limpiar_monto()` — ahora maneja `NaN` e `Inf` como `0.00`.

### Resultado

```
27 passed, 1 skipped  ✅  (3.19s SQLite | 5.84s PostgreSQL)
```

---

## 5. Bloque 3: Base de Datos Dual (SQLite + PostgreSQL)

### Problema

El proyecto usaba SQLite exclusivamente: sin concurrencia real, sin backups, sin RLS, no escalable.

### Solución

`core/database.py` — Motor dual con auto-detección:

```python
_DATABASE_URL_ENV = os.getenv("DATABASE_URL", "").strip()
if _DATABASE_URL_ENV:
    DATABASE_URL = _DATABASE_URL_ENV
    _ENGINE = "postgresql"
    # Pool size 5, max_overflow 10, SSL require, connect_timeout 10
else:
    DATABASE_URL = f"sqlite:///{_DB_PATH}"
    _ENGINE = "sqlite"
    # check_same_thread=False, timeout=30, WAL mode
```

**Comportamiento:**
- Si `DATABASE_URL` está definida en `.env` → PostgreSQL (con pool de conexiones)
- Si no → SQLite local (WAL mode, como antes)
- Mismo código SQLAlchemy, misma lógica, mismo ORM

### Archivos creados

| Archivo | Propósito |
|---------|-----------|
| `scripts/migrar_a_postgresql.py` | Script unificado: exporta SQLite → JSON → importa a PostgreSQL |
| `scripts/exportar_sqlite.py` | Exporta datos de SQLite a JSON (backup) |
| `scripts/importar_a_postgresql.py` | Importa datos de JSON a PostgreSQL (batch de 500, casteo booleano) |

### Dependencias

`requirements.txt` actualizado con `psycopg2-binary>=2.9.9`.

---

## 6. Bloque 4: Migración de Datos

### Ejecución

```
SQLite → Exportación a JSON (773,636 registros) → Importación a PostgreSQL (Supabase)

Tablas migradas:
  empresas:               9
  padron_dgii:          767,421
  dgii_606:                651
  dgii_607:                500
  dgii_it1:                 13
  activos:                   5
  inventarios:               4
  prestamos:                 1
  estados_financieros:      15
  validaciones_fiscales: 4,830
  tss_nomina:              179
  ir18_retenciones:          1
  socios:                    5
  planificacion_scenarios:   2
  ---
  TOTAL:              773,636 registros ✅
```

### Lección técnica

SQLite guarda booleanos como `0`/`1` (enteros). PostgreSQL requiere `true`/`false`. Se resolvió con casteo explícito durante la migración de `dgii_606.anulada`, `dgii_607.anulada`, `socios.es_persona_fisica`, `socios.es_beneficiario_final`, y `socios.rnc_bloqueado`.

### Verificación

- Tests 27/27 pasan contra PostgreSQL
- Smoke test: Health, Paginación, Riesgo DGII (23% VERDE), Anexo B — todo OK
- Riesgo DGII para cliente 130826552: consistente pre/post migración

---

## 7. Bloque 5: BackgroundTasks (Pipeline Async)

### Problema

`POST /api/procesar` ejecutaba TODO el pipeline (ETL → TSS → motor fiscal → cruce terceros → riesgo → entregables) de forma sincrónica. Con un cliente de 20k facturas, podía tomar 2-5 minutos y causar timeout.

### Solución

**7.1.** Task Store en memoria:

```python
_tasks: dict = {}
_create_task(task_type) → task_id
_update_task(task_id, status, progress, result)
_get_task(task_id) → task state
```

**7.2.** Endpoint `POST /api/procesar` modificado:
- Guarda archivos (rápido, sync)
- Crea un `task_id`
- Delega el pipeline a `background_tasks.add_task(_ejecutar_pipeline, task_id, config)`
- Devuelve `{"task_id": "abc123", "status": "processing"}` inmediatamente

**7.3.** Nuevo endpoint `GET /api/tasks/{task_id}`:
- Permite al frontend hacer polling del progreso
- Devuelve `status` (processing/completed/error), `progress` (texto), `result` (datos finales)

**7.4.** `_ejecutar_pipeline()` — corre en background, actualiza `_update_task()` en cada paso.

---

## 8. Bloque 6: Paginación en API

### Problema

`GET /api/clientes` devolvía **todos** los clientes sin límite. Con el tiempo, esto rompe el frontend y la red.

### Solución

```python
@app.get("/api/clientes")
async def listar_clientes(page: int = 1, per_page: int = 20, ...):
    total = db.query(Empresa).count()
    offset = (max(1, page) - 1) * per_page
    clientes = db.query(Empresa).order_by(Empresa.id.desc()).offset(offset).limit(per_page).all()
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
        "clientes": [...],
        "stats": {...}
    }
```

---

## 9. Bloque 7: Planificador Fiscal

### Problema

`motor_fiscal.py` (Fase 9) importaba `from planificador_fiscal import PlanificadorIA` pero el módulo nunca fue creado. Causaba `ModuleNotFoundError` en cada pipeline.

### Solución

**9.1.** `core/planificador_fiscal.py` creado con:

| Componente | Descripción |
|-----------|-------------|
| `PlanificadorIA.proyectar_cierre_anual()` | Proyección basada en tendencia histórica (últimos 3 períodos) |
| `PlanificadorIA._escenario_base()` | Escenario base cuando no hay histórico |
| `PlanificadorIA.actualizar_planificacion_db()` | Guarda escenario en `planificacion_scenarios` |
| `PlanificadorIA.generar_escenarios()` | 3 escenarios: BASE, OPTIMISTA (+15%), PESIMISTA (-10%) |
| Cálculo de anticipos Art. 314 | 1% de ingresos brutos (Código Tributario RD) |

**9.2.** Import condicional en `motor_fiscal.py`:

```python
try:
    from planificador_fiscal import PlanificadorIA
    planificador = PlanificadorIA(self.db, self.empresa_id, self.anio_fiscal)
    ...
except ImportError:
    resultados["proyeccion_ia"] = {"error": "Módulo no disponible"}
```

---

## 10. Bloque 8: Clasificación de Gastos Expandida

### Problema

`RNC_CONOCIDOS` tenía ~70 entradas en 11 categorías. Muchos proveedores caían en "sin_clasificar".

### Solución

**Nivel 1 (RNC exacto):** Expandido de ~70 a **150+ RNCs** en **18 categorías**:

```
Agregados: Banco Caribe, Vimenca, Promerica, Atlántico,
           Palic, Global, Patria, APAP,
           Farmacia Carol, Hormigo, Aqua,
           Constructora Norberto Odebrecht, Santiago,
           Ferretería Americana, Ocho,
           Transporte Segura, Motores Delcio,
           Hoteles Jardín, Intercontinental, Puntacana,
           PUCMM, UNIBE, INTEC, APEC,
           Listín Diario, Diario Libre, Telemicro
```

**Nivel 2 (Semántica):** 2 nuevas categorías:

```python
"Salud y Farmacia": ["FARMACIA", "CLINICA", "HOSPITAL", "MEDICO", ...],
"Educación y Capacitación": ["COLEGIO", "ESCUELA", "UNIVERSIDAD", ...]
```

Y expandidas las existentes:
```python
"Dietas y Gastos de Viaje": agregados "PIZZA", "COMIDA", "VIATICO"
"Publicidad y Mercadeo": agregados "DISENO", "CREATIVO", "AGENCIA"
```

---

## 11. Bloque 9: Seguridad (API Key)

### Problema

```python
secret = os.getenv("API_SECRET_KEY", "AiConta_Secure_Key_2026_RD")
```

Si no había `.env`, el servidor usaba una clave hardcodeada pública.

### Solución

```python
secret = os.getenv("API_SECRET_KEY")
if not secret:
    raise HTTPException(status_code=500, detail="Error de configuración del servidor.")
```

Sin `API_SECRET_KEY` en `.env`, el servidor rechaza **todas** las requests con error 500. No hay fallback.

---

## 12. Bloque 10: Frontend Separado

### Problema

`index.html` tenía **1,736 líneas** con 675 líneas de CSS embebido y 729 líneas de JS embebido. Imposible de mantener, sin cacheo, sin separación de concerns.

### Solución

| Archivo | Líneas | Contenido |
|---------|--------|-----------|
| `api/static/index.html` | **306** | Solo estructura HTML (head, body, divs) |
| `api/static/style.css` | **675** | Design system completo (extraído) |
| `api/static/dashboard.js` | **730** | Lógica del dashboard (extraída) |
| `api/static/app.js` | 894 | Lógica de cliente (existente, sin cambios) |

**Estructura final del frontend:**

```
api/static/
├── index.html       (306 lines)  →  HTML puro, references a CSS/JS externos
├── style.css        (675 lines)  →  Design tokens, layout, componentes
├── dashboard.js     (730 lines)  →  Lógica de dashboard, chat, voice
├── app.js           (894 lines)  →  Lógica de cliente (API calls)
├── cliente.html     (666 lines)  →  UI de expediente de cliente
└── style.css        (existente)  →  (reemplazado por el nuevo)
```

---

## 13. Bloque 11: ETL Restringido

### Problema

El ETL usaba `os.walk` sobre **todo** el directorio del cliente, procesando archivos de nóminas (`02_Nominas_TSS`), logs (`05_Auditoria_Logs`) y entregables (`06_Entregables_IR2_PDF`) como si fueran facturas 606/607.

### Solución

```python
# Antes:
for root, d_names, f_names in os.walk(directorio_empresa):

# Después:
subcarpetas = [
    os.path.join(directorio_empresa, "01_Formatos_606_607"),
    os.path.join(directorio_empresa, "04_Declaraciones_Anteriores"),
]
for carpeta in subcarpetas:
    if os.path.exists(carpeta):
        for root, d_names, f_names in os.walk(carpeta):
            ...
```

---

## 14. Bloque 12: Corrección Motor de Auditoría

### Problema

`auditoria_experta.py` línea 168 referenciaba `ef.ventas` pero el modelo `EstadoFinanciero` no tiene ese campo (es `ef.ventas_totales`).

### Solución

```python
# Antes:
ingresos_brutos = float(ef.ventas) if ef and ef.ventas else 0.0

# Después:
ingresos_brutos = float(ef.ventas_totales) if ef and ef.ventas_totales else 0.0
```

---

## 15. Bloque 13: Deploy en Render.com

### Archivos creados

**`render.yaml`** — Configuración oficial para Render:

```yaml
services:
  - type: web
    name: aicontafiscalrd-api
    runtime: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn api.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: PYTHON_VERSION
        value: 3.13.0
      - key: API_SECRET_KEY
        sync: false
      - key: DATABASE_URL
        sync: false
```

**`RENDER_DEPLOY.md`** — Guía paso a paso para hacer deploy.

**`README.md`** — Actualizado (README original existente).

**Repositorio:** https://github.com/demetrioparedes/AiContaFiscalRD

---

## 16. Estado Final

### Archivos modificados (35)

```
api/main.py, api/static/index.html, api/static/style.css, api/static/app.js,
core/__init__.py, core/database.py, core/auditoria_experta.py,
core/etl_analisis_it1.py, core/etl_cruce_terceros.py, core/etl_ingesta.py,
core/etl_ir17.py, core/etl_it1.py, core/etl_tss_ir13.py,
core/generador_anexo_b.py, core/generador_final.py,
core/generador_ir17_reporte.py, core/generador_ir2_oficial.py,
core/motor_activos.py, core/motor_beneficiario_final.py,
core/motor_clasificacion.py, core/motor_fiscal.py,
core/motor_riesgo_dgii.py, core/seed_maestras.py,
core/utils/generate_template.py, core/utils/importador_socios.py,
core/validador_rnc.py,
test_humo.py, test_report.py, test_visual_report.py,
tests/security_shield_test.py, tests/test_activos_fijos.py,
tests/test_auditoria_socio.py, tests/test_beneficiario_final.py,
tests/test_inventario.py, tests/test_maestro_fiscal.py
```

### Archivos creados (9)

```
core/planificador_fiscal.py
api/static/dashboard.js
scripts/migrar_a_postgresql.py
scripts/exportar_sqlite.py
scripts/importar_a_postgresql.py
render.yaml
RENDER_DEPLOY.md
docs/MEMORIA_OPTIMIZACION.md
.env.example
```

### Línea base final

```
Tests:     27 passed, 1 skipped  ✅
Sintaxis:  main.py, planificador, migración OK  ✅
Frontend:  index.html 306 líneas, 3 assets externos  ✅
DB:        SQLite (local) / PostgreSQL (Supabase) — mismo código  ✅
Datos:     773,636 registros migrados a PostgreSQL  ✅
API:       Paginación, BackgroundTasks, seguridad  ✅
Repositorio: GitHub público  ✅
Deploy:    Preparado para Render.com  ✅
```

---

## 17. Próximos Pasos Recomendados

| Prioridad | Tarea | Archivos | Esfuerzo |
|-----------|-------|----------|----------|
| 🔴 | **Deploy en Render.com** | Dashboard Render | 5 min |
| 🔴 | **Fix IR-17 warning** (`NoneType + NoneType`) | `core/etl_ir17.py` | 10 min |
| 🟠 | **Pipeline real con cliente completo** | Verificar POST /api/procesar async | 1-2h |
| 🟠 | **Conectar planificador al frontend** | `dashboard.js` + endpoint | 2-3h |
| 🟡 | **IR-17 Visual Report endpoint** | `generador_ir17_reporte.py` + API | 1h |
| 🟡 | **Tests de integración del pipeline completo** | `tests/test_integracion.py` | 3-4h |
| 🔵 | **Integración bancaria API (Cardnet/Visanet)** | Módulo nuevo | 1 semana |

---

*Documento generado el 2026-06-11 como parte de la sesión de optimización integral.*
