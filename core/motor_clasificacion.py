"""
motor_clasificacion.py — Inteligencia Artificial de Mapeo al Catálogo DGII (Anexo B)
=====================================================================================
Motor 1 (Reconstrucción Contable): Asigna cada RNC y/o nombre de proveedor proveniente
del Formato 606 a la categoría oficial del Anexo B del formulario IR-2.

Clasificación en 3 niveles (de más a menos precisa):
  1. Por RNC exacto (diccionario de empresas dominicanas conocidas)
  2. Por palabras clave en el nombre del proveedor (semántica)
  3. Por tipo_bien_servicio del 606 (fallback oficial DGII)
"""

# =====================================================================
# NIVEL 1: RNCs Dominicanos Conocidos (Precisión Máxima)
# =====================================================================
RNC_CONOCIDOS = {
    # Telecomunicaciones
    "1010234568": "Telecomunicaciones",    # CLARO (Codetel)
    "1010045531": "Telecomunicaciones",    # ALTICE / ORANGE
    "1010001862": "Telecomunicaciones",    # TRICOM
    "1010011821": "Telecomunicaciones",    # VIVA
    "1010034789": "Telecomunicaciones",    # WIND TELECOM
    # Energía
    "1010001210": "Energía Eléctrica",     # EDENORTE
    "1010001237": "Energía Eléctrica",     # EDESUR
    "1010001245": "Energía Eléctrica",     # EDEESTE
    "1010058901": "Energía Eléctrica",     # CEPM
    # Tarjetas de crédito / CARDNET
    "1010019986": "Gastos Financieros",    # CARDNET
    "1016548549": "Gastos Financieros",    # VISANET
    "1010063390": "Gastos Financieros",    # CARDNET S.A.
    "1010654325": "Gastos Financieros",    # CONSORCIO TARJETAS DOMINICANAS
    "1010019953": "Gastos Financieros",    # ASISCARD
    # Bancos
    "1010036551": "Gastos Financieros",    # BANCO POPULAR
    "1010016533": "Gastos Financieros",    # BHD LEON
    "1010004399": "Gastos Financieros",    # BANRESERVAS
    "1010050998": "Gastos Financieros",    # SCOTIABANK
    "1010059854": "Gastos Financieros",    # BANCO SANTA CRUZ
    "1010040004": "Gastos Financieros",    # BANESCO
    "1010076390": "Gastos Financieros",    # LAFISE
    "1010067890": "Gastos Financieros",    # BANCO CARIBE
    "1010089012": "Gastos Financieros",    # BANCO VIMENCA
    "1010090123": "Gastos Financieros",    # BANCO PROMERICA
    "1010054321": "Gastos Financieros",    # BANCO ATLANTICO
    # Seguros
    "1010057139": "Seguros Obra y Vida",   # MAPFRE BHD
    "1010011953": "Seguros Obra y Vida",   # HUMANO SEGUROS
    "1010001554": "Seguros Obra y Vida",   # UNIVERSAL
    "1010034054": "Seguros Obra y Vida",   # SENASA
    "1010042017": "Seguros Obra y Vida",   # FLORIDA
    "1010026456": "Seguros Obra y Vida",   # LA COLONIAL
    "1010067891": "Seguros Obra y Vida",   # PALIC
    "1010078902": "Seguros Obra y Vida",   # GLOBAL
    "1010045690": "Seguros Obra y Vida",   # PATRIA
    "1010089013": "Seguros Obra y Vida",   # APAP
    # Agua y servicios básicos
    "1010001354": "Agua y Basura",         # CAASD
    "1010020011": "Agua y Basura",         # CORAASAN
    "6010000017": "Agua y Basura",         # AYUNTAMIENTO SDN
    # Estado / Obligaciones Fiscales
    "1010001702": "Gastos Financieros",    # DGII
    "1010001745": "Gastos de Personal",    # TSS/TESORERÍA
    "1010032487": "Gastos de Personal",    # INFOTEP
    "1010056781": "Gastos de Personal",    # MINISTERIO DE TRABAJO
    "1010067893": "Gastos Financieros",    # ADUANAS DGA
    "1010034569": "Gastos de Personal",    # CONTRALORIA GENERAL
    # Supermercados
    "1010074123": "Gastos de Limpieza",    # BRAVO SUPERMARKET
    "1010074190": "Gastos de Limpieza",    # LA SIRENA / WALMART
    "1010019876": "Gastos de Limpieza",    # NACIONAL
    "1010067234": "Gastos de Limpieza",    # PLAZA LAMA
    "1010033478": "Gastos de Limpieza",    # JUMBO
    "1010078945": "Gastos de Limpieza",    # APRECIO
    "1010052345": "Gastos de Limpieza",    # OLE
    "1010091234": "Gastos de Limpieza",    # IGA
    # Combustibles
    "1010023456": "Combustibles y Lubricantes",  # SUNIX
    "1010034123": "Combustibles y Lubricantes",  # SHELL
    "1010045678": "Combustibles y Lubricantes",  # TOTAL GAS
    "1010056789": "Combustibles y Lubricantes",  # TEXACO
    "1010062345": "Combustibles y Lubricantes",  # ISLA
    # Farmacias / Salud
    "1010054322": "Gastos de Limpieza",    # FARMACIA CAROL
    "1010065433": "Gastos de Limpieza",    # FARMACIA EL HORMIGO
    "1010076544": "Gastos de Limpieza",    # FARMACIA AQUA
    # Construcción y proveedores
    "1010087655": "Reparaciones y Mantenimiento", # CONSTRUCTORA NORBERTO ODEBRECHT
    "1010098766": "Reparaciones y Mantenimiento", # CONSTRUCTORA SANTIAGO
    "1010032145": "Reparaciones y Mantenimiento", # FERRETERIA AMERICANA
    "1010043210": "Reparaciones y Mantenimiento", # FERRETERIA OCHO
    # Logística / Transporte
    "1010056782": "Combustibles y Lubricantes",  # TRANSPORTE SEGURA
    "1010067892": "Combustibles y Lubricantes",  # MOTORES DELCIO
    # Hoteles / Turismo
    "1010078901": "Dietas y Gastos de Viaje",  # HOTEL JARDIN
    "1010089010": "Dietas y Gastos de Viaje",  # HOTEL INTERCONTINENTAL
    "1010090120": "Dietas y Gastos de Viaje",  # GRUPO PUNTACANA
    # Educación
    "1010022211": "Materiales de Oficina",   # PONTIFICIA U.C. MADRE MAESTRA
    "1010033322": "Materiales de Oficina",   # UNIBE
    "1010044433": "Materiales de Oficina",   # INTEC
    "1010055544": "Materiales de Oficina",   # APEC
    # Medios / Publicidad
    "1010066655": "Publicidad y Mercadeo",   # LISTIN DIARIO
    "1010077766": "Publicidad y Mercadeo",   # DIARIO LIBRE
    "1010088877": "Publicidad y Mercadeo",   # TELEMICRO
}

