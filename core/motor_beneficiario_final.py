# core/motor_beneficiario_final.py
from typing import List, Dict, Any
from decimal import Decimal
from sqlalchemy.orm import Session
from database import Socio, ValidacionFiscal
from datetime import datetime

class MotorBeneficiarioFinal:
    """
    Motor Experto para cumplimiento de Anexos H-1 y H-2 (Beneficiario Final).
    Implementa lógica de resolución recursiva y detección de Red Flags.
    """
    def __init__(self, db: Session, empresa_id: int, ejercicio: int):
        self.db = db
        self.empresa_id = empresa_id
        self.ejercicio = ejercicio
        self.anio_str = str(ejercicio)
        self.socios = self._cargar_socios()

    def _cargar_socios(self):
        """Carga todos los socios registrados para la empresa."""
        return self.db.query(Socio).filter_by(empresa_id=self.empresa_id).all()

    def ejecutar_auditoria_socios(self) -> Dict[str, Any]:
        """Ejecuta el pipeline completo de validación de socios."""
        resultados = {
            "integridad": self.validar_integridad_accionaria(),
            "red_flags": self.detectar_red_flags(),
            "anexos": self.generar_anexos_h1_h2()
        }
        
        # Registrar hallazgos en la DB para el Dashboard
        if resultados["integridad"]["estado"] == "ERROR":
            self._registrar_hallazgo(
                "INTEGRIDAD_ACCIONARIA", 
                resultados["integridad"]["hallazgo"],
                resultados["integridad"]["recomendacion_socio"]
            )
            
        for flag in resultados["red_flags"]:
            self._registrar_hallazgo(flag["tipo"], flag["hallazgo"], flag["recomendacion_socio"])

        return resultados

    def validar_integridad_accionaria(self) -> Dict:
        """Valida que la suma de participaciones directas sea 100%."""
        # Sumamos solo los que no tienen entidad_madre_id (participación directa en la empresa base)
        total = sum(float(s.porcentaje_participacion) for s in self.socios if not s.entidad_madre_id)
        
        if abs(total - 100.00) > 0.01:
            return {
                "estado": "ERROR",
                "hallazgo": f"Inconsistencia en Capital Social: Suma de participaciones es {total:.2f}% (Debe ser 100%)",
                "recomendacion_socio": "📍 ACCIÓN REQUERIDA: Revise la estructura de socios. La DGII rechazará el IR-2 si los porcentajes no cuadran exactamente.",
                "bloqueante": True
            }
        return {"estado": "OK", "hallazgo": "Capital Social cuadrado (100%)", "bloqueante": False}

    def generar_anexos_h1_h2(self) -> Dict:
        """Genera la data estructurada para los reportes H-1 y H-2 con resolución recursiva."""
        h1 = [] # Accionistas Directos (Nivel 1)
        h2_map = {} # Mapa para consolidar beneficiarios finales (Personas Físicas)
        
        # 1. Identificar H-1 (Cualquier socio directo)
        for socio in self.socios:
            if not socio.entidad_madre_id:
                h1.append({
                    "identificador": socio.identificador,
                    "nombre": socio.nombre_razon_social,
                    "porcentaje": float(socio.porcentaje_participacion),
                    "es_pf": socio.es_persona_fisica
                })
                # Iniciar rastreo desde este socio
                self._rastrear_beneficiario(socio, Decimal(str(socio.porcentaje_participacion)), h2_map)

        # 2. Convertir el mapa de H-2 a lista
        h2 = []
        for ident, data in h2_map.items():
            # Regla DGII: Reportar si tiene >= 10% (anteriormente 20%, industrializamos a 10%)
            if data["porcentaje_efectivo"] >= 10 or data["es_beneficiario_final"]:
                h2.append({
                    "identificador": ident,
                    "nombre": data["nombre"],
                    "porcentaje": float(data["porcentaje_efectivo"]),
                    "domicilio": data["domicilio"],
                    "nacionalidad": data["nacionalidad"]
                })
        
        return {"H1": h1, "H2": h2}

    def _rastrear_beneficiario(self, socio_actual: Socio, porcentaje_en_hijo: Decimal, h2_map: Dict):
        """Función recursiva para navegar la cadena de control."""
        if socio_actual.es_persona_fisica:
            # Es un Beneficiario Final (Cima de la cadena)
            ident = socio_actual.identificador
            if ident not in h2_map:
                h2_map[ident] = {
                    "nombre": socio_actual.nombre_razon_social,
                    "porcentaje_efectivo": Decimal("0.0"),
                    "domicilio": socio_actual.domicilio,
                    "nacionalidad": socio_actual.nacionalidad,
                    "es_beneficiario_final": socio_actual.es_beneficiario_final
                }
            h2_map[ident]["porcentaje_efectivo"] += porcentaje_en_hijo
        else:
            # Es una empresa, buscar a sus socios
            hijos = [s for s in self.socios if s.entidad_madre_id == socio_actual.id]
            for hijo in hijos:
                # El porcentaje efectivo es (Porcentaje del Hijo en la Empresa Madre) * (Porcentaje de la Empresa Madre en la Empresa Anterior)
                porcentaje_hijo_en_madre = Decimal(str(hijo.porcentaje_participacion)) / Decimal("100.0")
                porcentaje_efectivo_hijo = porcentaje_hijo_en_madre * porcentaje_en_hijo
                self._rastrear_beneficiario(hijo, porcentaje_efectivo_hijo, h2_map)

    def detectar_red_flags(self) -> List[Dict]:
        # ... (se mantiene igual pero con lógica de socios cargados)
        flags = []
        for socio in self.socios:
            # Alerta si hay niveles de opacidad excesivos (> 3)
            # (Futura mejora: contador de profundidad en _rastrear)
            if socio.riesgo_pais:
                flags.append({
                    "tipo": "RED_FLAG_SOCIOS",
                    "hallazgo": f"Socio en jurisdicción de alto riesgo: {socio.nombre_razon_social} ({socio.residencia_fiscal})",
                    "recomendacion_socio": "⚠️ ALERTA PLD: Los socios en paraísos fiscales disparan fiscalizaciones. Documente el origen de los fondos."
                })
        return flags

    def _registrar_hallazgo(self, tipo: str, hallazgo: str, recomendacion: str):
        # Asegurar que no duplicamos hallazgos iguales en la misma sesión
        db = self.db
        periodo = self.anio_str
        existe = db.query(ValidacionFiscal).filter_by(
            empresa_id=self.empresa_id, periodo=periodo, tipo_validacion=tipo
        ).first()
        
        if not existe:
            nueva_val = ValidacionFiscal(
                empresa_id=self.empresa_id,
                periodo=periodo,
                tipo_validacion=tipo,
                estado="CRITICO" if "ERROR" in hallazgo or "RIESGO" in hallazgo else "ADVERTENCIA",
                recomendacion_socio=recomendacion,
                creado=datetime.now()
            )
            db.add(nueva_val)
            db.commit()
