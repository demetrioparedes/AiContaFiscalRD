"""
core/etl_ir17.py — Motor de Generación Mansual de IR-17
======================================================
Extrae las retenciones de ISR e ITBIS desde el formulario 606
y las consolida en la tabla dgii_ir17.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import SessionLocal, Empresa, Dgii606, DgiiIr17
from sqlalchemy import func, and_
from decimal import Decimal, ROUND_HALF_UP

def procesar_ir17_mensual(db, rnc_empresa: str, anio: int):
    """
    Genera el IR-17 para todos los meses del año fiscal basándose en el 606.
    """
    print(f"\n[Módulo IR-17] Generando declaraciones mensuales para {anio}...")
    
    empresa = db.query(Empresa).filter_by(rnc=rnc_empresa).first()
    if not empresa:
        print("  [!] Error: Empresa no encontrada.")
        return
    
    emp_id = empresa.id
    anio_str = str(anio)
    
    # Obtener todos los periodos con data en el 606 para este año
    periodos = db.query(Dgii606.periodo).filter(
        and_(Dgii606.empresa_id == emp_id, Dgii606.periodo.like(f"{anio_str}%"))
    ).distinct().all()
    
    for (periodo,) in sorted(periodos):
        # Limpiar registro previo si existe
        db.query(DgiiIr17).filter_by(empresa_id=emp_id, periodo=periodo).delete()
        
        # 1. Agrupar retenciones de ISR por Tipo de Bien o Servicio (606)
        # 02 = Honorarios/Servicios (10% o 2%)
        # 03 = Alquileres (10%)
        
        # Heurística de clasificación:
        # Si Tipo == 3 -> Alquileres
        # Si Tipo == 2:
        #    - Si Retención / Monto ~ 0.10 -> Honorarios
        #    - Si Retención / Monto ~ 0.02 -> Servicios Técnicos
        #    - Otros -> Otros Pagos
        
        registros_606 = db.query(Dgii606).filter(
            and_(Dgii606.empresa_id == emp_id, 
                 Dgii606.periodo == periodo,
                 Dgii606.isr_retenido > 0)
        ).all()
        
        ir17 = DgiiIr17(empresa_id=emp_id, periodo=periodo)
        itbis_total_retenido = Decimal("0.00")
        
        for reg in registros_606:
            monto = Decimal(str(reg.monto_facturado))
            retenido = Decimal(str(reg.isr_retenido))
            tipo = reg.tipo_bien_servicio
            itbis_total_retenido += Decimal(str(reg.itbis_retenido or 0))
            
            # Clasificación por tipo de gasto de la DGII
            if tipo == 3: # Arrendamientos
                ir17.alquileres += retenido
            elif tipo == 2: # Trabajos y Servicios
                # Validar tasa aproximada
                tasa = (retenido / monto) if monto > 0 else 0
                if 0.09 <= tasa <= 0.11:
                    ir17.honorarios += retenido
                elif 0.015 <= tasa <= 0.025:
                    ir17.servicios_tecnicos += retenido
                else:
                    ir17.otros_pagos += retenido
            else:
                ir17.otros_pagos += retenido
        
        # ITBIS Retenido total
        ir17.itbis_retenido_terceros = itbis_total_retenido
        
        # Totales
        ir17.total_is_retenido = (
            ir17.alquileres + ir17.honorarios + ir17.servicios_tecnicos + 
            ir17.otros_pagos + ir17.dividendos
        )
        ir17.total_a_pagar = ir17.total_is_retenido + ir17.itbis_retenido_terceros + ir17.retribuciones_complementarias
        
        db.add(ir17)
        print(f"  [+] IR-17 Generado para {periodo}: Total a Pagar RD$ {ir17.total_a_pagar:,.2f}")
    
    db.commit()
    print("  [OK] Proceso IR-17 completado.")

if __name__ == "__main__":
    db = SessionLocal()
    try:
        procesar_ir17_mensual(db, "130826552", 2025)
    finally:
        db.close()
