# Auditoría Técnica del Proyecto AiContaFiscalRD

## 1. Estructura del proyecto
Rutas relativas a `C:\GEMINI\AiContaFiscalRD\`:

*   `core/database.py`: Define el motor SQLite (WAL-mode), las 13 tablas del esquema ORM (SQLAlchemy) y utilidades de inicialización.
*   `core/etl_ingesta.py`: Pipeline principal de carga. Normaliza archivos 606/607 (TXT/CSV/Excel) de la DGII a la base de datos SQL.
*   `core/etl_cruce_terceros.py`: Algoritmo para contrastar NCFs registrados con los reportes de proveedores externos.
*   `core/etl_tss_ir13.py`: Extractor de hojas de empleados, contribuciones de Seguridad Social (TSS) y retenciones (IR-13).
*   `core/motor_clasificacion.py`: Asignador de cuentas contables vía inferencia de IA/Reglas estáticas para compras.
*   `core/motor_fiscal.py`: Cerebro relacional que consolida los estados financieros (Módulo 3) y ejecuta las reglas de auditoría BIG4 (Módulo 5).
*   `core/motor_riesgo_dgii.py`: Simulador heurístico que emite un semáforo (Verde, Amarillo, Rojo) evaluando el riesgo de fiscalización DGII según cruces.
*   `core/generador_anexo_b.py`: Consolida la matriz cruzada de tipos de bien/gastos exigida en el Anexo B del IR-2.
*   `core/generador_final.py`: Compilador para emitir los Estados Financieros en PDF (mediante plantillas TeX/LaTeX) y el form base en Excel.
*   `core/generador_ir2_oficial.py`: Script para hidratar la plantilla oficial de Excel de la DGII usando Python-openpyxl.
*   `api/main.py`: Orquestador HTTP (FastAPI) con todos los *endpoints* del motor (15 rutas configuradas).
*   `api/static/app.js`: Script principal del frontend con la lógica de envío de formularios híbridos (Archivos 606 + Textos).
*   `api/static/index.html`: UI Dashboard principal (Multitenant).
*   `api/static/cliente.html`: UI Expediente único de cliente.
*   `api/static/style.css`: Hojas de estilo generales.

## 2. Estado del ETL (parser 606/607)
**Ubicación:** `core/etl_ingesta.py`

*   **Campos que extrae (606):** RNC Proveedor, NCF, Fecha, Monto, ITBIS, Tipo de Bien. Calcula de forma automática: si el NCF es anulado (`monto < 0`), extrae prefijo/secuencia del NCF, y vincula una `cuenta_contable`.
*   **Campos que extrae (607):** RNC Cliente, NCF, Fecha, Monto Facturado, ITBIS Facturado, Monto Exento, Retención ISR, Retención ITBIS.
*   **Manejo numérico:** No usa `Decimal` inicialmente. Mapea la cadena (quitando comas) y fuerza un casteo a `float` usando la función `limpiar_monto()`. Al insertarlo a SQLite lo traduce a columna `Numeric(18,2)`.
*   **Manejo de registros malos (Dirty Data):** Usa bloques `try/except`. Si falla al buscar el RNC o al limpiar el texto, ignora la fila (hace `continue`) y suma 1 al contador interno `errores`. Se salta filas que no pertenecen al `anio_requerido` suministrado.
*   **Tests Unitarios:** **NO EXISTEN.** (0 cobertura de pruebas automatizadas aisladas).

## 3. Motor de auditoría / banderas
**Ubicación:** `core/motor_fiscal.py` mediante la función `anotar(id_cruce, nombre...)` de `ejecutar_auditoria_fiscal()`. Todas retornan métricas a la tabla `ValidacionFiscal`.

| # | Nombre de Regla | Condición Evaluada | Tolerancia | Estado de Implementación |
| :--- | :--- | :--- | :--- | :--- |
| **01** | Ventas 607 vs ER | Comprueba que las Ventas Netas del 607 coinciden con Total Ingreso - Exentas. | <= 50 pesos | OK / Funcionando |
| **02** | ITBIS Fac vs IT-1 | Cierre de IVA por pagar contra resúmenes anuales. | Estricta (0) | OK / Funcionando |
| **03** | Ventas Gravadas vs IT-1 | Ventas del 607 vs Acumulado de declaraciones juradas IT1 | <= 5,000 | OK / Funcionando |
| **04** | Ventas Exentas | Chequeo manual contra valores de exención pura | Estricta (0) | Parcial (Harcodeada a 0.0 vs Sistema) |
| **05** | Terceros vs 607 (Ventas) | Rastro DGII: Total compras declaradas por terceros hacia este RNC vs RNC emitidas | <= 30% dif | OK / Funcionando |
| **06** | Regla de Notas Credito | Notas de crédito > 20% de las ventas brutas alertan a la DGII. | <= Monto Total | Tolerancia amplia de testing actual |
| **07** | Compras 606 vs ER Gastos | Facturas 606 totales vs Gastos + Costos operativos del ER | <= 5,000 | Parcial (Resta valor duro harcodeado `2883081.00`) |
| **08** | ITBIS Compras vs IT-1 Cr. | ITBIS Adelantado en el 606 frente a Declarado. | Amplia | Incompleto |
| **11** | Compras vs Ventas | Costos > 90% de ingresos dispara auditorías por pérdida continua. | Muy Amplia | OK pero tolerancia no realista |
| **13** | Retenciones Nómina vs IR13 | Cuadre IR-13 Empleado | <= 10 | Funcionando. Falta extensión al formulario IR-17 |
| **14** | Retenciones Tarjetas | Confirmar % cobro adquirente Cardnet/Visanet. | <= 1 | Depende de excel paralelo, OK si archivo provisto |
| **15** | Margen Bruto Contable | Ventas totales - Costo Venta vs Utilidad estática. | <= 1 | OK / Funcionando |
| **16** | Tope Gastos Mágicos | Evita registros fuera de libros sin NCF de crédito fiscal válido. | Dinámica | OK / Funcionando |
| **17** | Depuración Gasto TSS | Valida Aporte Empresa vs TSS pagada real | <= 0.10 | OK / Funcionando |
| **18** | Consistencia Renta Imp. | Renta calculada en sistema vs renta declarada en anexo. | <= 1 | OK (Autorreferencial) |

## 4. Schema de la base de datos
**Motor de base de datos:** SQLite bajo configuración WAL (`sqlite:///...aicontafiscal_core.db`)
El DDL equivalente derivado del ORM:

