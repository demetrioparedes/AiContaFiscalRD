---
name: rd-ocr-engine
description: Extrae texto e información clave de documentos fiscales escaneados o en formato de imagen (JPG, PNG, PDF no seleccionable).
---

# rd-ocr-engine (El Lector Visual)

Este Skill es utilizado por el Sub-Agente Archivista para procesar documentos que no tienen texto estructurado (ej. facturas de compra impresas y escaneadas, recibos físicos).

## Instrucciones del Skill
1. Recibe como entrada la ruta de una imagen o PDF escaneado desde el `doc-classifier-rd` (esto incluye facturas, formularios DGII (IR-1, IR-2, IT-1, etc.), certificaciones, recibos, cheques y cualquier documento físico).
2. Utiliza un motor de reconocimiento óptico de caracteres (OCR) como Tesseract OCR o una API de visión basada en la nube (ej. Google Cloud Vision/Gemini/Claude) para convertir los píxeles en texto.
3. Analiza el layout (estructura visual) del documento para determinar su tipo si no viene pre-clasificado, buscando palabras clave ("Formulario", "Declaración Jurada", "IR-2", "IT-1", "Factura de Crédito Fiscal", etc.).
4. Aplica estrategias de extracción basadas en el tipo de documento detectado:
   - **Facturas**: NCF, RNC, Fecha, Montos (Subtotal, ITBIS, Total).
   - **Formularios/Declaraciones (ej. IT-1, IR-2)**: Casillas específicas, RNC declarante, Período fiscal, Saldo a pagar o a favor.
   - **Documentos varios**: Nombres de entidades, fechas, montos totales y firmas.
5. Devuelve un objeto JSON estructurado al `doc-classifier-rd` con el tipo de documento detectado y los pares clave-valor (KVP) extraídos.
6. Si la confianza del OCR es baja (< 70%) o si un campo crítico es ilegible, marca el documento con el flag `"requires_manual_review": true`.
