"""
AiContaFiscalRD - Modelo Completo de Base de Datos (Arquitectura SaaS / Big4)
=============================================================================
Modelo de producción para PostgreSQL / SQLite.
Diseñado para alto volumen, cruces fiscales automáticos y generación de IR-2.
"""
from sqlalchemy import create_engine, text, Column, Integer, String, Boolean, ForeignKey, Text, Date, Numeric, DateTime, Index
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.sql import func
import datetime
import os

# Resolución dinámica de la raíz del proyecto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

DATABASE_URL = f"sqlite:///{os.path.join(DATA_DIR, 'aicontafiscal_core.db')}"

# Blindaje Anti-Lock SQLite (3 capas de protección):
# 1. check_same_thread=False → permite uso en múltiples hilos (FastAPI async)
# 2. timeout=30 → espera hasta 30s si otra conexión tiene el lock (en vez de fallar)
# 3. WAL mode → (en init_db) permite que lecturas no bloqueen escrituras simultáneas
engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={
        "check_same_thread": False,
        "timeout": 30
    },
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ==========================================
# 1. EMPRESAS (SaaS Multi-tenant)
# ==========================================
class PadronDGII(Base):
    __tablename__ = "padron_dgii"
    
    id = Column(Integer, primary_key=True, index=True)
    rnc = Column(String(20), unique=True, index=True)
    razon_social = Column(String(200), index=True)
    actividad_economica = Column(String(300))
    fecha_inicio = Column(String(20))
    estado = Column(String(50))
    regimen_pago = Column(String(100))

class Empresa(Base):
    """Permite SaaS o múltiples clientes."""
    __tablename__ = "empresas"
    id = Column(Integer, primary_key=True)
    rnc = Column(String(11), unique=True, nullable=False)
    nombre_empresa = Column(Text, nullable=False)
    direccion = Column(Text)
    telefono = Column(String(20))
    email = Column(Text)
    fecha_creacion = Column(DateTime, default=func.now())

    # Relaciones (Lógica Industrial)
    registros_606 = relationship("Dgii606", back_populates="empresa", cascade="all, delete-orphan")
    registros_607 = relationship("Dgii607", back_populates="empresa", cascade="all, delete-orphan")
    socios = relationship("Socio", back_populates="empresa", cascade="all, delete-orphan")
    estados_financieros = relationship("EstadoFinanciero", back_populates="empresa", cascade="all, delete-orphan")
    validaciones = relationship("ValidacionFiscal", back_populates="empresa", cascade="all, delete-orphan")

# ==========================================
# 2. DGII 606 (Compras)
# ==========================================
class Dgii606(Base):
    """Formato real del Reporte 606 de DGII"""
    __tablename__ = "dgii_606"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"))
    periodo = Column(String(6))
    rnc_proveedor = Column(String(11))
    tipo_identificacion = Column(Integer)
    ncf = Column(String(19))
    ncf_modificado = Column(String(19))
    fecha_comprobante = Column(Date)
    fecha_pago = Column(Date)
    tipo_bien_servicio = Column(Integer)
    monto_facturado = Column(Numeric(18,2), default=0.0)
    itbis_facturado = Column(Numeric(18,2), default=0.0)
    itbis_retenido = Column(Numeric(18,2), default=0.0)
    isr_retenido = Column(Numeric(18,2), default=0.0)
    monto_propina_legal = Column(Numeric(18,2), default=0.0)
    forma_pago = Column(Integer)
    creado = Column(DateTime, default=func.now())
    
    # Relación con Empresa
    empresa = relationship("Empresa", back_populates="registros_606")
    
    # Extensiones internas para el Motor:
    anulada = Column(Boolean, default=False)
    cuenta_contable = Column(String(50)) # Llenado por el Clasificador

Index('idx_606_empresa', Dgii606.empresa_id)
Index('idx_606_periodo', Dgii606.periodo)

