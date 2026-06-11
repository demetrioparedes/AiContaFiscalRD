import sys, os
from decimal import Decimal

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.database import SessionLocal, ActivoFijo, Empresa, init_db
from core.motor_activos import MotorActivosFijos


def test_depreciacion():
    """Test de depreciación usando la API clase MotorActivosFijos."""
    init_db()
    db = SessionLocal()
    try:
        rnc_test = "987654321"
        emp = db.query(Empresa).filter_by(rnc=rnc_test).first()
        if not emp:
            emp = Empresa(rnc=rnc_test, nombre_empresa="Asset Test Ltd.")
            db.add(emp)
            db.commit()

        db.query(ActivoFijo).filter_by(empresa_id=emp.id).delete()

        activos = [
            ActivoFijo(empresa_id=emp.id, descripcion="Edificio Principal",
                       categoria="CAT1", valor_compra=10000000.00, depreciacion_acumulada=0.0),
            ActivoFijo(empresa_id=emp.id, descripcion="Laptop Dell XPS",
                       categoria="CAT2", valor_compra=100000.00, depreciacion_acumulada=0.0),
            ActivoFijo(empresa_id=emp.id, descripcion="Torno Industrial",
                       categoria="CAT3", valor_compra=500000.00, depreciacion_acumulada=0.0),
        ]
        db.add_all(activos)
        db.commit()

        motor = MotorActivosFijos(db, emp.id, 2025)
        total_gasto = motor.calcular_depreciacion_anual()

        assert total_gasto == Decimal("600000.00"), f"Esperado 600,000, obtenido {total_gasto}"
        print(f"\n[OK] Depreciación calculada: RD$ {total_gasto:,.2f}")
    finally:
        db.rollback()
        db.close()