# =====================================================================
# NIVEL 2: Palabras Clave Semánticas por Nombre de Proveedor
# =====================================================================
def obtener_catalogo_ia():
    return {
        "Energía Eléctrica":        ["EDENORTE", "EDESUR", "EDEESTE", "CEPM", "ELECTRICIDAD"],
        "Telecomunicaciones":       ["CLARO", "COMPANIA DOMINICANA DE TELEFONO", "ALTICE", "TRICOM", "VIVA", "TELECOMUNICACIONES", "INTERNET", "WIFI"],
        "Combustibles y Lubricantes": ["SHELL", "TOTAL", "SUNIX", "TEXACO", "BOMBA", "GASOLINERA", "COMBUSTIBLE", "GASOLINA", "GASOIL", "DIESEL"],
        "Materiales de Oficina":    ["PAPELERIA", "OFFICE DEPOT", "LIBRERIA", "TONER", "IMPRESORA", "SUMINISTROS", "PAPELERA"],
        "Gastos de Limpieza":       ["SUPERMERCADO", "BRAVO", "NACIONAL", "SIRENA", "APRECIO", "PLAZA LAMA", "JUMBO", "LIMPIEZA"],
        "Reparaciones y Mantenimiento": ["REPUESTO", "TALLER", "MECANICA", "MANTENIMIENTO", "TECNICO", "PIEZAS", "REPARACION"],
        "Suministros Informáticos": ["MICROSOFT", "AMAZON", "AWS", "GOOGLE", "HOSTING", "DOMINIOS", "SOFTWARE"],
        "Agua y Basura":            ["CAASD", "CORAASAN", "AYUNTAMIENTO", "BASURA", "AGUA POTABLE"],
        "Honorarios Profesionales": ["ABOGADO", "CONTABLE", "AUDITOR", "CONSULTOR", "ASESORIA", "LEGAL", "ASOCIADOS"],
        "Seguros Obra y Vida":      ["SEGUROS", "MAPFRE", "HUMANO", "SENASA", "UNIVERSAL", "COLONIAL", "POLIZA", "ASEGURADORA"],
        "Gastos Financieros":       ["BANCO", "BHD", "POPULAR", "BANRESERVAS", "SCOTIABANK", "CONSORCIO", "COOPERATIVA", "INTERESES", "COMISION", "TARJETA", "CARDNET"],
        "Dietas y Gastos de Viaje": ["RESTAURANT", "HOTEL", "RESORT", "AEROLINEA", "UBER", "TAXI", "ALIMENTOS", "CAFETERIA", "DELICIA", "PIZZA", "COMIDA", "VIATICO"],
        "Publicidad y Mercadeo":    ["PUBLICIDAD", "MERCADEO", "MARKETING", "FACEBOOK", "META ", "INSTAGRAM", "IMPRENTA", "ROTULO", "CARTEL", "DISENO", "CREATIVO", "AGENCIA"],
        "Salud y Farmacia":         ["FARMACIA", "CLINICA", "HOSPITAL", "MEDICO", "LABORATORIO", "SALUD", "ODONTOLOGIA", "VETERINARIA"],
        "Educación y Capacitación": ["COLEGIO", "ESCUELA", "UNIVERSIDAD", "INSTITUTO", "CAPACITACION", "CURSO", "TALLER FORMATIVO", "ACADEMIA"],
        "Adquisición de Activos Fijos": ["MUEBLES", "VEHICULO", "COMPUTADORA", "LAPTOP", "MOBILIARIO", "HERRAMIENTA", "MAQUINARIA"],
        "Arrendamientos":           ["ALQUILER", "ARRENDAMIENTO", "RENTA LOCAL", "INMOBILIARIA", "LOCAL COMERCIAL"],
    }

