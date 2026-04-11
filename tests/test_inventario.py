import sys
import os
sys.path.insert(0, os.path.abspath("core"))

from database import SessionLocal, Inventario, Empresa, Dgii606, init_db
from motor_inventario import calcular_costo_ventas
from decimal import Decimal
import datetime

def test_costo_ventas():
    init_db()
    db = SessionLocal()
    try:
        # 1. Crear Empresa
        rnc_test = "101010101"
        emp = db.query(Empresa).filter_by(rnc=rnc_test).first()
        if not emp:
            emp = Empresa(rnc=rnc_test, nombre_empresa="Retail Test SA")
            db.add(emp)
            db.commit()

        # Limpiar data previa
        db.query(Inventario).filter_by(empresa_id=emp.id).delete()
        db.query(Dgii606).filter_by(empresa_id=emp.id).delete()

        # 2. Registrar Inventario Inicial (1 de Enero 2025)
        inv_ini = Inventario(
            empresa_id=emp.id, descripcion="Stock Apertura",
            cantidad=100, costo_unitario=1000, valor_total=100000.00,
            tipo_inventario='inicial', fecha_registro=datetime.date(2025, 1, 1)
        )
        db.add(inv_ini)

        # 3. Registrar Compras (606) - Tipo 2 (Gastos de Mercancía)
        compra = Dgii606(
            empresa_id=emp.id, rnc_proveedor="888888888", periodo="202505",
            ncf="B0100000001", monto_facturado=500000.00, tipo_bien_servicio=2,
            anulada=False
        )
        db.add(compra)

        # 4. Registrar Inventario Final (31 de Diciembre 2025)
        inv_fin = Inventario(
            empresa_id=emp.id, descripcion="Conteo Cierre",
            cantidad=80, costo_unitario=1000, valor_total=80000.00,
            tipo_inventario='final', fecha_registro=datetime.date(2025, 12, 31)
        )
        db.add(inv_fin)
        db.commit()

        # --- EJECUTAR MOTOR ---
        costo_calculado = calcular_costo_ventas(db, emp.id, 2025)

        # Verificación: 100,000 (Ini) + 500,000 (Com) - 80,000 (Fin) = 520,000
        print(f"\nResultado Obtenido: RD$ {costo_calculado:,.2f}")
        assert costo_calculado == 520000.0, f"Error en cálculo. Esperado 520,000, obtenido {costo_calculado}"

        print("\n[OK] El Módulo de Inventarios calculó el Costo de Ventas correctamente.")

    finally:
        db.rollback()
        db.close()

if __name__ == "__main__":
    test_costo_ventas()
