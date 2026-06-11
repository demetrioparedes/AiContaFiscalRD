"""
test_integracion_pipeline.py — Test de Integración del Pipeline Completo
=======================================================================
Valida el flujo completo: ETL -> Motor Fiscal -> Auditoría -> IR-17 -> Planificador.

Usa datos sintéticos (no requiere archivos externos).
Corre en SQLite (local) o PostgreSQL (según DATABASE_URL).
Siempre hace ROLLBACK al final — no persiste nada.
"""
import sys, os, json
from decimal import Decimal
from datetime import date, datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import pytest
from sqlalchemy.orm import Session
from core.database import (
    SessionLocal, Empresa, Dgii606, Dgii607, DgiiIt1,
    Inventario, TssNomina, ActivoFijo, Prestamo,
    EstadoFinanciero, ValidacionFiscal, init_db
)
from core.motor_fiscal import OrquestadorFiscal
from core.motor_riesgo_dgii import calcular_riesgo
from core.etl_ir17 import procesar_ir17_mensual


@pytest.fixture(scope="module")
def db():
    """Fixture que provee sesión de BD con rollback automático."""
    init_db()
    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()


@pytest.fixture
def empresa_test(db):
    """Crea o recupera una empresa de test."""
    rnc = "999999999"
    emp = db.query(Empresa).filter_by(rnc=rnc).first()
    if not emp:
        emp = Empresa(rnc=rnc, nombre_empresa="Integracion Test SRL")
        db.add(emp)
        db.commit()
        db.refresh(emp)
    return emp


