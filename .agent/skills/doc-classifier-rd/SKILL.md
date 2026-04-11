---
name: doc-classifier-rd
description: Clasifica y extrae información de documentos fiscales dominicanos (Formatos 606, 607, Anexos, Facturas).
---

# doc-classifier-rd (El Archivista)

Este Skill es utilizado por el Sub-Agente Archivista. Su propósito principal es tomar documentos crudos y convertirlos en datos estructurados.

## Instrucciones del Skill
1. Recorre la carpeta `data/raw/`.
2. Para cada archivo, evalúa su tipo de contenido:
   - **Excel**: Usa pandas/openpyxl para extraer las filas. Identifica si es un reporte 606, 607, de análisis de costo o de estado de resultados.
   - **PDF (Texto)**: Extrae tablas de compras/ventas utilizando herramientas de extracción de tablas en Python (ej. `pdfplumber`).
   - **Imágenes/PDF (Escaneado)**: Activa el motor OCR integrado.
3. Clasifica la información bajo un esquema estandarizado (RNC, Fecha, NCF, Monto, ITBIS).
4. Guarda cada archivo procesado como un `.json` descriptivo dentro de `data/extracted/` (ej. `datos_607.json`, `balance_inicial_2024.json`).
5. Devuelve un resumen de los archivos procesados con éxito y aquellos que tuvieron errores de lectura.