```sql
CREATE TABLE padron_dgii (id INTEGER PRIMARY KEY, rnc VARCHAR(20) UNIQUE, razon_social VARCHAR(200), actividad_economica VARCHAR(300), fecha_inicio VARCHAR(20), estado VARCHAR(50), regimen_pago VARCHAR(100));
CREATE TABLE empresas (id INTEGER PRIMARY KEY, rnc VARCHAR(11) UNIQUE NOT NULL, nombre_empresa TEXT NOT NULL, direccion TEXT, telefono VARCHAR(20), email TEXT, fecha_creacion DATETIME);
CREATE TABLE dgii_606 (id INTEGER PRIMARY KEY, empresa_id INTEGER REFERENCES empresas, periodo VARCHAR(6), rnc_proveedor VARCHAR(11), tipo_identificacion INTEGER, ncf VARCHAR(19), ncf_modificado VARCHAR(19), fecha_comprobante DATE, fecha_pago DATE, tipo_bien_servicio INTEGER, monto_facturado NUMERIC(18,2), itbis_facturado NUMERIC(18,2), itbis_retenido NUMERIC(18,2), isr_retenido NUMERIC(18,2), monto_propina_legal NUMERIC(18,2), forma_pago INTEGER, anulada BOOLEAN, cuenta_contable VARCHAR(50), creado DATETIME);
CREATE TABLE dgii_607 (id INTEGER PRIMARY KEY, empresa_id INTEGER REFERENCES empresas, periodo VARCHAR(6), rnc_cliente VARCHAR(11), tipo_identificacion INTEGER, ncf VARCHAR(19), ncf_modificado VARCHAR(19), fecha_comprobante DATE, monto_facturado NUMERIC(18,2), itbis_facturado NUMERIC(18,2), monto_propina_legal NUMERIC(18,2), efectivo NUMERIC(18,2), cheque_transferencia NUMERIC(18,2), tarjeta_credito NUMERIC(18,2), credito NUMERIC(18,2), bonos_certificados NUMERIC(18,2), permuta NUMERIC(18,2), otras_formas NUMERIC(18,2), anulada BOOLEAN, monto_exento NUMERIC(18,2), retencion_isr NUMERIC(18,2), creado DATETIME);
CREATE TABLE dgii_it1 (id INTEGER PRIMARY KEY, empresa_id INTEGER REFERENCES empresas, periodo VARCHAR(6), ventas_gravadas NUMERIC(18,2), ventas_exentas NUMERIC(18,2), itbis_generado NUMERIC(18,2), compras_gravadas NUMERIC(18,2), itbis_credito NUMERIC(18,2), itbis_retenido_terceros NUMERIC(18,2), saldo_anterior NUMERIC(18,2), itbis_a_pagar NUMERIC(18,2), creado DATETIME);
CREATE TABLE clasificacion_fiscal (id INTEGER PRIMARY KEY, tipo_ncf VARCHAR(3), descripcion TEXT, tipo_operacion VARCHAR(20), cuenta_contable VARCHAR(50), categoria_fiscal VARCHAR(50), deducible BOOLEAN, aplica_itbis BOOLEAN);
CREATE TABLE activos (id INTEGER PRIMARY KEY, empresa_id INTEGER REFERENCES empresas, descripcion TEXT, categoria VARCHAR(50), fecha_compra DATE, valor_compra NUMERIC(18,2), vida_util INTEGER, tasa_depreciacion NUMERIC(5,2), depreciacion_acumulada NUMERIC(18,2), valor_libro NUMERIC(18,2), creado DATETIME);
CREATE TABLE inventarios (id INTEGER PRIMARY KEY, empresa_id INTEGER REFERENCES empresas, producto_codigo VARCHAR(50), descripcion TEXT, cantidad NUMERIC(18,2), costo_unitario NUMERIC(18,2), valor_total NUMERIC(18,2), fecha_registro DATE, tipo_inventario VARCHAR(20));
CREATE TABLE prestamos (id INTEGER PRIMARY KEY, empresa_id INTEGER REFERENCES empresas, entidad_financiera TEXT, numero_prestamo VARCHAR(50), fecha_inicio DATE, monto_original NUMERIC(18,2), saldo_actual NUMERIC(18,2), tasa_interes NUMERIC(6,3), cuota_mensual NUMERIC(18,2), intereses_pagados NUMERIC(18,2), creado DATETIME);
CREATE TABLE estados_financieros (id INTEGER PRIMARY KEY, empresa_id INTEGER REFERENCES empresas, periodo VARCHAR(6), ventas_totales NUMERIC(18,2), costo_ventas NUMERIC(18,2), gastos_operativos NUMERIC(18,2), utilidad_bruta NUMERIC(18,2), utilidad_neta NUMERIC(18,2), ventas_exentas NUMERIC(18,2), gastos_personal NUMERIC(18,2), isr_calcular NUMERIC(18,2), renta_imponible NUMERIC(18,2), anticipos NUMERIC(18,2), retenciones NUMERIC(18,2), isr_pagar NUMERIC(18,2), creado DATETIME);
CREATE TABLE validaciones_fiscales (id INTEGER PRIMARY KEY, empresa_id INTEGER REFERENCES empresas, periodo VARCHAR(6), tipo_validacion VARCHAR(50), valor_sistema NUMERIC(18,2), valor_dgii NUMERIC(18,2), diferencia NUMERIC(18,2), estado VARCHAR(20), creado DATETIME);
CREATE TABLE tss_nomina (id INTEGER PRIMARY KEY, empresa_id INTEGER REFERENCES empresas, periodo VARCHAR(6), empleados INTEGER, salario_cotizable NUMERIC(18,2), aporte_empresa NUMERIC(18,2));
CREATE TABLE ir18_retenciones (id INTEGER PRIMARY KEY, empresa_id INTEGER REFERENCES empresas, empleado VARCHAR(200), cedula VARCHAR(11), salario NUMERIC(18,2), retencion_isr NUMERIC(18,2));
```

