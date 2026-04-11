---
name: rd-tax-reconciliation-engine
description: Motor fiscal para generar la conciliación (Anexo G) y cálculos del IR-2 basado en la normativa DGII.
---

# rd-tax-reconciliation-engine (Contador Senior)

Este Skill ejecuta la lógica de negocios crítica sobre los datos ya consolidados y validados.

## Instrucciones del Skill
1. Lee los datos consolidados desde `data/consolidated/datos_consolidados_2025.json` (y el balance anterior si existe).
2. Calcula deducciones admitidas y no admitidas.
3. Determina la base imponible del Impuesto Sobre la Renta (ISR) aplicando la tasa correspondiente (27%).
4. Realiza la conciliación bancaria y fiscal necesaria para poblar el Anexo G.
5. Calcula los anticipos a pagar, saldos a favor e ITBIS por liquidar.
6. Si detecta variables no definidas (ej. inventario final no reportado), pausa su ejecución y solicita al Orquestador que active al "Asistente" para interactuar con el usuario.
7. Guarda los cálculos finales y resultados en un esquema JSON preparado para el reporte (ej. `calculos_fiscales_y_anexos.json`).
