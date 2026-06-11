import sys, os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
from decimal import Decimal
from database import SessionLocal
from motor_fiscal import calcular_estado_resultados

db = SessionLocal()
er = calcular_estado_resultados(db, "130826552", 2025)
if er:
    renta_im = Decimal(str(er.renta_imponible))
    isr_bruto = renta_im * Decimal("0.27")
    isr_neto = Decimal(str(er.isr_calcular))
    
    print("\n")
    print("=================================================")
    print("  RESULTADOS PRUEBA END-TO-END (IR-2 LEY 11-92)")
    print("=================================================")
    print(f"Renta Imponible (Ajustada): RD$ {renta_im:>15,.2f}")
    print(f"ISR Bruto al 27%:           RD$ {isr_bruto:>15,.2f}")
    print(f"ISR a Pagar (Neto):         RD$ {isr_neto:>15,.2f}")
    print("=================================================\n")
