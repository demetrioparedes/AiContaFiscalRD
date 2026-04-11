---
name: excel-exporter
description: Genera los reportes contables y los anexos del IR-2 en formato de Excel oficial.
---

# excel-exporter (El Editor)

Este Skill es invocado en la fase final para generar los artefactos entregables de Excel según los requerimientos de la DGII.

## Instrucciones del Skill
1. Recibe los JSON resultantes del motor fiscal (ej. `calculos_fiscales_y_anexos.json`).
2. Utiliza una librería como `openpyxl` o `xlsxwriter` para poblar celdas específicas en plantillas predefinidas.
3. Genera múltiples pestañas:
   - Estado de Resultados
   - Balance General
   - Anexos (A-1, B-1, D, E, G, etc.)
4. Asegúrate de que las sumas y fórmulas in-Excel se inserten correctamente para que el usuario pueda auditar el archivo.
5. Guarda el archivo final en `data/output/anexos_ir2_2025.xlsx`.
