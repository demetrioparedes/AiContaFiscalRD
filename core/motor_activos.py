"""
motor_activos.py — Módulo de Activos Fijos y Depreciación Fiscal (Anexo D)
========================================================================
Calcula la depreciación anual según las categorías de la DGII:
- Categoría 1: 5% (Edificaciones y mejoras permanentes)
- Categoría 2: 25% (Automóviles, equipos de cómputo, mobiliario)
- Categoría 3: 15% (Otras máquinas, equipos y bienes muebles)
"""
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import ActivoFijo, EstadoFinanciero

# Tasas Oficiales DGII
TASAS = {
    "CAT1": Decimal("0.05"),
    "CAT2": Decimal("0.25"),
    "CAT3": Decimal("0.15")
}

class MotorActivosFijos:
    """
    Motor de Activos Fijos y Depreciación Fiscal (Anexo D)
    ========================================================
    Calcula la depreciación anual según las categorías de la DGII:
    - Categoría 1: 5% (Edificaciones y mejoras permanentes)
    - Categoría 2: 25% (Automóviles, equipos de cómputo, mobiliario)
    - Categoría 3: 15% (Otras máquinas, equipos y bienes muebles)
    """
    TASAS = {
        "CAT1": Decimal("0.05"),
        "CAT2": Decimal("0.25"),
        "CAT3": Decimal("0.15")
    }

    def __init__(self, db: Session, empresa_id: int, anio: int):
        self.db = db
        self.empresa_id = empresa_id
        self.anio = anio

    def calcular_depreciacion_anual(self):
        """
        Calcula la depreciación total permitida para el año fiscal.
        Actualiza la tabla ActivoFijo y devuelve el total deducible.
        """
        print(f"  [Activos] Calculando Depreciación Fiscal {self.anio}...")
        
        activos = self.db.query(ActivoFijo).filter_by(empresa_id=self.empresa_id).all()
        total_depreciacion_ejercicio = Decimal("0.00")
        
        for activo in activos:
            # 1. Determinar Categoría y Tasa
            cat = str(activo.categoria).upper()
            cat_key = cat.replace(" ", "")
            if cat_key in ("CAT1",) or any(k in cat for k in ("EDIFIC", "MEJORA", "INMUEBLE")):
                tasa = self.TASAS["CAT1"]
                categoria_real = "CAT1"
            elif cat_key in ("CAT2",) or any(k in cat for k in ("VEHIC", "COMPU", "MOBILI", "OFICINA")):
                tasa = self.TASAS["CAT2"]
                categoria_real = "CAT2"
            else:
                tasa = self.TASAS["CAT3"]
                categoria_real = "CAT3"

            # Actualizar tasa en el registro si es 0
            if not activo.tasa_depreciacion:
                activo.tasa_depreciacion = float(tasa * 100)

            # 2. Base Depreciable
            # En RD, la depreciación se calcula sobre el Valor de Libro al inicio
            valor_compra = Decimal(str(activo.valor_compra or 0))
            deprec_acum_ini = Decimal(str(activo.depreciacion_acumulada or 0))
            base_depreciable = valor_compra - deprec_acum_ini
            
            if base_depreciable <= 0:
                activo.valor_libro = 0.0
                continue

            # 3. Cálculo del Gasto del Ejercicio
            gasto_anio = (base_depreciable * tasa).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            
            # 4. Actualización de Valores
            nueva_deprec_acum = deprec_acum_ini + gasto_anio
            nuevo_valor_libro = valor_compra - nueva_deprec_acum
            
            activo.depreciacion_acumulada = float(nueva_deprec_acum)
            activo.valor_libro = float(nuevo_valor_libro)
            
            total_depreciacion_ejercicio += gasto_anio
            print(f"    [+] {activo.descripcion[:20]:<20} | {categoria_real} | Gasto: RD${gasto_anio:>12,.2f}")

        self.db.commit()
        print(f"  [OK] Depreciación Total Permitida: RD$ {total_depreciacion_ejercicio:>15,.2f}")
        return total_depreciacion_ejercicio

    def generar_anexo_d_resumen(self):
        """
        Simula el Anexo D del IR-2 agrupado por categoría.
        """
        resumen = self.db.query(
            ActivoFijo.categoria,
            func.sum(ActivoFijo.valor_compra).label("costo_total"),
            func.sum(ActivoFijo.depreciacion_acumulada).label("deprec_total"),
            func.sum(ActivoFijo.valor_libro).label("valor_libro_total")
        ).filter_by(empresa_id=self.empresa_id).group_by(ActivoFijo.categoria).all()
        
        return resumen