## 5. API endpoints
FastAPI implementa 15 endpoints en `api/main.py`:

*   **GET `/`** -> Retorna el `index.html` estático del Frontend.
*   **GET `/api/health`** -> Check de vida (ping).
*   **GET `/api/clientes`** -> Lista clientes (Empresas) y estadísticas.
*   **POST `/api/clientes`** -> Crea nueva empresa/SaaS Tenant y genera la estructura de carpetas `base_dir`.
*   **GET `/cliente/{cliente_id}`** -> Interfaz HTML individual para cliente específico.
*   **GET `/api/clientes/{cliente_id}`** -> JSON datos empresa unificada.
*   **GET `/api/padron/buscar/`** -> Busca en tabla `PadronDGII` con limit 10 (Autocomplete).
*   **POST `/api/resumen_archivos/{tipo}`** -> Ingiere archivos temporales (Dropzone) y da totales instantáneos rechazando años erróneos.
*   **POST `/api/procesar_rapido/{cliente_id}/{periodo}`** -> Fake/Mock para testear dashboard.
*   **GET `/api/generar_ir2_oficial/{rnc}/{anio}`** -> Exporta directamente el xls de la DGII hidratado.
*   **POST `/api/parse_ir2_anterior`** -> Ingiere PDFs para extraer data anterior.
*   **POST `/api/procesar`** -> **ENDPOINT CORE:** Recibe variables, lee archivos, carga en sqlite, procesa estados financieros y corre la auditoría general.
*   **GET `/api/riesgo`** -> Retorna payload semáforo rojo/verde.
*   **POST `/api/generar_ef`** -> Emite solo reporte LaTeX Financiero en PDF.
*   **GET `/api/anexo_b`** -> Extrae gastos categorizados para popular formulario DGII Anexo B.
*   **GET `/api/descargar/{filename}`** -> Sirve descargas genéricas del `data/output`.

