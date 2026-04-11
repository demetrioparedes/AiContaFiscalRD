---
name: latex-pdf-generator
description: Genera los Estados Financieros en formato PDF utilizando una plantilla LaTeX.
---

# latex-pdf-generator (El Editor)

Este Skill toma los resultados financieros calculados y los inyecta en una plantilla LaTeX profesional para generar un PDF listo para la firma del auditor.

## Instrucciones del Skill
1. Lee los datos finales de los estados financieros desde `data/consolidated/calculos_fiscales_y_anexos.json`.
2. Carga la plantilla base `template_estados_financieros.tex` ubicada en el directorio de este skill.
3. Reemplaza las variables (marcadores tipo `{{VARIABLE}}`) en la plantilla LaTeX con los montos exactos, fechas y nombres correspondientes (ej. `{{COMPANY_NAME}}`, `{{SALES_CURRENT}}`).
4. Ejecuta el compilador de LaTeX (`pdflatex` interaccionando con el sistema operativo) sobre el archivo `.tex` generado.
5. El PDF resultante debe almacenarse en `data/output/estados_financieros_{{YEAR}}.pdf`.
6. Informa de cualquier error de compilación LaTeX al Orquestador para que pueda notificarse al usuario.