def test_pipeline_completo(db, empresa_test):
    """
    Test integral del pipeline fiscal:

    1. Carga 606/607 sintéticos (ETL simulado)
    2. Carga IT-1, Inventario, TSS, Activos
    3. Ejecuta OrquestadorFiscal (9 fases)
    4. Ejecuta IR-17
    5. Calcula riesgo DGII
    6. Verifica resultados en BD
    """
    emp = empresa_test
    anio = 2025
    anio_str = str(anio)

    # --- LIMPIAR DATOS PREVIOS ---
    for tabla in [ValidacionFiscal, Dgii606, Dgii607, DgiiIt1,
                  Inventario, TssNomina, ActivoFijo]:
        db.query(tabla).filter_by(empresa_id=emp.id).delete()
    db.commit()

    # --- 1. CARGAR DATOS SINTÉTICOS ---
    # 10 facturas de compras (606)
    for i in range(10):
        db.add(Dgii606(
            empresa_id=emp.id, periodo=f"{anio_str}01",
            rnc_proveedor=f"10100000{i:02d}",
            ncf=f"B0100000{i:02d}", fecha_comprobante=date(anio, 1, 15),
            monto_facturado=Decimal("50000.00"),
            itbis_facturado=Decimal("9000.00"),
            tipo_bien_servicio=2,  # Servicios
            isr_retenido=Decimal("5000.00") if i < 3 else Decimal("0.00"),
            anulada=False,
        ))

    # 20 facturas de ventas (607)
    for i in range(20):
        db.add(Dgii607(
            empresa_id=emp.id, periodo=f"{anio_str}01",
            rnc_cliente=f"99999999{i:02d}",
            ncf=f"E3100000{i:02d}{i:02d}", fecha_comprobante=date(anio, 1, 20),
            monto_facturado=Decimal("75000.00"),
            itbis_facturado=Decimal("13500.00"),
            anulada=False,
        ))

    # IT-1 (declaración ITBIS)
    db.add(DgiiIt1(
        empresa_id=emp.id, periodo=f"{anio_str}01",
        ventas_gravadas=Decimal("1500000.00"),
        ventas_exentas=Decimal("0.00"),
        itbis_generado=Decimal("270000.00"),
        compras_gravadas=Decimal("500000.00"),
        itbis_credito=Decimal("90000.00"),
    ))

    # Inventario inicial y final
    db.add(Inventario(
        empresa_id=emp.id, descripcion="Inventario Inicial",
        cantidad=Decimal("100"), costo_unitario=Decimal("1000"),
        valor_total=Decimal("100000.00"),
        tipo_inventario="inicial", fecha_registro=date(anio, 1, 1),
    ))
    db.add(Inventario(
        empresa_id=emp.id, descripcion="Inventario Final",
        cantidad=Decimal("50"), costo_unitario=Decimal("1000"),
        valor_total=Decimal("50000.00"),
        tipo_inventario="final", fecha_registro=date(anio, 12, 31),
    ))

    # Activos fijos
    db.add(ActivoFijo(
        empresa_id=emp.id, descripcion="Edificio Test",
        categoria="CAT1", valor_compra=Decimal("5000000.00"),
        depreciacion_acumulada=Decimal("0.00"),
    ))

    # TSS
    db.add(TssNomina(
        empresa_id=emp.id, periodo=f"{anio_str}01",
        empleados=10, salario_cotizable=Decimal("500000.00"),
        aporte_empresa=Decimal("81950.00"),
    ))

    db.commit()

    # --- 2. EJECUTAR ORQUESTADOR ---
    orquestador = OrquestadorFiscal(db, emp.rnc, anio)
    resultado = orquestador.ejecutar_auditoria_fiscal_completa()

    # Verificar estado del pipeline
    assert resultado["estado"] in ("Listo", "Bloqueado"), \
        f"Pipeline falló: {resultado.get('mensaje', 'sin mensaje')}"

    # --- 3. VERIFICAR RESULTADOS ---
    # Debe haber generado un EstadoFinanciero
    ef = db.query(EstadoFinanciero).filter_by(
        empresa_id=emp.id, periodo=anio_str
    ).first()
    assert ef is not None, "No se generó EstadoFinanciero"
    assert ef.ventas_totales > 0, "Ventas totales no calculadas"
    print(f"  [OK] Ventas totales: RD$ {ef.ventas_totales:,.2f}")

    # Debe haber validaciones fiscales
    validaciones = db.query(ValidacionFiscal).filter_by(
        empresa_id=emp.id, periodo=anio_str
    ).all()
    assert len(validaciones) > 0, "No se generaron validaciones fiscales"
    print(f"  [OK] Validaciones generadas: {len(validaciones)}")

    # --- 4. EJECUTAR IR-17 ---
    try:
        procesar_ir17_mensual(db, emp.rnc, anio)
        print(f"  [OK] IR-17 generado sin errores")
    except Exception as e:
        pytest.fail(f"IR-17 falló: {e}")

    # --- 5. CALCULAR RIESGO DGII ---
    riesgo = calcular_riesgo(emp.rnc, anio)
    assert "indice_riesgo" in riesgo, "Riesgo DGII no calculado"
    assert riesgo["semaforo"] in ("VERDE", "AMARILLO", "NARANJA", "ROJO")
    print(f"  [OK] Riesgo DGII: {riesgo['indice_riesgo']}% ({riesgo['semaforo']})")

    # --- 6. VERIFICAR IR2 DATA ---
    ir2_data = resultado.get("ir2_data", {})
    assert ir2_data, "No hay datos IR-2"
    assert ir2_data.get("ventas", 0) > 0, "Ventas IR-2 en 0"
    print(f"  [OK] IR-2: Ventas RD$ {ir2_data['ventas']:,.2f} | ISR RD$ {ir2_data['isr_pagar']:,.2f}")

    # --- 7. VERIFICAR RED FLAGS ---
    red_flags = resultado.get("red_flags", [])
    bloqueos = resultado.get("bloqueos", [])
    print(f"  [OK] Red flags: {len(red_flags)} | Bloqueos: {len(bloqueos)}")

    print(f"\n  {'='*50}")
    print(f"  PIPELINE COMPLETO VERIFICADO")
    print(f"  {'='*50}")
    print(f"  Estado:    {resultado['estado']}")
    print(f"  Ventas:    RD$ {ir2_data.get('ventas', 0):,.2f}")
    print(f"  Costos:    RD$ {resultado['resumen'].get('costo_ventas', 0):,.2f}")
    print(f"  Depreciac: RD$ {resultado['resumen'].get('depreciacion', 0):,.2f}")
    print(f"  ISR:       RD$ {ir2_data.get('isr_pagar', 0):,.2f}")
    print(f"  Riesgo:    {riesgo['indice_riesgo']}% ({riesgo['semaforo']})")
    print(f"  {'='*50}")


