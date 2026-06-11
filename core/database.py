"""
AiContaFiscalRD — Modelo Completo de Base de Datos (Arquitectura SaaS / Big4)
=============================================================================
Soporte dual SQLite (desarrollo/local) y PostgreSQL (producción/Supabase).
La selección se hace automáticamente vía DATABASE_URL en .env.

SQLAlchemy ORM: mismo código, dos motores.
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

# ─── Configuración de Base de Datos ─────────────────────────────
# Orden de precedencia:
# 1. Variable de entorno DATABASE_URL (producción: PostgreSQL en Supabase)
# 2. SQLite local (desarrollo)
_DATABASE_URL_ENV = os.getenv("DATABASE_URL", "").strip()

if _DATABASE_URL_ENV:
    DATABASE_URL = _DATABASE_URL_ENV
    _ENGINE = "postgresql"
else:
    _DB_PATH = os.path.join(DATA_DIR, 'aicontafiscal_core.db')
    DATABASE_URL = f"sqlite:///{_DB_PATH}"
    _ENGINE = "sqlite"

print(f"[DB] Motor: {_ENGINE.upper()} | {DATABASE_URL[:50]}...")

# ─── Creación del Engine ─────────────────────────────────────────
if _ENGINE == "postgresql":
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        pool_pre_ping=True,          # Verifica conexión antes de usarla
        pool_size=5,                 # Conexiones en pool (PgBouncer compatible)
        max_overflow=10,             # Conexiones extra bajo demanda
        connect_args={
            "sslmode": "require",
            "connect_timeout": 10,
        },
    )
else:
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        connect_args={
            "check_same_thread": False,
            "timeout": 30,
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

    empresa = relationship("Empresa", back_populates="registros_606")
    anulada = Column(Boolean, default=False)
    cuenta_contable = Column(String(50))

Index('idx_606_empresa', Dgii606.empresa_id)
Index('idx_606_periodo', Dgii606.periodo)


# ==========================================
# 3. DGII 607 (Ventas)
# ==========================================
class Dgii607(Base):
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

    empresa = relationship("Empresa", back_populates="registros_607")
    anulada = Column(Boolean, default=False)
    monto_exento = Column(Numeric(18,2), default=0.0)
    retencion_isr = Column(Numeric(18,2), default=0.0)
    retencion_itbis = Column(Numeric(18,2), default=0.0)


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
# 4.1. DGII IR-17
# ==========================================
class DgiiIr17(Base):
    __tablename__ = "dgii_ir17"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"))
    periodo = Column(String(6))
    alquileres = Column(Numeric(18,2), default=0.0)
    honorarios = Column(Numeric(18,2), default=0.0)
    servicios_tecnicos = Column(Numeric(18,2), default=0.0)
    otros_pagos = Column(Numeric(18,2), default=0.0)
    dividendos = Column(Numeric(18,2), default=0.0)
    itbis_retenido_terceros = Column(Numeric(18,2), default=0.0)
    retribuciones_complementarias = Column(Numeric(18,2), default=0.0)
    total_is_retenido = Column(Numeric(18,2), default=0.0)
    total_a_pagar = Column(Numeric(18,2), default=0.0)
    creado = Column(DateTime, default=func.now())

Index('idx_ir17_empresa', DgiiIr17.empresa_id)
Index('idx_ir17_periodo', DgiiIr17.periodo)


# ==========================================
# 5. CLASIFICADOR FISCAL
# ==========================================
class ClasificacionFiscal(Base):
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
    __tablename__ = "inventarios"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"))
    producto_codigo = Column(String(50))
    descripcion = Column(Text)
    cantidad = Column(Numeric(18,2), default=0.0)
    costo_unitario = Column(Numeric(18,2), default=0.0)
    valor_total = Column(Numeric(18,2), default=0.0)
    fecha_registro = Column(Date)
    tipo_inventario = Column(String(20))


# ==========================================
# 8. PRESTAMOS
# ==========================================
class Prestamo(Base):
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
    intereses_pagados = Column(Numeric(18,2), default=0.0)


# ==========================================
# 9. ESTADOS FINANCIEROS
# ==========================================
class EstadoFinanciero(Base):
    __tablename__ = "estados_financieros"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"))
    periodo = Column(String(6))
    ventas_totales = Column(Numeric(18,2), default=0.0)
    ventas_exentas = Column(Numeric(18,2), default=0.0)
    costo_ventas = Column(Numeric(18,2), default=0.0)
    gastos_operativos = Column(Numeric(18,2), default=0.0)
    gastos_personal = Column(Numeric(18,2), default=0.0)
    utilidad_bruta = Column(Numeric(18,2), default=0.0)
    utilidad_neta = Column(Numeric(18,2), default=0.0)
    renta_imponible = Column(Numeric(18,2), default=0.0)
    isr_calcular = Column(Numeric(18,2), default=0.0)
    anticipos = Column(Numeric(18,2), default=0.0)
    retenciones = Column(Numeric(18,2), default=0.0)
    isr_pagar = Column(Numeric(18,2), default=0.0)
    creado = Column(DateTime, default=func.now())
    empresa = relationship("Empresa", back_populates="estados_financieros")


# ==========================================
# 9.1. ESCENARIOS DE PLANIFICACIÓN
# ==========================================
class PlanificacionScenario(Base):
    __tablename__ = "planificacion_scenarios"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"))
    nombre_escenario = Column(String(50))
    periodo = Column(String(6))
    ventas_proyectadas = Column(Numeric(18,2), default=0.0)
    gastos_proyectados = Column(Numeric(18,2), default=0.0)
    isr_estimado_anual = Column(Numeric(18,2), default=0.0)
    anticipo_sugerido = Column(Numeric(18,2), default=0.0)
    factor_crecimiento = Column(Numeric(5,2), default=1.0)
    creado = Column(DateTime, default=func.now())


# ==========================================
# 10. VALIDACIONES FISCALES
# ==========================================
class ValidacionFiscal(Base):
    __tablename__ = "validaciones_fiscales"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"))
    periodo = Column(String(6))
    tipo_validacion = Column(String(50))
    valor_sistema = Column(Numeric(18,2), default=0.0)
    valor_dgii = Column(Numeric(18,2), default=0.0)
    diferencia = Column(Numeric(18,2), default=0.0)
    estado = Column(String(20))
    recomendacion_socio = Column(Text)
    asiento_propuesto = Column(Text)
    creado = Column(DateTime, default=func.now())
    empresa = relationship("Empresa", back_populates="validaciones")


# ==========================================
# TSS / IR-18
# ==========================================
class TssNomina(Base):
    __tablename__ = "tss_nomina"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"))
    periodo = Column(String(6))
    empleados = Column(Integer, default=0)
    salario_cotizable = Column(Numeric(18,2), default=0.0)
    aporte_empresa = Column(Numeric(18,2), default=0.0)


class Ir18Retenciones(Base):
    __tablename__ = "ir18_retenciones"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"))
    empleado = Column(String(200))
    cedula = Column(String(11))
    salario = Column(Numeric(18,2), default=0.0)
    retencion_isr = Column(Numeric(18,2), default=0.0)


# ==========================================
# 11. SOCIOS Y BENEFICIARIOS FINALES
# ==========================================
class Socio(Base):
    __tablename__ = 'socios'
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey('empresas.id'), nullable=False)
    identificador = Column(String(20), nullable=False)
    tipo_identificador = Column(Integer, nullable=False)
    nombre_razon_social = Column(String(255), nullable=False)
    nacionalidad = Column(String(100), default='Dominicana')
    residencia_fiscal = Column(String(100), nullable=False)
    domicilio = Column(Text, nullable=True)
    telefono = Column(String(20), nullable=True)
    empresa = relationship("Empresa", back_populates="socios")
    porcentaje_participacion = Column(Numeric(5,2), nullable=False)
    es_persona_fisica = Column(Boolean, default=True)
    es_beneficiario_final = Column(Boolean, default=False)
    entidad_madre_id = Column(Integer, ForeignKey('socios.id'), nullable=True)
    cargo = Column(String(100), nullable=True)
    rnc_bloqueado = Column(Boolean, default=False)
    fecha_actualizacion = Column(DateTime, default=func.now(), onupdate=func.now())

Index('idx_socios_empresa', Socio.empresa_id)
Index('idx_socios_madre', Socio.entidad_madre_id)


# ==========================================
# FUNCIONES DE INICIALIZACIÓN
# ==========================================
def init_db():
    """
    Inicializa la base de datos:
    - PostgreSQL: create_all, sin PRAGMAs (no aplican)
    - SQLite: create_all + WAL mode para concurrencia local
    """
    db_path = os.path.join(DATA_DIR, 'aicontafiscal_core.db') if _ENGINE == "sqlite" else None
    es_nueva = not os.path.exists(db_path) if db_path else False

    # Crear tablas (safe: solo las que faltan)
    Base.metadata.create_all(bind=engine)

    if _ENGINE == "sqlite":
        with engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA synchronous=NORMAL"))
            conn.execute(text("PRAGMA cache_size=10000"))
        estado = "nueva" if es_nueva else "existente (esquema actualizado)"
        print(f"=== AiContaFiscalRD BD [SQLite] [{estado}] | {len(Base.metadata.tables)} tablas | WAL mode ===")
    else:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"=== AiContaFiscalRD BD [PostgreSQL] | {len(Base.metadata.tables)} tablas | Pool activo ===")


def get_db():
    """Dependency para FastAPI — sesión por request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