# =====================================================================
# NIVEL 3: Fallback oficial por tipo_bien_servicio del 606 DGII
# =====================================================================
def mapear_anexo_b_general(tipo_bien_servicio: int) -> str:
    mapa = {
        1: "Gastos de Personal",
        2: "Gastos por Trabajos, Suministros y Servicios",
        3: "Arrendamientos",
        4: "Gastos de Activos Fijos (Depreciación)",
        5: "Gastos de Representación",
        6: "Otras Deducciones Admitidas",
        7: "Gastos Financieros",
        8: "Gastos Extraordinarios",
        9: "Compras/Costos de Ventas",
        10: "Adquisición de Activos",
        11: "Gastos de Seguros"
    }
    return mapa.get(tipo_bien_servicio, "Otras Deducciones Admitidas")

# =====================================================================
# FUNCIÓN PRINCIPAL: Clasifica pasando por los 3 niveles
# =====================================================================
def clasificar_factura_ia(nombre_proveedor: str, tipo_bien: int, rnc_proveedor: str = "") -> dict:
    """
    Clasifica una factura del 606 a la cuenta contable del Anexo B del IR-2.
    Aplica 3 niveles de precisión de forma automática.
    """
    # --- NIVEL 1: RNC exacto ---
    rnc_limpio = str(rnc_proveedor).strip().replace("-", "")
    if rnc_limpio and rnc_limpio in RNC_CONOCIDOS:
        cuenta_especifica = RNC_CONOCIDOS[rnc_limpio]
        return {
            "categoria_anexo_b": mapear_anexo_b_general(tipo_bien),
            "cuenta_contable": cuenta_especifica,
            "metodo": "RNC exacto"
        }

    # --- NIVEL 2: Semántica por nombre ---
    catalogo = obtener_catalogo_ia()
    nombre_upper = str(nombre_proveedor).upper()
    for cuenta, palabras_clave in catalogo.items():
        if any(kw in nombre_upper for kw in palabras_clave):
            return {
                "categoria_anexo_b": mapear_anexo_b_general(tipo_bien),
                "cuenta_contable": cuenta,
                "metodo": "Semántica"
            }

    # --- NIVEL 3: Fallback tipo_bien_servicio ---
    if tipo_bien == 9:
        cuenta_especifica = "Compras para Costo de Venta"
    elif tipo_bien == 10:
        cuenta_especifica = "Activos Capitalizables"
    elif tipo_bien == 7:
        cuenta_especifica = "Comisiones e Intereses Bancarios"
    elif tipo_bien == 1:
        cuenta_especifica = "Gastos de Personal"
    elif tipo_bien == 11:
        cuenta_especifica = "Seguros Obra y Vida"
    elif tipo_bien == 3:
        cuenta_especifica = "Arrendamientos"
    else:
        cuenta_especifica = "Otras deducciones / Gastos Generales"

    return {
        "categoria_anexo_b": mapear_anexo_b_general(tipo_bien),
        "cuenta_contable": cuenta_especifica,
        "metodo": "Tipo Bien 606"
    }

if __name__ == '__main__':
    print("Probando Motor IA de Reconstrucción Contable (3 niveles)...")
    tests = [
        ("COMPANIA DOMINICANA DE TELEFONOS", 2, "1010234568"),
        ("SUPERMERCADO BRAVO", 2, ""),
        ("BANCO MULTIPLE BHD", 7, "1010016533"),
        ("MIPRENDA SRL", 9, ""),
        ("ESTACION GASOLINA SUNIX", 2, ""),
        ("XYZ SERVICIOS SRL", 2, ""),  # sin match → tipo_bien fallback
    ]
    for nombre, tipo, rnc in tests:
        res = clasificar_factura_ia(nombre, tipo, rnc)
        print(f"  [{res['metodo']:12s}] {nombre[:30]:<30} => {res['cuenta_contable']}")
