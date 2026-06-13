"""
motor_inventario.py — Módulo de Control de Inventarios y Costo de Ventas (Anexo B - IR-2)
====================================================================================
Calcula el Costo de Ventas (COGS) integrando las compras reportadas en el 606 
con los inventarios iniciales y finales registrados en la base de datos.
"""
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from database import Inventario, Dgii606

class MotorInventario:
    """
    Motor de Control de Inventarios y Costo de Ventas (Anexo B - IR-2)
    ====================================================================
    Calcula el Costo de Ventas (COGS) integrando las compras reportadas en el 606 
    con los inventarios iniciales y finales registrados en la base de datos.
    """
    def __init__(self, db: Session, empresa_id: int, anio: int):
        self.db = db
        self.empresa_id = empresa_id
        self.anio = anio

    def calcular_costo_ventas(self, compras_606_externas=None):
        """
        Calcula el Costo de Ventas consolidado para el cierre fiscal.
        Fórmula: Inventario Inicial + Compras del Año - Inventario Final.
        """
        print(f"  [Inventario] Calculando Costo de Ventas Fiscal {self.anio}...")
        
        # 1. Recuperar Inventario Inicial
        inv_inicial = self.db.query(func.sum(Inventario.valor_total)).filter(
            and_(
                Inventario.empresa_id == self.empresa_id,
                Inventario.tipo_inventario == 'inicial',
                func.extract('year', Inventario.fecha_registro) == self.anio
            )
        ).scalar() or 0.0
        
        # 2. Recuperar Compras del Año (Desde 606 - Tipo 2: Costos y Gastos de Mercancía)
        if compras_606_externas is not None:
             compras_606 = compras_606_externas
        else:
            compras_606 = self.db.query(func.sum(Dgii606.monto_facturado)).filter(
                and_(
                    Dgii606.empresa_id == self.empresa_id,
                    Dgii606.periodo.like(f"{self.anio}%"),
                    Dgii606.tipo_bien_servicio == 2, # Costos / Mercancía
                    Dgii606.anulada == False
                )
            ).scalar() or 0.0
        
        # 3. Recuperar Inventario Final
        inv_final = self.db.query(func.sum(Inventario.valor_total)).filter(
            and_(
                Inventario.empresa_id == self.empresa_id,
                Inventario.tipo_inventario == 'final',
                func.extract('year', Inventario.fecha_registro) == self.anio
            )
        ).scalar() or 0.0
        
        # --- CÁLCULO FINAL ---
        inicial = Decimal(str(inv_inicial))
        compras = Decimal(str(compras_606))
        final = Decimal(str(inv_final))
        
        costo_ventas = inicial + compras - final
        
        # ALERTA FISCAL: Si el inventario final es 0, el costo es muy alto (Margen bajo)
        if final == 0:
            print("    [!] ADVERTENCIA: Inventario Final es 0. Riesgo de notificación DGII por margen bajo.")
            
        print(f"    (+) Inventario Inicial: RD$ {inicial:>15,.2f}")
        print(f"    (+) Compras del Año:    RD$ {compras:>15,.2f}")
        print(f"    (-) Inventario Final:   RD$ {final:>15,.2f}")
        print(f"    (=) Costo de Ventas:    RD$ {costo_ventas:>15,.2f}")
        
        return costo_ventas

    def obtener_detalles_anexo_b(self):
        """
        Devuelve los datos listos para el Anexo B del formulario IR-2.
        """
        # Ajuste de filtros para usar el año fiscal correctamente
        return {
            "anio": self.anio,
            "inventario_inicial": float(self.db.query(func.sum(Inventario.valor_total)).filter(
                and_(Inventario.empresa_id==self.empresa_id, Inventario.tipo_inventario=='inicial', func.extract('year', Inventario.fecha_registro) == self.anio)
            ).scalar() or 0),
            "compras_locales": float(self.db.query(func.sum(Dgii606.monto_facturado)).filter(
                and_(Dgii606.empresa_id==self.empresa_id, Dgii606.tipo_bien_servicio==2, Dgii606.periodo.like(f"{self.anio}%"))
            ).scalar() or 0),
            "inventario_final": float(self.db.query(func.sum(Inventario.valor_total)).filter(
                and_(Inventario.empresa_id==self.empresa_id, Inventario.tipo_inventario=='final', func.extract('year', Inventario.fecha_registro) == self.anio)
            ).scalar() or 0)
        }
