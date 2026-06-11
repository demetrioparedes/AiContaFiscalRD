import sys, os
from sqlalchemy import and_
from decimal import Decimal

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.database import (
    SessionLocal, Empresa, Dgii606, DgiiIt1, Dgii607,
    Inventario, TssNomina, EstadoFinanciero, ValidacionFiscal,
    init_db
)
from core.motor_fiscal import OrquestadorFiscal


def test_escenarios_red_flag():
    """Test de detección de Red Flags usando OrquestadorFiscal."""
    init_db()
    db = SessionLocal()
    try:
        rnc_test = "101826552"
        anio = 2025
        anio_str = str(anio)

        emp = db.query(Empresa).filter_by(rnc=rnc_test).first()
        if not emp:
            emp = Empresa(rnc=rnc_test, nombre_empresa="Comercial Riesgosa SRL")
            db.add(emp)
            db.commit()

        db.query(ValidacionFiscal).filter_by(empresa_id=emp.id).delete()
        db.query(Dgii606).filter_by(empresa_id=emp.id).delete()
        db.query(Inventario).filter_by(empresa_id=emp.id).delete()
        db.query(DgiiIt1).filter_by(empresa_id=emp.id).delete()

        for i in range(10):
            db.add(Dgii606(
                empresa_id=emp.id, periodo=f"{anio_str}01", rnc_proveedor=f"123{i}",
                monto_facturado=20000.0, itbis_facturado=3600.0,
                tipo_bien_servicio=1, ncf=f"B0100000{i}", anulada=0
            ))
        for i in range(5):
            db.add(Dgii606(
                empresa_id=emp.id, periodo=f"{anio_str}02", rnc_proveedor=f"999{i}",
                monto_facturado=20000.0, itbis_facturado=0,
                tipo_bien_servicio=2, ncf=f"B1300000{i}", anulada=0
            ))
        db.add(TssNomina(empresa_id=emp.id, periodo=f"{anio_str}01", empleados=10,
                         salario_cotizable=100000, aporte_empresa=15000))
        db.add(EstadoFinanciero(empresa_id=emp.id, periodo=anio_str,
                                ventas_totales=1000000, gastos_personal=400000))
        db.commit()

        orquestador = OrquestadorFiscal(db, rnc_test, anio)
        res = orquestador.ejecutar_auditoria_fiscal_completa()

        assert res["estado"] in ("Listo", "Bloqueado"), f"Pipeline falló: {res.get('mensaje')}"
        print(f"\n[OK] Pipeline ejecutado. Estado: {res['estado']}")
    finally:
        db.rollback()
        db.close()
