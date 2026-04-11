# scratch/test_recursividad_socios.py
import sys
import os
from decimal import Decimal

project_root = r"c:\GEMINI\AiContaFiscalRD"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "core"))

from database import SessionLocal, Empresa, Socio
from motor_beneficiario_final import MotorBeneficiarioFinal

def test_recursividad():
    db = SessionLocal()
    try:
        rnc_test = "999-REC-001"
        # 1. Limpiar data previa si existe
        emp = db.query(Empresa).filter_by(rnc=rnc_test).first()
        if emp:
            db.query(Socio).filter_by(empresa_id=emp.id).delete()
            db.commit()
        else:
            # Crear si no existe
            emp = Empresa(rnc=rnc_test, nombre_empresa="EMPRESA AUDITADA SAS")
            db.add(emp)
            db.commit()
            db.refresh(emp)
        
        # Socio 1: Empresa Holding (50%)
        holding = Socio(empresa_id=emp.id, identificador="101-HOLDING", tipo_identificador=2, 
                        nombre_razon_social="HOLDING INVESTMENTS SRL", porcentaje_participacion=Decimal("50.0"), 
                        es_persona_fisica=False, residencia_fiscal="República Dominicana", 
                        nacionalidad="Dominicana", domicilio="Santo Domingo")
        db.add(holding)
        db.commit()
        db.refresh(holding)
        
        # Socio 2: Persona Física Directa (50%)
        directo = Socio(empresa_id=emp.id, identificador="001-DIRECTO", tipo_identificador=1, 
                        nombre_razon_social="PEDRO DIRECTO", porcentaje_participacion=Decimal("50.0"), 
                        es_persona_fisica=True, residencia_fiscal="República Dominicana", 
                        nacionalidad="Dominicana", domicilio="Santo Domingo")
        db.add(directo)
        
        # Socio 3: Persona Física en Holding (50% del Holding -> 25% efectivo)
        indirecto = Socio(empresa_id=emp.id, entidad_madre_id=holding.id, identificador="001-INDIRECTO", 
                          tipo_identificador=1, nombre_razon_social="JUAN INVISIBLE", 
                          porcentaje_participacion=Decimal("50.0"), es_persona_fisica=True,
                          residencia_fiscal="República Dominicana", nacionalidad="Dominicana", 
                          domicilio="Santo Domingo")
        db.add(indirecto)
        db.commit()
        
        # 3. Ejecutar Motor
        motor = MotorBeneficiarioFinal(db, emp.id, 2025)
        res = motor.generar_anexos_h1_h2()
        
        print("\n=== RESULTADOS TEST RECURSIVIDAD ===")
        print(f"H-1 (Accionistas Directos): {len(res['H1'])}")
        for h in res['H1']:
            print(f"  - {h['nombre']}: {h['porcentaje']}%")
            
        print(f"\nH-2 (Beneficiarios Finales Efectivos): {len(res['H2'])}")
        for h in res['H2']:
            print(f"  - {h['nombre']}: {h['porcentaje']}% (Efectivo)")
            
        # Validar lógica: Juan Invisible debe tener 25%
        juan = next((h for h in res['H2'] if "JUAN" in h['nombre']), None)
        if juan and juan['porcentaje'] == 25.0:
            print("\n[SUCCESS] Lógica de recursividad validada al 100%.")
        else:
            print("\n[FAILED] Error en cálculo de participación efectiva.")

    finally:
        db.close()

if __name__ == "__main__":
    test_recursividad()
