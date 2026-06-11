"""
AiContaFiscalRD — Paquete de Lógica Fiscal.
Asegura que core/ esté en sys.path para que 'from database import ...'
funcione tanto desde la API como desde pruebas y ejecución directa.
"""
import sys, os

_core_dir = os.path.dirname(os.path.abspath(__file__))
if _core_dir not in sys.path:
    sys.path.insert(0, _core_dir)

# También asegurar que la raíz del proyecto esté disponible para imports absolutos
BASE_DIR = os.path.dirname(_core_dir)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
