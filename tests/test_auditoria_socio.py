import sys
import os
from sqlalchemy import and_

# Localizar core relativo a este archivo de test
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, os.path.join(project_root, "core"))

from database import (
    SessionLocal, Empresa, Dgii606, DgiiIt1, Dgii607, 
    Inventario, TssNomina, EstadoFinanciero, ValidacionFiscal, 
    init_db
)
from motor_fiscal import calcular_estado_resultados, ejecutar_auditoria_fiscal
from decimal import Decimal

def test_escenarios_red_flag():
    init_db()
    db = SessionLocal()
    try:
        rnc_test = "101826552" # Simulado
        anio = 2025
        anio_str = str(anio)
        
        # 1. Preparar Empresa
        emp = db.query(Empresa).filter_by(rnc=rnc_test).first()
        if not emp:
            emp = Empresa(rnc=rnc_test, nombre_empresa="Comercial Riesgosa SRL")
            db.add(emp)
            db.commit()

        # Limpiar data previa
        db.query(ValidacionFiscal).filter_by(empresa_id=emp.id).delete()
        db.query(Dgii606).filter_by(empresa_id=emp.id).delete()
        db.query(Inventario).filter_by(empresa_id=emp.id).delete()
        db.query(DgiiIt1).filter_by(empresa_id=emp.id).delete()
        
        # ESCENARIO A: Inventario en Cero con compras altas
        for i in range(10):
            db.add(Dgii606(
                empresa_id=emp.id, periodo=f"{anio_str}01", rnc_proveedor=f"123{i}",
                monto_facturado=20000.0, itbis_facturado=3600.0,
                tipo_bien_servicio=1, ncf=f"B0100000{i}", anulada=0
            ))
        
        # ESCENARIO B: Abuso de B13 (Gastos Menores)
        # 30% de los gastos seran B13
        for i in range(5):
             db.add(Dgii606(
                empresa_id=emp.id, periodo=f"{anio_str}02", rnc_proveedor=f"999{i}",
                monto_facturado=20000.0, itbis_facturado=0,
                tipo_bien_servicio=2, ncf=f"B1300000{i}", anulada=0
            ))
             
        # ESCENARIO C: TSS vs B-1 Descuadrado
        db.add(TssNomina(empresa_id=emp.id, periodo=f"{anio_str}01", empleados=10, 
                         salario_cotizable=100000, aporte_empresa=15000))
        
        # Simulamos Estado Financiero con gasto de nomina inflado (40% de ingresos)
        db.add(EstadoFinanciero(empresa_id=emp.id, periodo=anio_str, 
                                ventas_totales=1000000, gastos_personal=400000))
        
        db.commit()

        # 2. Ejecutar Auditoria
        print("\n>>> Ejecutando Auditoria Nivel Socio Senior...")
        ejecutar_auditoria_fiscal(db, rnc_test, anio)

        # 3. Verificar resultados en DB
        alertas = db.query(ValidacionFiscal).filter(
            and_(ValidacionFiscal.empresa_id == emp.id, ValidacionFiscal.tipo_validacion.like("SOCIO_%"))
        ).all()

        print(f"\n[RESULTADO] Se detectaron {len(alertas)} Red Flags criticas.")
        
        for a in alertas:
            print(f"\n[FLAG] TIPO: {a.tipo_validacion}")
            print(f"   RECOMENDACION: {a.recomendacion_socio}")
            print(f"   ASIENTO: {a.asiento_propuesto}")

        assert len(alertas) >= 3, "El motor no detecto todos los escenarios de riesgo"
        print("\n[Veredicto] PASSED: El motor de auditoria experta es consciente de los riesgos fiscales.")

    finally:
        db.rollback()
        db.close()

if __name__ == "__main__":
    test_escenarios_red_flag()
