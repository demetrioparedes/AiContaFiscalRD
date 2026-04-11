import sys
import os
sys.path.insert(0, os.path.abspath("core"))

from database import SessionLocal, ActivoFijo, Empresa, init_db
from motor_activos import calcular_depreciacion_anual
from decimal import Decimal

def test_depreciacion():
    init_db()
    db = SessionLocal()
    try:
        # 1. Crear Empresa
        rnc_test = "987654321"
        emp = db.query(Empresa).filter_by(rnc=rnc_test).first()
        if not emp:
            emp = Empresa(rnc=rnc_test, nombre_empresa="Asset Test Ltd.")
            db.add(emp)
            db.commit()

        # Limpiar activos previos de test
        db.query(ActivoFijo).filter_by(empresa_id=emp.id).delete()

        # 2. Agregar Activos de Diferentes Categorías
        activos = [
            ActivoFijo(
                empresa_id=emp.id, descripcion="Edificio Principal", 
                categoria="Edificaciones (Cat 1)", valor_compra=10000000.00,
                depreciacion_acumulada=0.0
            ),
            ActivoFijo(
                empresa_id=emp.id, descripcion="Laptop Dell XPS", 
                categoria="Equipo Computo (Cat 2)", valor_compra=100000.00,
                depreciacion_acumulada=0.0
            ),
            ActivoFijo(
                empresa_id=emp.id, descripcion="Torno Industrial", 
                categoria="Maquinaria (Cat 3)", valor_compra=500000.00,
                depreciacion_acumulada=0.0
            )
        ]
        db.add_all(activos)
        db.commit()

        # 3. Calcular Depreciación
        total_gasto = calcular_depreciacion_anual(db, emp.id, 2025)
        
        # Verificaciones
        # Cat 1: 10,000,000 * 0.05 = 500,000
        # Cat 2: 100,000 * 0.25 = 25,000
        # Cat 3: 500,000 * 0.15 = 75,000
        # Total: 600,000
        
        print(f"\nResultado Total Gasto Depreciacion: RD$ {total_gasto:,.2f}")
        assert total_gasto == Decimal("600000.00"), f"Error en calculo total. Esperado 600,000, Obtenido {total_gasto}"
        
        # Verificar permanencia en DB
        for a in db.query(ActivoFijo).filter_by(empresa_id=emp.id).all():
            print(f"  Confirmado DB -> {a.descripcion}: Valor Libro = RD$ {a.valor_libro:,.2f}")

        print("\n[OK] El Motor de Activos Fijos calculó y actualizó correctamente la base de datos.")

    finally:
        db.rollback()
        db.close()

if __name__ == "__main__":
    test_depreciacion()
