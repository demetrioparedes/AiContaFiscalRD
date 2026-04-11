"""
etl_tss_ir13.py — Extractor de TSS e IR-13 desde el Excel del Despacho
========================================================================
Lee el archivo estándar "IR-13 y TSS XXXX.xls" que usa el Despacho PGA para cada cliente.

Datos disponibles en el archivo actual de Elvira:
  SECCION TSS (Completa):
    - 12 pagos mensuales de Seguridad Social
    - Total TSS Empleador: RD$ 301,061.18
    - Desglose: AFP (45%), SFS (46%), RL (9%)

  SECCION IR-13 (Incompleta):
    - Cabeceras correctas (NRP, NSS, Salario, Ret.Seg.Social, ISR, etc.)
    - Solo un registro con salario anual (RD$ 1,143,000) pero SIN detalle de empleados
    - DATOS FALTANTES: cédulas, NSS individuales, monto de ISR por empleado

El sistema procesa lo disponible y genera alertas sobre lo que falta.
"""
import sys, os
sys.path.insert(0, r"c:\GEMINI\AiContaFiscalRD\core")

import xlrd
from database import SessionLocal, TssNomina, Ir18Retenciones, Empresa

def serial_a_mes(serial):
    """Convierte serial Excel a YYYY-MM."""
    try:
        if not serial or serial == 0:
            return None
        dt = xlrd.xldate_as_datetime(float(serial), 0)
        return dt.strftime("%Y-%m")
    except:
        return None

def limpiar_monto(valor):
    """Limpia montos que vienen como string con comas."""
    if isinstance(valor, str):
        return float(valor.replace(",", "").strip() or 0)
    return float(valor or 0)


def extraer_tss(hoja, rnc_empresa, anio):
    """Extrae los pagos mensuales de TSS de la hoja."""
    print("\n[TSS] Extrayendo pagos de Seguridad Social...")
    pagos = []
    total_tss = 0.0

    # Detectar filas de TSS: col[1] = "Pagada", col[5] = monto
    for r in range(hoja.nrows):
        row = hoja.row_values(r)
        if len(row) < 10 or str(row[1]).strip() != "Pagada":
            continue

        # Período del pago es col[3] (serial Excel del mes pagado)
        periodo = serial_a_mes(row[3])  # Mes al que corresponde el pago
        if not periodo:
            continue

        monto = limpiar_monto(row[9])  # Col 9: Total TSS
        if monto <= 0:
            continue

        # Solo incluir pagos del año fiscal
        if not periodo.startswith(str(anio)):
            continue

        pagos.append({"mes": periodo, "monto": monto})
        total_tss += monto
        print(f"  [TSS] {periodo}: RD$ {monto:>12,.2f}")

    # Buscar el desglose AFP/SFS/RL (filas 32-35 aprox)
    afp = sfs = rl = 0.0
    for r in range(hoja.nrows):
        row = hoja.row_values(r)
        if len(row) < 3:
            continue
        label = str(row[0]).strip().upper()
        if label == "AFP" and row[2]:
            afp = float(row[2])
        elif label == "SFS" and row[2]:
            sfs = float(row[2])
        elif label == "RL" and row[2]:
            rl = float(row[2])

    print(f"\n  [TSS] DESGLOSE ANUAL:")
    print(f"         AFP:  RD$ {afp:>12,.2f}  (45%)")
    print(f"         SFS:  RD$ {sfs:>12,.2f}  (46%)")
    print(f"         RL:   RD$ {rl:>12,.2f}   (9%)")
    print(f"  [TSS] TOTAL: RD$ {total_tss:>12,.2f}  ({len(pagos)} pagos)")

    return pagos, total_tss


def extraer_ir13(hoja, rnc_empresa):
    """Extrae los datos del IR-13 (retenciones a asalariados). Genera alertas si falta info."""
    print("\n[IR13] Extrayendo datos de retenciones a asalariados...")
    alertas = []
    empleados = []
    salario_total = 0.0
    isr_total = 0.0

    # Buscar fila de headers del IR-13
    headers_encontrados = False
    for r in range(hoja.nrows):
        row = hoja.row_values(r)
        # Detectar fila de encabezados
        if any("SALARIO" in str(v).upper() for v in row):
            headers_encontrados = True
            continue

        # Después de los headers, leer filas de datos de empleados
        if headers_encontrados and len(row) >= 13:
            nrp    = row[0]
            nss    = row[1]
            nombre = str(row[2]).strip()
            apell  = str(row[3]).strip()
            ced    = str(row[4]).strip()
            sal    = float(row[5]) if row[5] else 0.0
            isr    = float(row[12]) if len(row) > 12 and row[12] else 0.0

            # Parar si llegamos a la sección TSS
            if str(row[0]).upper().startswith("TSS"):
                break

            # Solo filas con datos válidos
            if sal > 0 or nss or nombre:
                emp = {
                    "nrp": nrp, "nss": str(nss).strip(),
                    "nombre": f"{nombre} {apell}".strip(),
                    "cedula": ced, "salario": sal, "isr": isr
                }
                empleados.append(emp)
                salario_total += sal
                isr_total += isr

                # Detectar datos faltantes para este empleado
                if not nss or str(nss).strip() in ["", "0.0"]:
                    alertas.append(f"  [!FALTA] Empleado '{emp['nombre']}': NSS no proporcionado")
                if not ced or str(ced).strip() in ["", "0.0"]:
                    alertas.append(f"  [!FALTA] Empleado '{emp['nombre']}': Cédula no proporcionada")
                if sal > 0 and isr == 0:
                    alertas.append(f"  [!FALTA] Empleado '{emp['nombre']}': Salario={sal:,.0f} pero ISR=0 (¿exento o sin detallar?)")

    # Análisis de completitud del IR-13
    if salario_total > 0 and isr_total == 0:
        alertas.append("  [!!CRITICO] El IR-13 muestra salarios pero NO tiene ISR calculado por empleado.")
        alertas.append("              Necesario para completar Casilla 22 del IR-2 (Retenciones Sufridas).")

    if not empleados:
        alertas.append("  [!!CRITICO] No se encontraron empleados con detalle en el IR-13.")

    return empleados, salario_total, isr_total, alertas


