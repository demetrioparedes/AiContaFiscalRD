import sys, os
sys.path.insert(0, r"c:\GEMINI\AiContaFiscalRD\core")

from database import SessionLocal, Base, Empresa, Dgii606, DgiiIr17
from etl_ir17 import procesar_ir17_mensual
from generador_ir17_reporte import generar_reporte_visual_ir17
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from decimal import Decimal

def test_visual():
    print("Iniciando prueba de generación visual...")
    
    # Usar DB real para esta prueba (o una temporal local)
    db = SessionLocal()
    try:
        rnc = "130826552"
        anio = 2025
        
        # 1. Asegurar que existe la empresa
        emp = db.query(Empresa).filter_by(rnc=rnc).first()
        if not emp:
            emp = Empresa(rnc=rnc, nombre_empresa="Comercial Elvira SRL")
            db.add(emp)
            db.commit()
        
        # 2. Insertar data de prueba en 606 si no hay nada
        # Para que el motor IR-17 tenga algo que procesar
        if not db.query(Dgii606).filter_by(empresa_id=emp.id).first():
            db.add(Dgii606(empresa_id=emp.id, periodo="202501", ncf="B0101", monto_facturado=Decimal("50000.00"), isr_retenido=Decimal("5000.00"), tipo_bien_servicio=3)) # Alquiler
            db.add(Dgii606(empresa_id=emp.id, periodo="202501", ncf="B0102", monto_facturado=Decimal("20000.00"), isr_retenido=Decimal("2000.00"), tipo_bien_servicio=2)) # Honorarios
            db.add(Dgii606(empresa_id=emp.id, periodo="202502", ncf="B0103", monto_facturado=Decimal("10000.00"), isr_retenido=Decimal("200.00"), tipo_bien_servicio=2))  # Servicio Tecnico (2%)
            db.commit()
            
        # 3. Procesar IR-17
        procesar_ir17_mensual(db, rnc, anio)
        
        # 4. Generar Reporte Visual
        ruta = generar_reporte_visual_ir17(rnc, anio)
        print(f"Prueba completada. Archivo generado en: {ruta}")
        
    finally:
        db.close()

if __name__ == "__main__":
    test_visual()
