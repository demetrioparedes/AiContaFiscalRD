import sys
import os
sys.path.insert(0, r"c:\GEMINI\AiContaFiscalRD\core")

# Localizar core relativo a este archivo de test
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "core"))

from core.database import SessionLocal, Socio, ValidacionFiscal, Empresa, init_db
from core.utils.importador_socios import importar_socios_desde_excel
from core.motor_beneficiario_final import MotorBeneficiarioFinal

def test_flujo_beneficiario_completo():
    print("\n" + "="*60)
    print("  TEST: FLUJO DE BENEFICIARIO FINAL (H-1 / H-2)")
    print("="*60)
    
    db = SessionLocal()
    init_db() # Asegurar tablas
    
    try:
        # 1. Asegurar que existe una empresa (id=1)
        rnc_test = "130826552"
        empresa = db.query(Empresa).filter_by(rnc=rnc_test).first()
        if not empresa:
            empresa = Empresa(rnc=rnc_test, nombre_empresa="EMPRESA TEST H1H2")
            db.add(empresa)
            db.commit()
            empresa_id = empresa.id
        else:
            empresa_id = empresa.id
            
        # 2. Importar desde Excel
        excel_path = r"c:\GEMINI\AiContaFiscalRD\data\templates\template_beneficiarios.xlsx"
        print(f"  [1] Importando socios desde: {excel_path}...")
        res_import = importar_socios_desde_excel(db, empresa_id, excel_path)
        
        if "error" in res_import:
            print(f"  [!] Fallo importación: {res_import['error']}")
            return
        
        print(f"  [OK] Socios importados: {res_import['count']}")
        
        # 3. Ejecutar Motor de Auditoría de Socios
        print("  [2] Ejecutando Motor de Beneficiario Final (Socio Senior)...")
        motor = MotorBeneficiarioFinal(db, empresa_id, 2025)
        resultados = motor.ejecutar_auditoria_socios()
        
        # 4. Validar Resultados
        print("\n  >>> RESULTADO INTEGRIDAD:")
        print(f"      Estado: {resultados['integridad']['estado']}")
        print(f"      Hallazgo: {resultados['integridad']['hallazgo']}")
        
        print("\n  >>> ANEXO H-1 (Accionistas Directos):")
        for h1 in resultados['anexos']['H1']:
            print(f"      - {h1['nombre']} ({h1['porcentaje']}%)")
            
        print("\n  >>> ANEXO H-2 (Beneficiarios Finales PF):")
        for h2 in resultados['anexos']['H2']:
            print(f"      - {h2['nombre']} | {h2['nacionalidad']} | ID: {h2['identificador']}")
            
        # 5. Verificar Red Flags persistidas
        flags = db.query(ValidacionFiscal).filter_by(
            empresa_id=empresa_id, 
            periodo="2025"
        ).filter(ValidacionFiscal.tipo_validacion.like("%SOCIO%")).all()
        
        if flags:
            print(f"\n  [!] {len(flags)} RED FLAGS DETECTADAS EN DB:")
            for f in flags:
                print(f"      - {f.tipo_validacion}: {f.recomendacion_socio[:50]}...")
        else:
            print("\n  [OK] No se detectaron riesgos en la estructura.")

    finally:
        db.close()
        print("\n" + "="*60)

if __name__ == "__main__":
    test_flujo_beneficiario_completo()
