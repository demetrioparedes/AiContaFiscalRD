from decimal import Decimal
from typing import Dict

PLANTILLAS_CRUCES = {
    1: {
        "ROJO": (
            "Tus ventas del 607 (RD${sist:,.2f}) no coinciden con "
            "el Estado de Resultados (RD${dgii:,.2f}). "
            "Diferencia: RD${dif:,.2f}. "
            "Revisa si hay facturas del 607 fuera del período o "
            "ventas registradas sin comprobante fiscal."
        ),
        "VERDE": (
            "Ventas 607 cuadran perfectamente con el Estado de "
            "Resultados. Sin observaciones."
        )
    },
    2: {
        "ROJO": (
            "El ITBIS facturado en tu 607 (RD${sist:,.2f}) difiere "
            "de lo declarado en el IT-1 (RD${dgii:,.2f}). "
            "Diferencia: RD${dif:,.2f}. "
            "Esto genera una notificación automática de la DGII. "
            "Debes presentar IT-1 rectificativo antes del cierre."
        ),
        "VERDE": "ITBIS facturado coincide con IT-1. Sin observaciones."
    },
    3: {
        "ROJO": (
            "Tus ventas gravadas del 607 (RD${sist:,.2f}) no coinciden "
            "con el acumulado del IT-1 (RD${dgii:,.2f}). "
            "Diferencia: RD${dif:,.2f}. "
            "La DGII cruza esta información automáticamente cada mes."
        ),
        "VERDE": "Ventas gravadas cuadran con IT-1. Sin observaciones."
    },
    4: {
        "ROJO": (
            "Tus ventas exentas del 607 (RD${sist:,.2f}) no coinciden "
            "con el ER (RD${dgii:,.2f}). "
            "Diferencia: RD${dif:,.2f}. "
            "Verifica que las exenciones tengan la documentación "
            "de respaldo exigida por el Art. 343 Ley 11-92."
        ),
        "VERDE": "Ventas exentas consistentes. Sin observaciones."
    },
    6: {
        "ROJO": (
            "Tus notas de crédito superan el 20% de las ventas brutas "
            "(RD${dif:,.2f} sobre el límite). "
            "Esto activa una alerta automática de auditoría en la DGII. "
            "Ten preparada la documentación de cada NC."
        ),
        "VERDE": "Notas de crédito dentro del límite del 20%. Sin observaciones."
    },
    7: {
        "ROJO": (
            "Tus compras del 606 (RD${sist:,.2f}) no cuadran con "
            "Gastos + Costo de Ventas del ER (RD${dgii:,.2f}). "
            "Diferencia: RD${dif:,.2f}. "
            "Posible gasto no registrado o factura duplicada."
        ),
        "VERDE": "Compras 606 cuadran con gastos del ER. Sin observaciones."
    },
    8: {
        "ROJO": (
            "El ITBIS adelantado en tus compras del 606 "
            "(RD${sist:,.2f}) no coincide con el crédito "
            "declarado en el IT-1 (RD${dgii:,.2f}). "
            "Diferencia: RD${dif:,.2f}. "
            "Estás dejando RD${dif:,.2f} de crédito fiscal sin aplicar "
            "o declaraste de más en el IT-1."
        ),
        "VERDE": "ITBIS crédito cuadra con IT-1. Sin observaciones."
    },
    11: {
        "ROJO": (
            "Tus compras (RD${sist:,.2f}) superan el 90% de tus "
            "ventas (RD${dgii:,.2f}). "
            "Esto indica pérdida operativa continua — la DGII "
            "activa auditoría automática después de 2 años consecutivos."
        ),
        "VERDE": "Relación compras/ventas dentro del límite del 90%. Sin observaciones."
    },
    13: {
        "ROJO": (
            "Las retenciones de nómina (IR-13) no cuadran con "
            "lo reportado (diferencia: RD${dif:,.2f}). "
            "Riesgo de inconsistencia en el IR-17 anual."
        ),
        "VERDE": "Retenciones nómina cuadran con IR-13. Sin observaciones."
    },
    15: {
        "ROJO": (
            "El margen bruto contable (RD${sist:,.2f}) no coincide "
            "con el calculado (RD${dgii:,.2f}). "
            "Diferencia: RD${dif:,.2f}. "
            "Posible error en el registro del costo de ventas."
        ),
        "VERDE": "Margen bruto consistente. Sin observaciones."
    },
    16: {
        "ROJO": (
            "Hay gastos operativos (RD${sist:,.2f}) que superan "
            "las compras registradas en el 606 (RD${dgii:,.2f}). "
            "Diferencia: RD${dif:,.2f}. "
            "Posibles gastos sin NCF válido que la DGII rechazará "
            "como deducción."
        ),
        "VERDE": "Gastos operativos respaldados por 606. Sin observaciones."
    },
    17: {
        "ROJO": (
            "El aporte TSS de la empresa no cuadra con la nómina "
            "(diferencia: RD${dif:,.2f}). "
            "La TSS cruza esta información con la DGII trimestralmente."
        ),
        "VERDE": "Aporte TSS consistente con nómina. Sin observaciones."
    },
    18: {
        "ROJO": (
            "La renta imponible calculada (RD${sist:,.2f}) difiere "
            "de la declarada (RD${dgii:,.2f}). "
            "Diferencia: RD${dif:,.2f}. "
            "Revisa los ajustes fiscales del Anexo G antes de firmar el IR-2."
        ),
        "VERDE": "Renta imponible consistente. Sin observaciones."
    },
}

