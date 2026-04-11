from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Dict, Any
from core.database import PadronDGII, Dgii606, Socio

class ValidadorRNC:
    """
    Motor de Validación de RNC Proactiva.
    Cruza los auxiliares (606) y socios con el Padrón DGII para detectar riesgos de estatus.
    """

    def __init__(self, db: Session):
        self.db = db

    def validar_socios(self, empresa_id: int) -> List[Dict]:
        """
        Valida que todos los socios registrados estén ACTIVOS en la DGII.
        Un socio inactivo es un bloqueo crítico para el IR-2.
        """
        hallazgos = []
        socios = self.db.query(Socio).filter_by(empresa_id=empresa_id).all()
        
        for socio in socios:
            # Buscar en el padrón (normalizar RNC eliminando guiones)
            rnc_clean = socio.identificador.replace("-", "")
            registro = self.db.query(PadronDGII).filter_by(rnc=rnc_clean).first()
            
            if not registro:
                hallazgos.append({
                    "tipo": "BLOQUEO",
                    "mensaje": f"Socio '{socio.nombre_razon_social}' (RNC: {socio.identificador}) no existe en el Padrón DGII.",
                    "recomendacion": "Verifique el RNC/Cédula del socio. Si es extranjero, debe estar registrado como tal."
                })
            elif registro.estado.upper() != "ACTIVO":
                hallazgos.append({
                    "tipo": "BLOQUEO",
                    "mensaje": f"Socio '{socio.nombre_razon_social}' está en estado '{registro.estado}' en DGII.",
                    "recomendacion": "El socio debe regularizar su estatus tributario antes de presentar el IR-2."
                })
        
        return hallazgos

    def validar_proveedores_criticos(self, empresa_id: int, periodo: str, umbral: float = 50000.0) -> List[Dict]:
        """
        Valida proveedores del 606 que superen el umbral de materialidad.
        """
        hallazgos = []
        
        # Agrupar compras por RNC de proveedor
        from sqlalchemy import func
        compras = self.db.query(
            Dgii606.rnc_proveedor,
            func.sum(Dgii606.monto_facturado).label('total')
        ).filter(
            Dgii606.empresa_id == empresa_id,
            Dgii606.periodo.like(f"{periodo}%")
        ).group_by(Dgii606.rnc_proveedor).all()

        for rnc, total in compras:
            if total >= umbral:
                # Normalizar para búsqueda
                rnc_clean = rnc.replace("-", "")
                registro = self.db.query(PadronDGII).filter_by(rnc=rnc_clean).first()
                if not registro or registro.estado.upper() != "ACTIVO":
                    estatus = registro.estado if registro else "NO REGISTRADO"
                    hallazgos.append({
                        "tipo": "ADVERTENCIA",
                        "mensaje": f"Proveedor crítico (RNC: {rnc}) con volumen de RD$ {total:,.2f} está '{estatus}'.",
                        "recomendacion": "El gasto podría ser impugnado por la DGII. Solicite estatus vigente al proveedor."
                    })
        
        return hallazgos
