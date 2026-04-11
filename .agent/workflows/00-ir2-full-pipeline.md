---
description: Flujo orquestador para la reconstrucción contable-fiscal IR-2 (República Dominicana)
---

# Reconstrucción Contable-Fiscal IR-2 (Orquestador Principal)

Este flujo de trabajo coordina al equipo de sub-agentes para generar los estados financieros y la declaración IR-2.

// turbo-all
1. Verificar que existan las carpetas necesarias: `data/raw`, `data/extracted`, `data/consolidated`, `data/output`.
2. Solicitar al usuario que confirme si ya depositó los archivos fuente (PDFs, Excel, imágenes) en la carpeta `data/raw/`.
3. Iniciar fase de extracción: Leer todos los archivos en `data/raw/` utilizando el skill `doc-classifier-rd` para clasificar y extraer la información. Guardar resultados como JSON normalizados en `data/extracted/`.
4. Iniciar fase de validación: Analizar los archivos JSON en `data/extracted/` buscando discrepancias (ej. valores de ventas entre 607 y estados de cuenta). 
5. Pausar y preguntar al usuario si se encuentran conflictos críticos que no se puedan auto-resolver. Guardar la versión limpia en `data/consolidated/datos_consolidados.json`.
6. Invocar motor fiscal (Contador Senior): Procesar `datos_consolidados.json` con los skills de `rd-cost-of-sales-calculator`, `rd-depreciation-engine` y generar la data para los anexos IR-2.
7. Generar reportes: Utilizar `excel-exporter` y `latex-pdf-generator` para exportar la declaración IR-2 a `data/output/`.
8. Generar un Artifact tipo Walkthrough resumiendo el proceso, los resultados fiscales y los impuestos a pagar.
