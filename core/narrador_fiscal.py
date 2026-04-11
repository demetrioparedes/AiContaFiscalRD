from typing import Dict, Any

class NarradorFiscal:
    """
    Generador de Narrativa IA para Informes de Auditoría.
    Transforma los resultados técnicos del Orquestador en un guion narrativo
    con tono de Socio Senior de Big-4.
    """

    def __init__(self, datos_auditoria: Dict[str, Any], rnc: str, periodo: str):
        self.datos = datos_auditoria
        self.rnc = rnc
        self.periodo = periodo

    def generar_guion(self) -> str:
        """Genera el texto completo para ser leído por el sintetizador de voz."""
        
        # 1. Introducción
        saludo = f"Saludos, socio. He finalizado el análisis fiscal exhaustivo del ejercicio {self.periodo}. "
        
        # 2. Resumen General del Estado
        estado = self.datos.get("estado", "Pendiente")
        if estado == "Bloqueado":
            resumen = "Lamentablemente, el proceso se encuentra actualmente bloqueado debido a inconsistencias críticas que deben resolverse antes de proceder con el envío a la oficina virtual. "
        else:
            resumen = "El proceso de auditoría ha concluido exitosamente y la declaración está lista para ser generada. "

        # 3. Análisis de Hallazgos (Red Flags)
        bloqueos = self.datos.get("bloqueos", [])
        red_flags = self.datos.get("red_flags", [])
        
        hallazgos_txt = ""
        if bloqueos:
            hallazgos_txt += f"Se han detectado {len(bloqueos)} puntos de bloqueo preventivo. "
            for b in bloqueos[:2]: # No saturar el audio
                hallazgos_txt += f"Atención: {b.get('mensaje', 'Inconsistencia detectada')}. "
        
        if red_flags:
            hallazgos_txt += f"Adicionalmente, identificamos {len(red_flags)} banderas rojas que, aunque no bloquean el proceso, podrían generar una fiscalización posterior. "
        
        # 4. Mensaje sobre Beneficiario Final (H-1/H-2)
        anexos_h = self.datos.get("anexos_h", {})
        cant_socios = len(anexos_h.get("socios", []))
        if cant_socios > 0:
            hallazgos_txt += f"Los anexos H-1 y H-2 han sido procesados con {cant_socios} socios validados frente al padrón oficial. "
        else:
            hallazgos_txt += "Recuerde que el reporte de beneficiarios finales es obligatorio este año. "

        # 5. Cierre y Recomendación del Socio
        recomendacion = "Mi recomendación como su consultor senior es revisar los asientos propuestos en el panel inferior y confirmar las rectificaciones sugeridas. "
        if estado != "Bloqueado":
            recomendacion += "Puede proceder con la descarga del XML oficial ahora mismo. "
        
        cierre = "Duerma tranquilo, socio. Su cumplimiento fiscal está bajo control inteligente."

        script_final = saludo + resumen + hallazgos_txt + recomendacion + cierre
        return script_final