## 6. Lo que NO funciona (Alertas y Deuda Técnica)
*   **Ausencia Absoluta de Tests:** Cero `pytest`, cero `unittest` implementados.
*   **Carencia del IR-17:** La auditoría flaggea requerir comparar IR-13, pero `"En el futuro contrastar IR-17"` aparece en los TODOs.
*   **Exenciones y Depreciaciones Hardcodeadas:** Módulo de ingresos exentos y ajustes por depreciación en el IR-2 dependen de recolecciones manuales estáticas en algunos componentes.

## 9. Registro de Cambios
Consultar el archivo [BITACORA.md](file:///c:/GEMINI/AiContaFiscalRD/BITACORA.md) para ver el historial detallado de avances y sesiones de desarrollo.


## 7. Dependencies
El proyecto carece de archivo de versionamiento `requirements.txt` o manejo virtual de dependencias explícito, lo cual es de altísimo riesgo en producción. Dependencias requeridas identificadas por inspección de imports:
```text
fastapi
uvicorn
sqlalchemy
pandas
openpyxl
lxml (usada por pandas.read_html para leer excel corruptos)
python-multipart (necesaria para FastAPI Forms)
```

## 8. Muestra de datos
Extraído del archivo de muestra real en producción: `C:\GEMINI\AiContaFiscalRD\data\clientes\130826552\01_Formatos_606_607\DGII_F_606_130826552_202501.TXT`

```text
606|130826552|202501|5
101801875|1|02|E310000143013||20250120||4474.43||4474.43|800.57||||800.57||||||||03
101019921|1|02|B0119590068||20250110||5742.75||5742.75|702.91||||702.91||||||||03
101602465|1|02|E310006668652||20250124||4711||4711|419.21||||419.21||||||||03
132522885|1|02|E310000001879||20250118||7764.9||7764.9|1270.62||||1270.62||||||||03
```
