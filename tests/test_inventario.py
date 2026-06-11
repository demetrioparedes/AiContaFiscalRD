import sys, os
from decimal import Decimal
import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.database import SessionLocal, Inventario, Empresa, Dgii606, init_db
from core.motor_inventario import MotorInventario


def test_costo_ventas():
    """Test de costo de ventas usando la API clase MotorInventario."""
    init_db()
    db = SessionLocal()
    try:
        rnc_test = "101010101"
        emp = db.query(Empresa).filter_by(rnc=rnc_test).first()
        if not emp:
            emp = Empresa(rnc=rnc_test, nombre_empresa="Retail Test SA")
            db.add(emp)
            db.commit()

        db.query(Inventario).filter_by(empresa_id=emp.id).delete()
        db.query(Dgii606).filter_by(empresa_id=emp.id).delete()

        db.add(Inventario(
            empresa_id=emp.id, descripcion="Stock Apertura",
            cantidad=100, costo_unitario=1000, valor_total=100000.00,
            tipo_inventario='inicial', fecha_registro=datetime.date(2025, 1, 1)
        ))
        db.add(Dgii606(
            empresa_id=emp.id, rnc_proveedor="888888888", periodo="202505",
            ncf="B0100000001", monto_facturado=500000.00, tipo_bien_servicio=2, anulada=False
        ))
        db.add(Inventario(
            empresa_id=emp.id, descripcion="Conteo Cierre",
            cantidad=80, costo_unitario=1000, valor_total=80000.00,
            tipo_inventario='final', fecha_registro=datetime.date(2025, 12, 31)
        ))
        db.commit()

        motor = MotorInventario(db, emp.id, 2025)
        costo = motor.calcular_costo_ventas()

        assert float(costo) == 520000.0, f"Esperado 520,000, obtenido {costo}"
        print(f"\n[OK] Costo de Ventas: RD$ {costo:,.2f}")
    finally:
        db.rollback()
        db.close()