PLANTILLA_RESUMEN_ISR = (
    "Resumen fiscal {anio}:\n"
    "  Renta Neta Imponible: RD${renta:,.2f}\n"
    "  ISR bruto (27%):      RD${isr_bruto:,.2f}\n"
    "  Anticipos pagados:    RD${anticipos:,.2f}\n"
    "  Retenciones:          RD${retenciones:,.2f}\n"
    "  ISR A PAGAR:          RD${isr_pagar:,.2f}"
)


def generar_mensaje_cruce(cruce: Dict) -> str:
    """
    Dado un dict de cruce del motor fiscal, devuelve el mensaje
    en español dominicano claro. Costo: RD$0.
    """
    cruce_id  = cruce.get("id", 0)
    estado    = cruce.get("estado", "VERDE")
    sist      = float(cruce.get("valor_sistema", 0))
    dgii      = float(cruce.get("valor_dgii", 0))
    dif       = float(cruce.get("diferencia", 0))

    plantilla = PLANTILLAS_CRUCES.get(cruce_id, {}).get(estado)

    if not plantilla:
        if estado == "VERDE":
            return f"Cruce #{cruce_id} en orden. Sin observaciones."
        return (
            f"Cruce #{cruce_id} requiere revisión. "
            f"Diferencia detectada: RD${dif:,.2f}."
        )

    return plantilla.format(sist=sist, dgii=dgii, dif=dif)


def generar_resumen_isr(er: Dict) -> str:
    """Resumen del ISR en lenguaje claro. Costo: RD$0."""
    return PLANTILLA_RESUMEN_ISR.format(
        anio        = er.get("periodo", ""),
        renta       = float(er.get("renta_imponible", 0)),
        isr_bruto   = float(er.get("renta_imponible", 0)) * 0.27,
        anticipos   = float(er.get("anticipos", 0)),
        retenciones = float(er.get("retenciones", 0)),
        isr_pagar   = float(er.get("isr_calcular", 0)),
    )


def necesita_ia(pregunta: str) -> bool:
    """
    Decide si la pregunta necesita IA o se resuelve con plantilla.
    Ahora es más proactiva: si no es una respuesta vacía o muy corta, usa IA.
    """
    if len(pregunta.strip()) < 2:
        return False
        
    # Si es un saludo o pregunta genérica, ahora permitimos que la IA responda
    return True
