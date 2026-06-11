"""
Importa datos de JSON a PostgreSQL (Supabase).
"""
import sys, os, json
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

import psycopg2
from psycopg2.extras import execute_values

CONN_STR = {
    "host": "aws-1-us-east-1.pooler.supabase.com",
    "port": 6543,
    "user": "postgres.ronevguwdmadgwodxqft",
    "password": "MasterOdyn2025#",
    "dbname": "postgres",
    "sslmode": "require"
}

MODELO_COLS = {
    "empresas": ["id","rnc","nombre_empresa","direccion","telefono","email","fecha_creacion"],
    "padron_dgii": ["id","rnc","razon_social","actividad_economica","fecha_inicio","estado","regimen_pago"],
    "dgii_606": ["id","empresa_id","periodo","rnc_proveedor","tipo_identificacion","ncf","ncf_modificado",
                 "fecha_comprobante","fecha_pago","tipo_bien_servicio","monto_facturado","itbis_facturado",
                 "itbis_retenido","isr_retenido","monto_propina_legal","forma_pago","anulada","cuenta_contable"],
    "dgii_607": ["id","empresa_id","periodo","rnc_cliente","tipo_identificacion","ncf","ncf_modificado",
                 "fecha_comprobante","monto_facturado","itbis_facturado","monto_propina_legal",
                 "efectivo","cheque_transferencia","tarjeta_credito","credito","bonos_certificados",
                 "permuta","otras_formas","anulada","monto_exento","retencion_isr","retencion_itbis"],
    "dgii_it1": ["id","empresa_id","periodo","ventas_gravadas","ventas_exentas","itbis_generado",
                 "compras_gravadas","itbis_credito","itbis_retenido_terceros","saldo_anterior","itbis_a_pagar"],
    "dgii_ir17": ["id","empresa_id","periodo","alquileres","honorarios","servicios_tecnicos",
                  "otros_pagos","dividendos","itbis_retenido_terceros","retribuciones_complementarias",
                  "total_is_retenido","total_a_pagar"],
    "clasificacion_fiscal": ["id","tipo_ncf","descripcion","tipo_operacion","cuenta_contable",
                              "categoria_fiscal","deducible","aplica_itbis"],
    "activos": ["id","empresa_id","descripcion","categoria","fecha_compra","valor_compra",
                "vida_util","tasa_depreciacion","depreciacion_acumulada","valor_libro"],
    "inventarios": ["id","empresa_id","producto_codigo","descripcion","cantidad","costo_unitario",
                    "valor_total","fecha_registro","tipo_inventario"],
    "prestamos": ["id","empresa_id","entidad_financiera","numero_prestamo","fecha_inicio",
                  "monto_original","saldo_actual","tasa_interes","cuota_mensual","intereses_pagados"],
    "estados_financieros": ["id","empresa_id","periodo","ventas_totales","ventas_exentas","costo_ventas",
                            "gastos_operativos","gastos_personal","utilidad_bruta","utilidad_neta",
                            "renta_imponible","isr_calcular","anticipos","retenciones","isr_pagar"],
    "validaciones_fiscales": ["id","empresa_id","periodo","tipo_validacion","valor_sistema",
                              "valor_dgii","diferencia","estado","recomendacion_socio","asiento_propuesto"],
    "tss_nomina": ["id","empresa_id","periodo","empleados","salario_cotizable","aporte_empresa"],
    "ir18_retenciones": ["id","empresa_id","empleado","cedula","salario","retencion_isr"],
    "socios": ["id","empresa_id","identificador","tipo_identificador","nombre_razon_social",
               "nacionalidad","residencia_fiscal","domicilio","telefono",
               "porcentaje_participacion","es_persona_fisica","es_beneficiario_final",
               "entidad_madre_id","cargo","rnc_bloqueado"],
    "planificacion_scenarios": ["id","empresa_id","nombre_escenario","periodo",
                                "ventas_proyectadas","gastos_proyectados","isr_estimado_anual",
                                "anticipo_sugerido","factor_crecimiento"],
}

# Cargar JSON
src = "C:/GEMINI/AiContaFiscalRD/data/migracion_backup.json"
with open(src, "r", encoding="utf-8") as f:
    export = json.load(f)

# Conectar
conn = psycopg2.connect(**CONN_STR)
conn.autocommit = False
cur = conn.cursor()

# Desactivar triggers (evita conflictos FK)
cur.execute("SET session_replication_role = 'replica';")

TABLAS = [
    "empresas", "padron_dgii", "dgii_606", "dgii_607", "dgii_it1", "dgii_ir17",
    "clasificacion_fiscal", "activos", "inventarios", "prestamos",
    "estados_financieros", "validaciones_fiscales", "tss_nomina",
    "ir18_retenciones", "socios", "planificacion_scenarios"
]

total = 0
errores = []

for tabla in TABLAS:
    records = export.get(tabla, [])
    if not records:
        continue

    cols = MODELO_COLS.get(tabla, [])
    if not cols:
        continue

    # Limpiar datos previos
    try:
        cur.execute(f'DELETE FROM "{tabla}"')
    except Exception as e:
        errores.append(f"{tabla}: DELETE - {e}")
        continue

    batch = []
    placeholders = ",".join(["%s"] * len(cols))
    col_names = ",".join(f'"{c}"' for c in cols)

    for r in records:
        row = tuple(r.get(c) for c in cols)
        batch.append(row)
        if len(batch) >= 500:
            try:
                execute_values(cur, f'INSERT INTO "{tabla}" ({col_names}) VALUES %s', batch)
                conn.commit()
                total += len(batch)
                batch = []
            except Exception as e:
                conn.rollback()
                errores.append(f"{tabla}: batch - {e}")
                batch = []

    if batch:
        try:
            execute_values(cur, f'INSERT INTO "{tabla}" ({col_names}) VALUES %s', batch)
            conn.commit()
            total += len(batch)
        except Exception as e:
            conn.rollback()
            errores.append(f"{tabla}: final - {e}")

    print(f"  [PG] {tabla}: {len(records)} importados")

# Reactivar triggers
cur.execute("SET session_replication_role = 'origin';")
conn.commit()
cur.close()
conn.close()

print(f"\n[OK] Total importados: {total}")
if errores:
    print(f"[!] Errores: {len(errores)}")
    for e in errores[:5]:
        print(f"     {e}")
