from database import SessionLocal, ClasificacionFiscal

def seed_clasificacion():
    db = SessionLocal()
    
    # 1. Limpiamos por si corremos varias veces
    db.query(ClasificacionFiscal).delete()
    
    # 2. Las reglas propuestas por el usuario
    reglas = [
        {"tipo_ncf": "B01", "categoria": "gasto", "cuenta_contable": "gasto_operativo", "deducible": True},
        {"tipo_ncf": "B04", "categoria": "activo", "cuenta_contable": "activo_fijo", "deducible": True},
        {"tipo_ncf": "B11", "categoria": "inventario", "cuenta_contable": "inventario", "deducible": True},
        {"tipo_ncf": "B13", "categoria": "servicio", "cuenta_contable": "gasto_servicio", "deducible": True},
    ]
    
    # 3. Insertar a Base de Datos
    for regla in reglas:
        nueva_regla = ClasificacionFiscal(
            tipo_ncf=regla["tipo_ncf"],
            categoria=regla["categoria"],
            cuenta_contable=regla["cuenta_contable"],
            deducible=regla["deducible"]
        )
        db.add(nueva_regla)
        print(f"[+] Regla Agregada: {regla['tipo_ncf']} -> {regla['cuenta_contable']}")
        
    db.commit()
    db.close()
    print("\n[OK] Tabla de Clasificación Fiscal poblada correctamente.")

if __name__ == "__main__":
    seed_clasificacion()
