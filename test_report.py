import sys, os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
from decimal import Decimal
from database import SessionLocal, Empresa, Dgii606, EstadoFinanciero, ValidacionFiscal
from etl_ingesta import ejecutar_etl
from motor_fiscal import calcular_estado_resultados, ejecutar_auditoria_fiscal
from sqlalchemy import func, and_, or_

def main():
    sys.stdout = open(r"c:\GEMINI\AiContaFiscalRD\resultado_humo.txt", "w", encoding="utf-8")
    try:
        rnc = "130826552"
        anio = 2025
        anio_str = str(anio)
        db = SessionLocal()
        
        empresa = db.query(Empresa).filter_by(rnc=rnc).first()
        if empresa:
            emp_id = empresa.id
            db.query(Dgii606).filter_by(empresa_id=emp_id, periodo=str(202501)).delete()
            db.query(EstadoFinanciero).filter_by(empresa_id=emp_id, periodo=anio_str).delete()
            db.query(ValidacionFiscal).filter_by(empresa_id=emp_id, periodo=anio_str).delete()
            db.commit()
    
        # 1. EJECUTAR ETL
        directorio = r"C:\GEMINI\AiContaFiscalRD\data\clientes\130826552"
        ejecutar_etl(directorio, rnc, anio)
        
        # Reconectar / refrescar empresa ID
        empresa = db.query(Empresa).filter_by(rnc=rnc).first()
        emp_id = empresa.id
        
        # 2. CALCULAR ETADO RESULTADOS
        er = calcular_estado_resultados(db, rnc, anio)
        
        # 3. EJECUTAR AUDITORIA
        ejecutar_auditoria_fiscal(db, rnc, anio)
        
        # Consultar metricas 606
        regs_procesados = db.query(Dgii606).filter_by(empresa_id=emp_id, periodo=str(202501)).count()
        regs_anulados = db.query(Dgii606).filter_by(empresa_id=emp_id, periodo=str(202501), anulada=1).count()
        
        # Consultar Banderas
        banderas = db.query(ValidacionFiscal).filter_by(empresa_id=emp_id, periodo=anio_str).all()
        
        gastos_sin_ncf = Decimal(str(db.query(func.sum(Dgii606.monto_facturado)).filter(
            and_(Dgii606.empresa_id == emp_id, Dgii606.periodo.like(f"{anio_str}%"), Dgii606.anulada != 1,
                 or_(Dgii606.ncf == None, Dgii606.ncf == "", Dgii606.ncf == "N/A"))
        ).scalar() or 0))

        print("\nRESULTADOS DEL MOTOR — RNC 130826552 / 2025")
        print("─────────────────────────────────────────────")
        print(f"Registros procesados del 606:     {regs_procesados}")
        print(f"Registros anulados detectados:    {regs_anulados}\n")
        
        print(f"Ventas totales:                   RD$ {er.ventas_totales:>15,.2f}")
        print(f"Costo de ventas:                  RD$ {er.costo_ventas:>15,.2f}")
        print(f"Gastos operativos:                RD$ {er.gastos_operativos:>15,.2f}")
        print(f"Utilidad operativa:               RD$ {er.utilidad_bruta - er.gastos_operativos:>15,.2f}\n")
        
        print(f"Gastos sin NCF (no deducibles):   RD$ {gastos_sin_ncf:>15,.2f}")
        print(f"Ingresos exentos:                 RD$ {er.ventas_exentas:>15,.2f}")
        print(f"Pérdidas compensables:            RD$ {'0.00':>15}")
        print("─────────────────────────────────────────────")
        print(f"RENTA IMPONIBLE:                  RD$ {er.renta_imponible:>15,.2f}")
        print(f"ISR BRUTO (27%):                  RD$ {er.renta_imponible * Decimal('0.27'):>15,.2f}")
        print(f"Anticipos pagados:                RD$ {er.anticipos:>15,.2f}")
        print(f"Retenciones aplicables:           RD$ {er.retenciones:>15,.2f}")
        print(f"ISR A PAGAR:                      RD$ {er.isr_calcular:>15,.2f}")
        print("─────────────────────────────────────────────\n")
        
        print("BANDERAS DISPARADAS:")
        for b in banderas:
            estado = "VERDE" if b.estado == "OK" else ("AMARILLO" if b.estado == "ALERTA" else "ROJO")
            print(f"[{estado}] {b.tipo_validacion} | Sist: {b.valor_sistema:,.2f} | DGII: {b.valor_dgii:,.2f} | Dif: {b.diferencia:,.2f}")
            
    except Exception as e:
        import traceback
        traceback.print_exc()
    sys.stdout.close()
        
if __name__ == '__main__':
    main()
