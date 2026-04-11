import sys
import os
import pytest
from decimal import Decimal
from datetime import date

# Añadir la raíz del proyecto al sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.etl_ingesta import (
    normalizar_rnc,
    parsear_ncf,
    limpiar_monto,
    normalizar_fecha,
    detectar_periodo
)

# ===========================================================
# TESTS: normalizar_rnc
# ===========================================================
def test_normalizar_rnc_valido():
    assert normalizar_rnc("130-82655-2") == "130826552"
    assert normalizar_rnc("101019921") == "101019921"

def test_normalizar_rnc_invalido():
    assert normalizar_rnc("ABC") is None
    assert normalizar_rnc("123") is None  # Demasiado corto
    assert normalizar_rnc("123456789012") is None  # Demasiado largo
    assert normalizar_rnc("") is None

# ===========================================================
# TESTS: parsear_ncf
# ===========================================================
def test_parsear_ncf_estandar():
    tipo, secuencia = parsear_ncf("B0100000001")
    assert tipo == "B01"
    assert secuencia == "00000001"

def test_parsear_ncf_electronico():
    tipo, secuencia = parsear_ncf("E310000143013")
    assert tipo == "E31"
    assert secuencia == "0000143013"

def test_parsear_ncf_invalido():
    tipo, secuencia = parsear_ncf("INVALIDO")
    assert tipo is None
    assert secuencia is None

# ===========================================================
# TESTS: limpiar_monto (PRECISIÓN CRÍTICA)
# ===========================================================
def test_limpiar_monto_formatos():
    assert limpiar_monto("1,270.62") == Decimal("1270.62")
    assert limpiar_monto("  500.5 ") == Decimal("500.50")
    assert limpiar_monto(100.25) == Decimal("100.25")

def test_limpiar_monto_redondeo_dgii():
    # La DGII usa ROUND_HALF_UP (0.005 -> 0.01)
    assert limpiar_monto("10.005") == Decimal("10.01")
    assert limpiar_monto("10.004") == Decimal("10.00")

def test_limpiar_monto_basura():
    assert limpiar_monto("NaN") == Decimal("0.00")
    assert limpiar_monto("None") == Decimal("0.00")
    assert limpiar_monto(None) == Decimal("0.00")

# ===========================================================
# TESTS: normalizar_fecha
# ===========================================================
def test_normalizar_fecha_formatos():
    assert normalizar_fecha("2025-01-20") == date(2025, 1, 20)
    assert normalizar_fecha("20/01/2025") == date(2025, 1, 20)
    assert normalizar_fecha("01/20/2025") == date(2025, 1, 20)
    assert normalizar_fecha("20250120") == date(2025, 1, 20)

def test_normalizar_fecha_invalida():
    assert normalizar_fecha("fecha-loca") is None
    assert normalizar_fecha("") is None

# ===========================================================
# TESTS: detectar_periodo
# ===========================================================
def test_detectar_periodo():
    d = date(2025, 3, 15)
    assert detectar_periodo(d) == "202503"

def test_detectar_periodo_nulo():
    # Si es nulo debe retornar el periodo actual (YYYYMM)
    from datetime import datetime
    actual = datetime.now().strftime("%Y%m")
    assert detectar_periodo(None) == actual
