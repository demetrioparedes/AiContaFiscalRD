import sys
import os
sys.path.insert(0, os.path.abspath("core"))

from database import SessionLocal, Dgii606, PadronDGII, Empresa, ValidacionFiscal
from auditoria_retenciones import auditar_registro_606
from decimal import Decimal

def test_auditoria():
    db = SessionLocal()
    try:
        # 1. Crear Empresa de Prueba
        emp = db.query(Empresa).filter_by(rnc="123456789").first()
        if not emp:
            emp = Empresa(rnc="123456789", nombre_empresa="Test S.A.")
            db.add(emp)
            db.commit()

        # 2. Mock Padron (Proveedor RST)
        prov_rnc = "40225123456" # 11 digitos = PF
        padron = db.query(PadronDGII).filter_by(rnc=prov_rnc).first()
        if not padron:
            padron = PadronDGII(rnc=prov_rnc, razon_social="Juan Perez RST", regimen_pago="RST - INGRESOS")
            db.add(padron)
            db.commit()

        # 3. Crear Registro 606 con Error de Retención
        # Escenario: Honorarios a PF (debe retener 10% ISR y 100% ITBIS)
        # Pero pondremos 0% para ver si el motor lo detecta.
        reg = Dgii606(
            empresa_id=emp.id,
            periodo="202501",
            rnc_proveedor=prov_rnc,
            ncf="B0100000001",
            tipo_bien_servicio=2, # Honorarios
            monto_facturado=10000.00,
            itbis_facturado=1800.00,
            isr_retenido=0.00,      # ERROR: Debería ser 1000.00
            itbis_retenido=0.00     # ERROR: Debería ser 1800.00
        )
        
        print("Testing Auditoria for NCF B0100000001 (Honorarios PF RST)...")
        hallazgos = auditar_registro_606(db, reg)
        
        for h in hallazgos:
            print(f"  [HALLAZGO] Tipo: {h.tipo_validacion} | Estado: {h.estado}")
            print(f"    Detalle: Sist={h.valor_sistema}, Esperado={h.valor_dgii}, Dif={h.diferencia}")

        assert len(hallazgos) >= 2, "Debería haber detectado 2 errores (ISR e ITBIS)"
        print("\n[OK] El motor de auditoría detectó correctamente las inconsistencias.")

    finally:
        db.rollback() # No queremos ensuciar la base de datos real
        db.close()

if __name__ == "__main__":
    test_auditoria()