def guardar_en_bd(pagos_tss, total_tss, empleados, rnc, anio, db):
    # Relacionar RNC a ID de empresa
    empresa = db.query(Empresa).filter_by(rnc=rnc).first()
    emp_id = empresa.id if empresa else None

    # Limpiar datos anteriores
    if emp_id:
        db.query(TssNomina).filter_by(empresa_id=emp_id, periodo=str(anio)).delete()
        db.query(Ir18Retenciones).filter_by(empresa_id=emp_id).delete()

    for p in pagos_tss:
        db.add(TssNomina(
            empresa_id=emp_id,
            periodo=str(anio) + p["mes"][-2:], # "202501" etc
            empleados=1,
            salario_cotizable=0.0,
            aporte_empresa=p["monto"]
        ))

    for emp in empleados:
        if emp["salario"] > 0 or emp["isr"] > 0:
            db.add(Ir18Retenciones(
                empresa_id=emp_id,
                empleado=emp["nombre"],
                cedula=emp["cedula"] or "PENDIENTE",
                salario=emp["salario"],
                retencion_isr=emp["isr"]
            ))

    db.commit()


def procesar_tss_ir13(ruta_archivo, rnc_empresa, anio):
    """Función principal universal para cualquier cliente."""
    print("=" * 65)
    print(f"  ETL TSS + IR-13: {os.path.basename(ruta_archivo)}")
    print(f"  RNC: {rnc_empresa} | Año: {anio}")
    print("=" * 65)

    wb = xlrd.open_workbook(ruta_archivo)
    hoja = wb.sheet_by_index(0)
    print(f"  [i] Hoja: '{hoja.name}' ({hoja.nrows} filas)")

    # Extraer TSS (completa)
    pagos_tss, total_tss = extraer_tss(hoja, rnc_empresa, anio)

    # Extraer IR-13 (puede estar incompleto)
    empleados, salario_total, isr_total, alertas = extraer_ir13(hoja, rnc_empresa)

    # Guardar en BD
    db = SessionLocal()
    try:
        guardar_en_bd(pagos_tss, total_tss, empleados, rnc_empresa, anio, db)
    finally:
        db.close()

    # =======================================================
    # PANEL DE ALERTAS Y DATOS FALTANTES
    # =======================================================
    print("\n" + "=" * 65)
    print("  RESUMEN TSS:")
    print(f"  Pagos TSS procesados:   {len(pagos_tss)} meses")
    print(f"  Total TSS 2025:         RD$ {total_tss:>12,.2f}  <- Gasto Nomina")

    print("\n  RESUMEN IR-13:")
    if empleados:
        print(f"  Empleados encontrados:  {len(empleados)}")
        print(f"  Salario total anual:    RD$ {salario_total:>12,.2f}")
        print(f"  ISR total retenido:     RD$ {isr_total:>12,.2f}")
    else:
        print("  Sin detalle por empleado disponible.")

    if alertas:
        print("\n" + "-" * 65)
        print("  [AVISO] - DATOS FALTANTES EN EL IR-13:")
        print("-" * 65)
        for a in alertas:
            print(f"  {a}")
        print("\n  ACCION REQUERIDA DEL USUARIO:")
        print("  Para completar el IR-13, proporciona el formulario oficial")
        print("  descargado del OFV (Oficina Virtual DGII) con:")
        print("   -> NSS de cada empleado")
        print("   -> Cedula de cada empleado")
        print("   -> Salario mensual por empleado")
        print("   -> ISR retenido por empleado (si aplica)")
        print("   -> Total de retenciones para la Casilla 22 del IR-2")
        print("-" * 65)

    print("\n  IMPACTO EN EL IR-2:")
    print(f"  Gastos Nomina (TSS):     RD$ {total_tss:>12,.2f}  -> Disponible (Anexo A)")
    print(f"  Retenciones IR-13:       RD$ {isr_total:>12,.2f}  -> {'OK' if isr_total > 0 else 'PENDIENTE (Casilla 22)'}")
    print("=" * 65)

    return total_tss, isr_total, alertas


if __name__ == "__main__":
    procesar_tss_ir13(
        ruta_archivo=r"G:\Mi unidad\Backup NAS (NO TOCAR)\PGA\13 DECLARACION IR-2 2025\IR-2 2025 ELVIRA\IR-13 y TSS 2025.xls",
        rnc_empresa="130826552",
        anio=2025
    )