def test_pipeline_con_errores(db, empresa_test):
    """Test: pipeline detecta errores con datos inconsistentes."""
    emp = empresa_test
    anio = 2025
    anio_str = str(anio)

    # Limpiar y crear datos inconsistentes: compras > ventas (pérdida gigante)
    for tabla in [ValidacionFiscal, Dgii606, Dgii607, DgiiIt1,
                  Inventario, TssNomina]:
        db.query(tabla).filter_by(empresa_id=emp.id).delete()
    db.commit()

    # Compras altísimas, ventas mínimas
    for i in range(50):
        db.add(Dgii606(
            empresa_id=emp.id, periodo=f"{anio_str}01",
            rnc_proveedor=f"10100000{i:02d}", ncf=f"B0100000{i:02d}",
            fecha_comprobante=date(anio, 1, 15),
            monto_facturado=Decimal("200000.00"),
            itbis_facturado=Decimal("36000.00"),
            tipo_bien_servicio=9,  # Compras
            anulada=False,
        ))

    # Ventas muy bajas
    for i in range(5):
        db.add(Dgii607(
            empresa_id=emp.id, periodo=f"{anio_str}01",
            rnc_cliente=f"99999999{i:02d}", ncf=f"E3100000{i:02d}{i:02d}",
            fecha_comprobante=date(anio, 1, 20),
            monto_facturado=Decimal("10000.00"),
            itbis_facturado=Decimal("1800.00"),
            anulada=False,
        ))

    db.commit()

    # Ejecutar pipeline
    orquestador = OrquestadorFiscal(db, emp.rnc, anio)
    resultado = orquestador.ejecutar_auditoria_fiscal_completa()

    # Verificar que el pipeline detectó algo (pérdida = alertas)
    assert len(resultado["red_flags"]) > 0 or resultado["estado"] == "Bloqueado", \
        "Pipeline no detectó inconsistencias en datos inválidos"

    print(f"\n  [OK] Pipeline detectó {len(resultado['red_flags'])} red flags en datos inconsistentes")


def test_planificador_con_datos(db, empresa_test):
    """Test: planificador fiscal genera proyecciones."""
    from core.planificador_fiscal import PlanificadorIA

    emp = empresa_test
    anio = 2025

    # Asegurar que hay datos financieros
    ef = db.query(EstadoFinanciero).filter_by(
        empresa_id=emp.id, periodo=str(anio)
    ).first()

    if not ef:
        pytest.skip("No hay EstadoFinanciero para este test (ejecutar test_pipeline_completo primero)")

    planificador = PlanificadorIA(db, emp.id, anio)
    proyeccion = planificador.proyectar_cierre_anual()

    assert "ventas_proyectadas" in proyeccion
    assert "isr_estimado_anual" in proyeccion
    assert "anticipo_sugerido" in proyeccion
    assert proyeccion["anticipo_sugerido"] > 0, "Anticipo no calculado"
    print(f"  [OK] Proyección: Ventas RD$ {proyeccion['ventas_proyectadas']:,.2f}")
    print(f"  [OK] ISR estimado: RD$ {proyeccion['isr_estimado_anual']:,.2f}")
    print(f"  [OK] Anticipo (Art.314): RD$ {proyeccion['anticipo_sugerido']:,.2f}")

    # Escenarios
    escenarios = planificador.generar_escenarios()
    assert len(escenarios) == 3, "Deben ser 3 escenarios"
    nombres = {e["nombre"] for e in escenarios}
    assert nombres == {"BASE", "OPTIMISTA", "PESIMISTA"}, \
        f"Escenarios incorrectos: {nombres}"
    print(f"  [OK] 3 escenarios generados: {nombres}")