# ==========================================
# 3. DGII 607 (Ventas)
# ==========================================
class Dgii607(Base):
    """Formato real del Reporte 607 de DGII"""
    __tablename__ = "dgii_607"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"))
    periodo = Column(String(6))
    rnc_cliente = Column(String(11))
    tipo_identificacion = Column(Integer)
    ncf = Column(String(19))
    ncf_modificado = Column(String(19))
    fecha_comprobante = Column(Date)
    monto_facturado = Column(Numeric(18,2), default=0.0)
    itbis_facturado = Column(Numeric(18,2), default=0.0)
    monto_propina_legal = Column(Numeric(18,2), default=0.0)
    efectivo = Column(Numeric(18,2), default=0.0)
    cheque_transferencia = Column(Numeric(18,2), default=0.0)
    tarjeta_credito = Column(Numeric(18,2), default=0.0)
    credito = Column(Numeric(18,2), default=0.0)
    bonos_certificados = Column(Numeric(18,2), default=0.0)
    permuta = Column(Numeric(18,2), default=0.0)
    otras_formas = Column(Numeric(18,2), default=0.0)
    creado = Column(DateTime, default=func.now())
    
    # Relación con Empresa
    empresa = relationship("Empresa", back_populates="registros_607")
    
    # Extensiones internas:
    anulada = Column(Boolean, default=False)
    monto_exento = Column(Numeric(18,2), default=0.0)
    retencion_isr = Column(Numeric(18,2), default=0.0)

Index('idx_607_empresa', Dgii607.empresa_id)
Index('idx_607_periodo', Dgii607.periodo)

# ==========================================
# 4. DGII IT-1 (Declaración ITBIS)
# ==========================================
class DgiiIt1(Base):
    __tablename__ = "dgii_it1"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"))
    periodo = Column(String(6))
    ventas_gravadas = Column(Numeric(18,2), default=0.0)
    ventas_exentas = Column(Numeric(18,2), default=0.0)
    itbis_generado = Column(Numeric(18,2), default=0.0)
    compras_gravadas = Column(Numeric(18,2), default=0.0)
    itbis_credito = Column(Numeric(18,2), default=0.0)
    itbis_retenido_terceros = Column(Numeric(18,2), default=0.0)
    saldo_anterior = Column(Numeric(18,2), default=0.0)
    itbis_a_pagar = Column(Numeric(18,2), default=0.0)
    creado = Column(DateTime, default=func.now())

Index('idx_it1_empresa', DgiiIt1.empresa_id)

# ==========================================
# 4.1. DGII IR-17 (Retenciones y Retribuciones)
# ==========================================
class DgiiIr17(Base):
    """Declaración mensual de retenciones a terceros y retribuciones complementarias."""
    __tablename__ = "dgii_ir17"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"))
    periodo = Column(String(6)) # YYYYMM
    
    # ISR Retenido
    alquileres = Column(Numeric(18,2), default=0.0)      # 10%
    honorarios = Column(Numeric(18,2), default=0.0)      # 10%
    servicios_tecnicos = Column(Numeric(18,2), default=0.0) # 2%
    otros_pagos = Column(Numeric(18,2), default=0.0)     # 1% u otros
    dividendos = Column(Numeric(18,2), default=0.0)      # 10%
    
    # ITBIS Retenido a Terceros (Suma de retenciones en 606)
    itbis_retenido_terceros = Column(Numeric(18,2), default=0.0)
    
    # Retribuciones Complementarias
    retribuciones_complementarias = Column(Numeric(18,2), default=0.0)
    
    # Totales
    total_is_retenido = Column(Numeric(18,2), default=0.0)
    total_a_pagar = Column(Numeric(18,2), default=0.0)
    
    creado = Column(DateTime, default=func.now())

Index('idx_ir17_empresa', DgiiIr17.empresa_id)
Index('idx_ir17_periodo', DgiiIr17.periodo)

