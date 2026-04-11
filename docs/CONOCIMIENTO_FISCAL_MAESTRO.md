# Conocimiento Fiscal Maestro (Dominicana) — AiContaFiscalRD
=========================================================
Este documento es la "Guía Consciente" y fuente de verdad para la lógica del sistema. 
Destila el Código Tributario (Ley 11-92), Normas Generales y mejores prácticas de auditoría.

## 1. El Ciclo de Vida del IR-2
El IR-2 no es una declaración aislada; es el punto de fuga donde colapsan 12 meses de operaciones mensuales.

### Reglas de Integridad (Cruces J-B1)
- **Cruce 01 (Ventas)**: `SUM(607.MontoFacturado) == Anexo_J.Ventas == Anexo_B1.Casilla_1`.
- **Cruce 02 (Compras)**: `SUM(606.MontoFacturado where tipo=2) == Anexo_B1.Costos`.
- **Cruce 03 (NCF Anulados)**: Los Saltos en la secuencia de NCF en el 607 deben estar soportados por el Formato 608.

## 2. Optimizaciones de Deducibilidad (El "Filo" del Motor)

### A. ITBIS Proporcional (Ley 253-12)
- **Lógica**: Si una empresa vende productos exentos (ej: Salud, Educación) y productos gravados, solo puede adelantar una parte del ITBIS en el IT-1.
- **Optimización**: El ITBIS que NO se pudo adelantar (por proporcionalidad) es un **gasto deducible** en el IR-2 (Anexo B-1, Casilla 6.7).
- **Cálculo Motor**: `Deduccion_ITBIS = (Total_ITBIS_Compras - ITBIS_Adelantado_IT1)`.

### B. Ajuste Fiscal por Inflación (Art. 327 y 99 Decreto 15-20)
- **Lógica**: La depreciación fiscal se calcula sobre el valor ajustado por inflación.
- **Optimización**: El sistema debe consultar el IPC (Índice de Precios al Consumidor) del cierre vs el de adquisición para maximizar el gasto permitido.

### C. Retenciones como Crédito (El "Cash-Back" Fiscal)
- **Crédito 623**: Retenciones del 5% del Estado.
- **Crédito IR-17**: Retenciones del 10% efectuadas por terceros (Persona Jurídica a Persona Jurídica bajo norma 02-05 o similar).
- **Alerta**: Si una retención no aparece en el reporte de la DGII (OFV) pero sí en nuestros libros, el sistema debe marcarla como "Riesgo de Rechazo".

## 3. Matriz de Obligaciones (Referencia Técnica)

| Formato | Fecha Límite | Impacto Directo IR-2 |
| :--- | :--- | :--- |
| **606** | 15 del mes sig. | Alimenta Anexo B-1 y Anexo D (Costos) |
| **607** | 15 del mes sig. | Alimenta Anexo B-1 (Ingresos) |
| **IT-1** | 20 del mes sig. | Determina Casilla 6.7 (Gasto ITBIS) |
| **IR-17** | 15 del mes sig. | Cruce de retenciones (Crédito Fiscal) |
| **Anticipos** | 15 cada mes | Crédito directo contra el ISR liquidado |

## 4. Auditoría de Riesgo (Red Flags)
1. **Margen Bruto Incoherente**: Si `(Ventas - Costo_Ventas) / Ventas` es < margen del sector, Auditoría DGII probable.
2. **NCF con Inconsistencias**: Proveedores en RST sin retención del 100% ITBIS.
3. **Pérdidas Sospechosas**: Declarar pérdidas por más de 3 años consecutivos.

---
*Este conocimiento debe ser invocado por el Motor de Auditoría Inteligente para generar consejos y explicaciones al usuario.*
