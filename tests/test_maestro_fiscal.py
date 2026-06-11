import sys, os
from decimal import Decimal

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.database import SessionLocal, Dgii606, DgiiIt1, Dgii607, Empresa, EstadoFinanciero, init_db
from core.motor_fiscal import OrquestadorFiscal


def test_optimizacion_itbis_proporcional():
    """Test de pipeline fiscal completo via OrquestadorFiscal."""
    init_db()
    db = SessionLocal()
    try:
        rnc_test = "130123456"
        emp = db.query(Empresa).filter_by(rnc=rnc_test).first()
        if not emp:
            emp = Empresa(rnc=rnc_test, nombre_empresa="Exportadora Consciente SRL")
            db.add(emp)
            db.commit()

        anio = 2025
        anio_str = str(anio)

        db.query(Dgii606).filter_by(empresa_id=emp.id).delete()
        db.query(DgiiIt1).filter_by(empresa_id=emp.id).delete()
        db.query(Dgii607).filter_by(empresa_id=emp.id).delete()

        db.add(Dgii606(
            empresa_id=emp.id, periodo="202501", rnc_proveedor="123",
            itbis_facturado=18000.00, monto_facturado=100000.00,
            tipo_bien_servicio=1, anulada=0
        ))
        db.add(DgiiIt1(
            empresa_id=emp.id, periodo="202501",
            itbis_credito=10000.00, ventas_gravadas=50000.00, ventas_exentas=40000.00
        ))
        db.commit()

        orquestador = OrquestadorFiscal(db, rnc_test, anio)
        res = orquestador.ejecutar_auditoria_fiscal_completa()

        assert res["estado"] in ("Listo", "Bloqueado"), f"Pipeline falló: {res.get('mensaje')}"
        print(f"\n[OK] Pipeline ejecutado. Estado: {res['estado']}")
    finally:
        db.rollback()
        db.close()