# ==========================================
# 5. CLASIFICADOR FISCAL (El Cerebro)
# ==========================================
class ClasificacionFiscal(Base):
    """Convierte los comprobantes en cuentas contables automáticas."""
    __tablename__ = "clasificacion_fiscal"
    id = Column(Integer, primary_key=True)
    tipo_ncf = Column(String(3))
    descripcion = Column(Text)
    tipo_operacion = Column(String(20))
    cuenta_contable = Column(String(50))
    categoria_fiscal = Column(String(50))
    deducible = Column(Boolean, default=True)
    aplica_itbis = Column(Boolean, default=True)

# ==========================================
# 6. ACTIVOS FIJOS
# ==========================================
class ActivoFijo(Base):
    """Para generar automáticamente depreciación fiscal IR-2 (Anexo D)"""
    __tablename__ = "activos"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"))
    descripcion = Column(Text)
    categoria = Column(String(50))
    fecha_compra = Column(Date)
    valor_compra = Column(Numeric(18,2), default=0.0)
    vida_util = Column(Integer)
    tasa_depreciacion = Column(Numeric(5,2), default=0.0)
    depreciacion_acumulada = Column(Numeric(18,2), default=0.0)
    valor_libro = Column(Numeric(18,2), default=0.0)
    creado = Column(DateTime, default=func.now())

# ==========================================
# 7. INVENTARIO
# ==========================================
class Inventario(Base):
    """Motor necesario para Costo de ventas IR-2"""
    __tablename__ = "inventarios"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"))
    producto_codigo = Column(String(50))
    descripcion = Column(Text)
    cantidad = Column(Numeric(18,2), default=0.0)
    costo_unitario = Column(Numeric(18,2), default=0.0)
    valor_total = Column(Numeric(18,2), default=0.0)
    fecha_registro = Column(Date)
    tipo_inventario = Column(String(20)) # 'inicial' o 'final'

# ==========================================
# 8. PRESTAMOS
# ==========================================
class Prestamo(Base):
    """Permite generar intereses deducibles y flujo financiero."""
    __tablename__ = "prestamos"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"))
    entidad_financiera = Column(Text)
    numero_prestamo = Column(String(50))
    fecha_inicio = Column(Date)
    monto_original = Column(Numeric(18,2), default=0.0)
    saldo_actual = Column(Numeric(18,2), default=0.0)
    tasa_interes = Column(Numeric(6,3), default=0.0)
    cuota_mensual = Column(Numeric(18,2), default=0.0)
    creado = Column(DateTime, default=func.now())
    # Extendemos para el motor:
    intereses_pagados = Column(Numeric(18,2), default=0.0)

# ==========================================
# 9. ESTADOS FINANCIEROS (Generados)
# ==========================================
class EstadoFinanciero(Base):
    __tablename__ = "estados_financieros"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"))
    periodo = Column(String(6)) # Anual, ej "2025"
    ventas_totales = Column(Numeric(18,2), default=0.0)
    costo_ventas = Column(Numeric(18,2), default=0.0)
    gastos_operativos = Column(Numeric(18,2), default=0.0)
    utilidad_bruta = Column(Numeric(18,2), default=0.0)
    utilidad_neta = Column(Numeric(18,2), default=0.0)
    creado = Column(DateTime, default=func.now())
    # Componentes adicionales
    ventas_exentas = Column(Numeric(18,2), default=0.0)
    gastos_personal = Column(Numeric(18,2), default=0.0)
    isr_calcular = Column(Numeric(18,2), default=0.0)
    renta_imponible = Column(Numeric(18,2), default=0.0)
    anticipos = Column(Numeric(18,2), default=0.0)
    retenciones = Column(Numeric(18,2), default=0.0)
    isr_pagar = Column(Numeric(18,2), default=0.0)

    # Relación
    empresa = relationship("Empresa", back_populates="estados_financieros")

# ==========================================
# 10. VALIDACIONES FISCALES
# ==========================================
class ValidacionFiscal(Base):
    """Motor de control automático."""
    __tablename__ = "validaciones_fiscales"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"))
    periodo = Column(String(6))
    tipo_validacion = Column(String(50))
    valor_sistema = Column(Numeric(18,2), default=0.0)
    valor_dgii = Column(Numeric(18,2), default=0.0)
    diferencia = Column(Numeric(18,2), default=0.0)
    estado = Column(String(20)) # "OK", "CRITICO", "ADVERTENCIA"
    recomendacion_socio = Column(Text) # El consejo del socio experto
    asiento_propuesto = Column(Text) # Sugerencia de ajuste contable
    creado = Column(DateTime, default=func.now())

    # Relación
    empresa = relationship("Empresa", back_populates="validaciones")

