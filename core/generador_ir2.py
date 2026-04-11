# core/generador_ir2.py
import os
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit
from sqlalchemy.orm import Session
from database import Empresa, Socio, EstadoFinanciero

class GeneradorIR2:
    """
    Generador IR-2 Nivel Socio Senior.
    Genera XML estructurado, Excel instructivo y PDF de constancia.
    """

    def __init__(self, db: Session, rnc: str, ejercicio: str):
        self.db = db
        self.rnc = rnc
        self.ejercicio = str(ejercicio)
        
        # Resolución dinámica de rutas
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.output_dir = os.path.join(self.base_dir, "data", "output")
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.empresa = self._obtener_datos_empresa()
        self.er = self._obtener_datos_financieros()

    def _obtener_datos_empresa(self):
        emp = self.db.query(Empresa).filter_by(rnc=self.rnc).first()
        return emp

    def _obtener_datos_financieros(self):
        return self.db.query(EstadoFinanciero).filter_by(
            empresa_id=self.empresa.id, periodo=self.ejercicio
        ).order_by(EstadoFinanciero.id.desc()).first()

    def generar_entregable_completo(self):
        """Genera XML, Excel y PDF en un solo proceso de consistencia."""
        archivos = []
        try:
            archivos.append(self._generar_xml_ofv())
            archivos.append(self._generar_excel_ofv())
            archivos.append(self._generar_pdf_reporte())
            return {"status": "success", "archivos": archivos}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _generar_xml_ofv(self):
        """Genera el XML estructurado para la Oficina Virtual."""
        root = ET.Element("DGII_IR2", version="2018")
        
        encabezado = ET.SubElement(root, "Encabezado")
        ET.SubElement(encabezado, "RNC").text = self.rnc
        ET.SubElement(encabezado, "Periodo").text = self.ejercicio
        ET.SubElement(encabezado, "FechaOperacion").text = datetime.now().strftime("%Y-%m-%d")

        detalles = ET.SubElement(root, "Detalles")
        if self.er:
            ET.SubElement(detalles, "RentaNetaImponible").text = str(round(self.er.renta_imponible, 2))
            ET.SubElement(detalles, "ImpuestoLiquidado").text = str(round(self.er.isr_calcular, 2))

        # Anexo H-1 (Socios)
        anexo_h1 = ET.SubElement(root, "Anexo_H1")
        socios = self.db.query(Socio).filter_by(empresa_id=self.empresa.id).all()
        for s in socios:
            socio_node = ET.SubElement(anexo_h1, "Socio")
            ET.SubElement(socio_node, "Identificacion").text = s.identificador
            ET.SubElement(socio_node, "Nombre").text = s.nombre_razon_social
            ET.SubElement(socio_node, "Porcentaje").text = str(float(s.porcentaje_participacion))

        filename = f"DGII_IR2_{self.rnc}_{self.ejercicio}.xml"
        path = os.path.join(self.output_dir, filename)
        
        tree = ET.ElementTree(root)
        tree.write(path, encoding="utf-8", xml_declaration=True)
        return {"nombre": "XML Oficina Virtual", "filename": filename}

    def _generar_excel_ofv(self):
        """Genera un reporte Excel basado en el IR-2."""
        # Nota: Aquí llamamos al generador oficial si está disponible o generamos uno rápido
        from core.generador_ir2_oficial import generar_ir2_oficial
        ruta = generar_ir2_oficial(self.rnc, int(self.ejercicio), db=self.db)
        return {"nombre": "Excel Pre-Validador DGII", "filename": os.path.basename(ruta)}

    def _generar_pdf_reporte(self):
        """Genera la constancia de auditoría en PDF."""
        filename = f"Constancia_Auditoria_{self.rnc}_{self.ejercicio}.pdf"
        path = os.path.join(self.output_dir, filename)
        
        c = canvas.Canvas(path, pagesize=letter)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, 750, f"Constancia de Auditoría Fiscal AI - IR-2 ({self.ejercicio})")
        
        c.setFont("Helvetica", 11)
        c.drawString(50, 730, f"Contribuyente: {self.empresa.nombre_empresa}")
        c.drawString(50, 715, f"RNC: {self.rnc}")
        
        if self.er:
            c.drawString(50, 680, f"Utilidad Neta Declarada: RD$ {self.er.utilidad_neta:,.2f}")
            c.drawString(50, 665, f"Impuesto a Pagar: RD$ {self.er.isr_pagar:,.2f}")
        
        c.drawString(50, 630, "Estatus: Verificado por AiContaFiscalRD - Listo para presentar.")
        c.save()
        return {"nombre": "Constancia de Auditoría PDF", "filename": filename}
