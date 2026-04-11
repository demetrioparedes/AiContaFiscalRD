# 🏢 Guía Maestra de Cumplimiento Fiscal IR-2 (Versión 2026)
> **Autor:** Socio Experto en Impuestos (Consultoría "Big4" Style)
> **Contexto:** República Dominicana - Legislación 11-92, Normas Generales y Reformas Vigentes al 2026.

## 1. Introducción Ejecutiva
El **IR-2** es el formulario de Declaración Jurada Anual del Impuesto Sobre la Renta de Sociedades (Personas Jurídicas). Es el "cierre de oro" del ciclo fiscal de una empresa dominicana.

*   **Sujetos Obligados:** SRL, SA, SAS, EIRL, Negocios de Único Dueño con personería jurídica y sucursales extranjeras.
*   **Tasa:** 27 % sobre la Renta Neta Imponible (Art. 297 CT).
*   **Plazo de Presentación:** 120 días calendario después de la fecha de cierre.
    *   Cierre 31 de Diciembre: Vence el 30 de abril (o último día hábil).
*   **Sanciones por Incumplimiento (Art. 252 y ss.):**
    *   Mora: 10% el primer mes y 4% meses subsiguientes.
    *   Interés Indemnizatorio: 1.10% mensual acumulativo.

---

## 2. Formulario Principal IR-2 y sus Anexos (Mapa de Integración)

| Anexo | Nombre / Función | Impacto en IR-2 (Alimenta Casilla) |
| :--- | :--- | :--- |
| **Anexo A1** | Balance General | Cuadrado con Activos/Pasivos. |
| **Anexo B-1** | Estado de Resultados | **Casilla 7 (Utilidad Neta)**. Corazón del IR-2. |
| **Anexo D** | Costo de Ventas y Depreciación | Alimenta B-1 y el Gasto por Depreciación. |
| **Anexo E** | Gastos de Personal (TSS) | Valida deducibilidad de sueldos. |
| **Anexo J** | Resumen 606/607/608 | **Filtro Crítico:** Cruce obligatorio con B-1. |

---

## 3. Matriz de Obligaciones Periódicas (Impacto Matrix)

| Cód | Nombre | Frecuencia | Impacto en IR-2 | Norma |
| :--- | :--- | :--- | :--- | :--- |
| **606** | Compras | Mensual | Define **Gasto Deducible**. | 06-18 |
| **607** | Ventas | Mensual | Define **Ingreso Operativo**. | 07-18 |
| **IT-1** | ITBIS | Mensual | ITBIS Proporcional (Gasto) y Créditos. | Art. 335 |
| **IR-17** | Retenciones | Mensual | Pasivos por retenciones. | Art. 309 |
| **623** | Retenciones Recibidas | Anual | **Crédito Fiscal** (Casilla 18). | 02-05 |

---

## 4. Flujo de Información: El "Oleoducto Fiscal"
1.  **Captura (606/607)** -> **IT-1 (Mensual)** -> **Acumulado (12 meses)** -> **Anexo J**.
2.  **Anexo J** debe ser idéntico al **Anexo B-1** (Ingresos/Gastos).
3.  **Anexo D** ajusta la utilidad contable a fiscal (Depreciación).
4.  **Resultado Final** se resta de Anticipos y Retenciones = **Saldo a Pagar**.

---

## 5. Otras Obligaciones (Compliance 360)
*   **Beneficiario Final (RS-1):** Quién es el dueño real (>20%).
*   **DIOR-628:** Precios de Transferencia (Relacionadas).

---

## 6. Consejos Prácticos y Red Flags del Socio 🚩

### Pecados Capitales:
1.  **Inventarios en Cero:** Sospecha inmediata de ventas omitidas.
2.  **Cruce 606 vs B-1:** Diferencia mayor al 0.01% dispara alerta en OFV.
3.  **Sueldos sin TSS:** Gasto no admitido si no está en la nómina de la TSS.
4.  **Exceso de B13:** Abuso de facturas de gastos menores.

---

## 7. Estrategia de Blindaje
*   Correr conciliaciones trimestrales.
*   Validar estatus "RST" de proveedores para retener el 100% de ITBIS si aplica.
*   **Automatización de Auditoría:** Usar el motor `AiContaFiscalRD` para detectar estas fallas antes de enviar a DGII.