# ==========================================
# REPOSITORIOS ADICIONALES NECESARIOS PARA EL PIPELINE
# ==========================================
class TssNomina(Base):
    """TSS: Nómina y aportes laborales. Clave para Validación."""
    __tablename__ = "tss_nomina"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"))
    periodo = Column(String(6))
    empleados = Column(Integer, default=0)
    salario_cotizable = Column(Numeric(18,2), default=0.0)
    aporte_empresa = Column(Numeric(18,2), default=0.0)

class Ir18Retenciones(Base):
    """IR-18: Retenciones a asalariados."""
    __tablename__ = "ir18_retenciones"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"))
    empleado = Column(String(200))
    cedula = Column(String(11))
    salario = Column(Numeric(18,2), default=0.0)
    retencion_isr = Column(Numeric(18,2), default=0.0)


# ==========================================
# 11. SOCIOS Y BENEFICIARIOS FINALES (H-1/H-2)
# ==========================================
class Socio(Base):
    """Módulo para cumplimiento de Anexos H-1 y H-2 (Beneficiario Final)"""
    __tablename__ = 'socios'

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey('empresas.id'), nullable=False)
    
    identificador = Column(String(20), nullable=False)  # Cédula, RNC, Pasaporte, ID Extranjero
    tipo_identificador = Column(Integer, nullable=False)  # 1:Cédula, 2:RNC, 3:Pasaporte, 4:ID Extranjero
    nombre_razon_social = Column(String(255), nullable=False)
    
    nacionalidad = Column(String(100), default='Dominicana')
    residencia_fiscal = Column(String(100), nullable=False)  # País
    domicilio = Column(Text, nullable=True)  
    telefono = Column(String(20), nullable=True)
    
    # Relación
    empresa = relationship("Empresa", back_populates="socios")
    
    porcentaje_participacion = Column(Numeric(5,2), nullable=False)  # Ej: 50.00
    es_persona_fisica = Column(Boolean, default=True)
    es_beneficiario_final = Column(Boolean, default=False)  
    
    entidad_madre_id = Column(Integer, ForeignKey('socios.id'), nullable=True)  
    cargo = Column(String(100), nullable=True)  # Presidente, Gerente, etc.
    
    rnc_bloqueado = Column(Boolean, default=False)
    
    fecha_actualizacion = Column(DateTime, default=func.now(), onupdate=func.now())

Index('idx_socios_empresa', Socio.empresa_id)
Index('idx_socios_madre', Socio.entidad_madre_id)


# ==========================================
# FUNCIONES DE DB
# ==========================================
def init_db():
    """
    Inicializa la base de datos de forma segura:
    - Activa WAL mode (lecturas concurrentes sin lock)
    - Solo crea las tablas que faltan (no destruye datos existentes)
    - Si la BD está en uso por otro proceso, espera hasta 30s antes de fallar
    """
    db_path = os.path.join(DATA_DIR, 'aicontafiscal_core.db')
    es_nueva = not os.path.exists(db_path)

    # Crear todas las tablas que no existan (safe: no toca las que ya están)
    Base.metadata.create_all(bind=engine)

    # Activar WAL mode — permite lecturas mientras hay escrituras simultáneas
    # Esto es diferente al modo por defecto (DELETE) que bloquea todo
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.execute(text("PRAGMA synchronous=NORMAL"))  # Velocidad + seguridad
        conn.execute(text("PRAGMA cache_size=10000"))    # 10MB cache en RAM

    estado = "nueva" if es_nueva else "existente (esquema actualizado)"
    print(f"=== AiContaFiscalRD BD [{estado}] | {len(Base.metadata.tables)} tablas | WAL mode activo ===")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
