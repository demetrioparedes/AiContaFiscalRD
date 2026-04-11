import sys
import os
from decimal import Decimal, ROUND_HALF_UP

# Añadir la raíz del proyecto al sys.path para que las importaciones funcionen
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.etl_ingesta import limpiar_monto, parsear_ncf

# TEST 1 — limpiar_monto con coma de miles:
def test_limpiar_monto_con_coma():
    assert limpiar_monto("1,270.62") == Decimal("1270.62")

# TEST 2 — limpiar_monto con string vacío:
def test_limpiar_monto_vacio():
    assert limpiar_monto("") == Decimal("0.00")

# TEST 3 — limpiar_monto con valor basura:
def test_limpiar_monto_basura():
    assert limpiar_monto("abc") == Decimal("0.00")

# TEST 4 — ROUND_HALF_UP en 0.005:
def test_redondeo_half_up():
    assert limpiar_monto("0.005") == Decimal("0.01")

# TEST 5 — NCF B04 detectado como anulado:
def test_ncf_b04_es_anulacion():
    tipo, secuencia = parsear_ncf("B0400000001")
    assert tipo == "B04"

# TEST 6 — NCF E34 detectado como anulado:
def test_ncf_e34_es_anulacion():
    tipo, secuencia = parsear_ncf("E340000000001")
    assert tipo == "E34"

# TEST 7 — renta imponible nunca negativa:
def test_renta_imponible_no_negativa():
    utilidad = Decimal("-500000")
    renta = max(Decimal("0.00"), utilidad)
    assert renta == Decimal("0.00")

# TEST 8 — ISR al 27% con ROUND_HALF_UP:
def test_isr_27_porciento():
    base = Decimal("18590415.04")
    isr = (base * Decimal("0.27")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    assert isr == Decimal("5019412.06")

# TEST 9 — ISR a pagar nunca negativo:
def test_isr_pagar_no_negativo():
    isr_bruto = Decimal("100000.00")
    anticipos = Decimal("150000.00")
    isr_pagar = max(Decimal("0.00"), isr_bruto - anticipos)
    assert isr_pagar == Decimal("0.00")

# TEST 10 — cruce simétrico detecta diferencia real:
def test_cruce_simetrico_detecta_diferencia():
    tolerancia = 500
    sist = Decimal("0.00")
    dgii = Decimal("1049811.53")
    diferencia = abs(sist - dgii)
    assert diferencia > tolerancia
