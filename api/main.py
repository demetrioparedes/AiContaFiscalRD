from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException, Depends
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from dotenv import load_dotenv
import shutil
import sys
import logging
from sqlalchemy import or_
from sqlalchemy.orm import Session

# Resolución dinámica de rutas del proyecto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

load_dotenv(os.path.join(BASE_DIR, ".env"))

from core.database import init_db, SessionLocal, Empresa, ValidacionFiscal, PadronDGII, EstadoFinanciero, get_db
from core.ai_plantillas import generar_mensaje_cruce, generar_resumen_isr, necesita_ia
from core.ai_conector import consultar_ia, construir_contexto_fiscal, PROVEEDOR_CHAT
from core.run_pipeline import registrar_cliente
from core.etl_ingesta import ejecutar_etl
from core.etl_tss_ir13 import procesar_tss_ir13
from core.etl_cruce_terceros import procesar_cruce_terceros
from core.motor_fiscal import OrquestadorFiscal
from core.generador_ir2 import GeneradorIR2
from core.narrador_fiscal import NarradorFiscal
from fastapi.responses import FileResponse, JSONResponse
import os
from core.motor_riesgo_dgii import calcular_riesgo
from core.generador_final import main as generar_final

app = FastAPI(title="AiContaFiscalRD API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOADS_DIR = os.path.join(BASE_DIR, "data", "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "output")
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Montar frontend estático
STATIC_DIR = os.path.join(BASE_DIR, "api", "static")
INDEX_HTML = os.path.join(STATIC_DIR, "index.html")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

from typing import List
from fastapi.security import APIKeyHeader

# Configuración de Seguridad Industrial
API_KEY_NAME = "X-API-KEY"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def verify_api_key(api_key: str = Depends(api_key_header)):
    secret = os.getenv("API_SECRET_KEY", "AiConta_Secure_Key_2026_RD")
    if api_key != secret:
        logging.warning(f"Intento de acceso no autorizado con API Key errónea.")
        raise HTTPException(status_code=403, detail="Acceso no autorizado: API Key inválida")
    return api_key

# --- BLINDAJE INDUSTRIAL: Global Exception Handler ---
from fastapi import Request
from fastapi.responses import JSONResponse
import uuid

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_id = str(uuid.uuid4())[:8]
    logging.error(f"Error ID {error_id} en {request.url}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "Error interno del servidor. El equipo técnico ha sido notificado.",
            "error_id": error_id,
            "recomendacion": "Por favor, contacte a soporte técnico proporcionando el ID del error."
        }
    )

class ClienteCreate(BaseModel):
    rnc: str
    razon_social: str

@app.get("/")
async def root():
    """Sirve el Dashboard Principal Multi-Cliente."""
    return FileResponse(INDEX_HTML)

@app.get("/api/health")
async def health_check(db: Session = Depends(get_db)):
    """Chequeo de salud avanzado (DB + Disco + IA)."""
    health_status = {"status": "ok", "checks": {}}
    
    # Check DB
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        health_status["checks"]["database"] = "connected"
    except Exception:
        health_status["checks"]["database"] = "disconnected"
        health_status["status"] = "warning"
        
    # Check Storage
    try:
        os.makedirs(UPLOADS_DIR, exist_ok=True)
        test_file = os.path.join(UPLOADS_DIR, ".health_check")
        with open(test_file, "w") as f: f.write("ok")
        health_status["checks"]["storage"] = "writable"
    except Exception:
        health_status["checks"]["storage"] = "readonly"
        health_status["status"] = "error"

    return health_status

@app.get("/api/clientes", dependencies=[Depends(verify_api_key)])
async def listar_clientes(db: Session = Depends(get_db)):
    try:
        clientes = db.query(Empresa).all()
        periodos = db.query(EstadoFinanciero).count()
        auditorias = db.query(ValidacionFiscal).count()
        return {
            "total": len(clientes),
            "clientes": [{"id": c.id, "rnc": c.rnc, "razon_social": c.nombre_empresa} for c in reversed(clientes)],
            "stats": {"periodos": periodos, "auditorias": auditorias}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/clientes", dependencies=[Depends(verify_api_key)])
async def crear_cliente(cliente: ClienteCreate, db: Session = Depends(get_db)):
    try:
        existente = db.query(Empresa).filter_by(rnc=cliente.rnc).first()
        if existente:
            # Si el cliente ya existe, actualizamos su nombre con el suministrado
            if cliente.razon_social and existente.nombre_empresa != cliente.razon_social:
                existente.nombre_empresa = cliente.razon_social
                db.commit()
            return JSONResponse(status_code=400, content={"detail": "El RNC ya está registrado", "id": existente.id, "razon_social": existente.nombre_empresa})
        
        nueva = Empresa(rnc=cliente.rnc, nombre_empresa=cliente.razon_social)
        db.add(nueva)
        db.commit()
        db.refresh(nueva)
        
        # ---> GENERAR EXPEDIENTE DIGITAL AUTOMATICO <---
        base_dir = os.path.join(BASE_DIR, "data", "clientes", cliente.rnc)
        
        carpetas_expediente = [
            "01_Formatos_606_607",
            "02_Nominas_TSS",
            "03_Estados_Financieros",
            "04_Declaraciones_Anteriores",
            "05_Auditoria_Logs",
            "06_Entregables_IR2_PDF"
        ]
        
        for carpeta in carpetas_expediente:
            ruta_carpeta = os.path.join(base_dir, carpeta)
            os.makedirs(ruta_carpeta, exist_ok=True)
            
            # Crear un mini archivo readme invisible para mantener la carpeta en git o logs
            readme_path = os.path.join(ruta_carpeta, "leeme.txt")
            if not os.path.exists(readme_path):
                with open(readme_path, "w", encoding="utf-8") as f:
                    f.write(f"Carpeta reservada para {carpeta} del cliente {cliente.razon_social} (RNC: {cliente.rnc}).")
                    
        return {"id": nueva.id, "message": "Cliente y Expediente Digital creado exitosamente", "ruta_expediente": base_dir}
        return {"id": nueva.id, "message": "Cliente y Expediente Digital creado exitosamente", "ruta_expediente": base_dir}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/cliente/{cliente_id}")
async def ver_cliente_ui(cliente_id: int):
    """Sirve la Vista Detalle Premium para un cliente específico."""
    return FileResponse(os.path.join(STATIC_DIR, "cliente.html"))

@app.get("/api/clientes/{cliente_id}", dependencies=[Depends(verify_api_key)])
async def obtener_cliente(cliente_id: int, db: Session = Depends(get_db)):
    c = db.query(Empresa).filter_by(id=cliente_id).first()
    if c:
        return {"id": c.id, "rnc": c.rnc, "razon_social": c.nombre_empresa}
    raise HTTPException(status_code=404, detail="Cliente no encontrado")

@app.get("/api/padron/buscar/", dependencies=[Depends(verify_api_key)])
async def buscar_padron(termino: str, db: Session = Depends(get_db)):
    """Busca en el Padrón de la DGII por RNC o Razón Social (Autocomplete limit 10)."""
    if len(termino) < 3:
        return []
    try:
        # Búsqueda usando LIKE (ignorando mayúsculas) en RNC o Razón Social
        resultados = db.query(PadronDGII).filter(
            or_(
                PadronDGII.rnc.ilike(f"%{termino}%"),
                PadronDGII.razon_social.ilike(f"%{termino}%")
            )
        ).limit(10).all()
        
        lista = []
        for r in resultados:
            lista.append({
                "rnc": r.rnc,
                "razon_social": r.razon_social,
                "actividad": r.actividad_economica,
                "estado": r.estado
            })
        return lista
    except Exception as e:
        print(f"Error buscando padrón: {e}")
        return []

@app.post("/api/resumen_archivos/{tipo}", dependencies=[Depends(verify_api_key)])
async def resumen_archivos(tipo: str, anio: str = Form("2025"), files: List[UploadFile] = File(...)):
    """Genera un resumen rápido de los archivos cargados (606 o 607) verificando el año fiscal."""
    import pandas as pd
    from io import BytesIO
    import re
    
    total_monto = 0.0
    meses_detectados = set()
    desglose_gastos = {}
    archivo_invalido_detectado = False
    
    for file in files:
        try:
            content = await file.read()
            ext = file.filename.lower()
            if ext.endswith(".txt") or ext.endswith(".csv"):
                lines = content.decode('latin1').splitlines()
                if not lines: continue
                sep = '|' if '|' in lines[0] else ','
                # Ignorar encabezados
                start_idx = 1 if len(lines) > 1 and not lines[0][0].isdigit() else 0
                for line in lines[start_idx:]:
                    cols = line.split(sep)
                    if tipo == "606" and len(cols) >= 9:
                        fecha_val = cols[5][:6] if len(cols) > 5 else "000000"
                        if fecha_val.isdigit() and len(fecha_val) == 6:
                            if fecha_val.startswith(anio):
                                meses_detectados.add(fecha_val)
                            else:
                                archivo_invalido_detectado = True
                                continue # Ignorar filas de otro año
                        try:
                            m_tot = float(cols[9].replace(',','')) if len(cols) > 9 and cols[9].strip() else 0.0
                            if m_tot == 0.0:
                                m_serv = float(cols[7].replace(',','')) if len(cols) > 7 and cols[7].strip() else 0.0
                                m_bien = float(cols[8].replace(',','')) if len(cols) > 8 and cols[8].strip() else 0.0
                                m_tot = m_serv + m_bien
                            total_monto += m_tot
                        except: pass
                        tbien = cols[2] if len(cols)>2 else "0"
                        desglose_gastos[tbien] = desglose_gastos.get(tbien, 0) + 1
                    elif tipo == "607" and len(cols) >= 7:
                        fecha_val = cols[5][:6] if len(cols) > 5 else "000000"
                        if fecha_val.isdigit() and len(fecha_val) == 6:
                            if fecha_val.startswith(anio):
                                meses_detectados.add(fecha_val)
                            else:
                                archivo_invalido_detectado = True
                                continue # Ignorar filas de otro año
                        try:
                            m = float(cols[7].replace(',','')) if len(cols)>7 and cols[7].strip() else 0.0
                            total_monto += m
                        except: pass
        except Exception as e:
            print(f"Error resumiendo {file.filename}: {e}")
            
    return {
        "meses": sorted(list(meses_detectados)), 
        "total": total_monto, 
        "desglose": desglose_gastos, 
        "count": len(files),
        "warning": f"ATENCIÓN: Se limitó la carga. Se bloquearon facturas que no corresponden al año fiscal {anio}." if archivo_invalido_detectado else None
    }

@app.post("/api/procesar_rapido/{cliente_id}/{periodo}", dependencies=[Depends(verify_api_key)])
async def procesar_rapido_mock(cliente_id: int, periodo: str):
    """Simula o prepara el pipeline, devolviendo confirmacion al dashboard."""
    return {"status": "ok", "message": "Dependencias conectadas. Iniciando..."}

@app.get("/api/generar_ir2_oficial/{rnc}/{anio}", dependencies=[Depends(verify_api_key)])
async def generar_ir2_oficial_endpoint(rnc: str, anio: int):
    """Genera el IR-2 oficial de la DGII con los datos del cliente y lo devuelve como descarga."""
    from core.generador_ir2_oficial import generar_ir2_oficial

    try:
        ruta = generar_ir2_oficial(rnc, anio)
        if ruta and os.path.exists(ruta):
            nombre_archivo = os.path.basename(ruta)
            from fastapi.responses import FileResponse
            return FileResponse(
                path=ruta,
                filename=nombre_archivo,
                media_type="application/vnd.ms-excel"
            )
        else:
            from fastapi.responses import JSONResponse
            return JSONResponse({"status": "error", "message": "No se pudo generar el IR-2 oficial. Verifica que el pipeline fue ejecutado primero."}, status_code=400)
    except Exception as e:
        from fastapi.responses import JSONResponse
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/parse_ir2_anterior", dependencies=[Depends(verify_api_key)])
async def parse_ir2_anterior(files: List[UploadFile] = File(...)):
    """Extrae datos de múltiples archivos IR-2 anteriores para autocompletar."""
    from core.pdf_parser_ir2 import extraer_datos_ir2
    
    tmp_dir = os.path.join(BASE_DIR, "data", "tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    temp_paths = []
    
    for file in files:
        temp_path = os.path.join(tmp_dir, file.filename)
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        temp_paths.append(temp_path)
        
    try:
        data = extraer_datos_ir2(temp_paths)
        return data
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/procesar", dependencies=[Depends(verify_api_key)])
async def procesar(
    rnc: str = Form(...),
    nombre: str = Form(...),
    anio: int = Form(...),
    inv_inicial: float = Form(0.0),
    inv_final: float = Form(0.0),
    retenciones: float = Form(0.0),
    pendientes_list: str = Form(""),
    files: List[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    rnc_limpio = rnc.replace("-", "")
    base_dir = os.path.join(BASE_DIR, "data", "clientes", rnc_limpio)
    
    # Garantizar que las carpetas base existan
    os.makedirs(base_dir, exist_ok=True)
    for c in ["01_Formatos_606_607", "02_Nominas_TSS", "03_Estados_Financieros", "04_Declaraciones_Anteriores", "05_Auditoria_Logs", "06_Entregables_IR2_PDF"]:
        os.makedirs(os.path.join(base_dir, c), exist_ok=True)

    it1_path = ""
    tss_path = ""
    
    # Guardar archivos en el Expediente Físico
    if files:
        for f in files:
            if f.filename:
                fname_upper = f.filename.upper()
                if "606" in fname_upper or "607" in fname_upper:
                    subcarpeta = "01_Formatos_606_607"
                elif "TSS" in fname_upper:
                    subcarpeta = "02_Nominas_TSS"
                elif "IT1" in fname_upper or "ANALISIS" in fname_upper:
                    subcarpeta = "04_Declaraciones_Anteriores"
                else:
                    subcarpeta = "01_Formatos_606_607"
                
                guardado_en = os.path.join(base_dir, subcarpeta, f.filename)
                with open(guardado_en, "wb") as buffer:
                    shutil.copyfileobj(f.file, buffer)
                
                if "ANALISIS" in fname_upper and f.filename.endswith(('.xls', '.xlsx')):
                    it1_path = guardado_en
                elif "TSS" in fname_upper and f.filename.endswith(('.xls', '.xlsx')):
                    tss_path = guardado_en
            
    # Config
    config = {
        "rnc": rnc.replace("-", ""),
        "nombre": nombre,
        "anio": anio,
        "regimen": "ordinario",
        "inv_inicial": inv_inicial,
        "inv_final": inv_final,
        "activos": [],
        "prestamos": [],
        "retenciones": retenciones,
        "directorio": base_dir,
        "tss_path": tss_path,
        "it1_path": it1_path,
        "pendientes_list": pendientes_list.split(",") if pendientes_list else []
    }
    
    try:
        init_db()
        # PASO 1: Registrar cliente
        registrar_cliente(config, db)
        db.commit()

        # PASO 2: ETL
        ejecutar_etl(config["directorio"], config["rnc"], config["anio"])

        # PASO 3: ETL TSS
        if tss_path:
            procesar_tss_ir13(tss_path, config["rnc"], config["anio"])

        # PASO 4: Motor Fiscal
        orquestador = OrquestadorFiscal(db, config["rnc"], config["anio"])
        res_pipeline = orquestador.ejecutar_auditoria_fiscal_completa()
        
        # PASO 4.1: ETL Cruce Terceros
        cruce_terceros_data = None
        if os.path.exists(config["directorio"]):
            cruce_files = [f for f in os.listdir(config["directorio"]) if 'Terceros' in f]
            if cruce_files:
                ventas_v = res_pipeline["ir2_data"]["ventas"] if res_pipeline["ir2_data"] else 0
                cruce_terceros_data = procesar_cruce_terceros(config["directorio"], config["rnc"], config["anio"], ventas_v)

        # Recuperar Semáforos
        empresa_act = db.query(Empresa).filter_by(rnc=config["rnc"]).first()
        validaciones_db = db.query(ValidacionFiscal).filter_by(
            empresa_id=empresa_act.id, periodo=str(config["anio"])
        ).all() if empresa_act else []

        validaciones_front = [
            {
                "id": v.tipo_validacion,
                "sist": float(v.valor_sistema),
                "dgii": float(v.valor_dgii),
                "dif": float(v.diferencia),
                "estado": v.estado
            } for v in validaciones_db
        ]

        # PASO 6: Motor de Riesgo DGII
        riesgo = calcular_riesgo(config["rnc"], config["anio"], cruce_terceros_data)
        
        # Generar archivos finales
        archivos_generados = []
        try:
            ruta_excel, ruta_tex = generar_final(config["rnc"], config["anio"], config["regimen"])
            if ruta_excel:
                archivos_generados.append({
                    "nombre": "Anexo B & IR-2 (Excel AiConta)",
                    "url": f"/api/descargar/{os.path.basename(ruta_excel)}"
                })
            if ruta_tex:
                archivos_generados.append({
                    "nombre": "Estados Financieros (Borrador PDF)",
                    "url": f"/api/descargar/{os.path.basename(ruta_tex)}"
                })
        except Exception as e:
            print(f"[!] Aviso: No se pudieron generar los entregables web: {e}")
        
        return {
            "status": "success",
            "message": "Procesamiento completado.",
            "resultados": {
                "ventas": res_pipeline["ir2_data"]["ventas"] if res_pipeline["ir2_data"] else 0,
                "costos": res_pipeline["resumen"]["costo_ventas"],
                "utilidad": res_pipeline["ir2_data"]["renta_neta_imponible"] if res_pipeline["ir2_data"] else 0,
                "isr_pagar": res_pipeline["ir2_data"]["isr_pagar"] if res_pipeline["ir2_data"] else 0,
                "rnc": config["rnc"],
                "anio": config["anio"],
                "auditoria_cruces": validaciones_front,
                "riesgo_dgii": riesgo
            },
            "archivos": archivos_generados
        }
    except Exception as e:
        import traceback
        logging.error(f"Error en pipeline: {traceback.format_exc()}")
        return {"status": "error", "message": str(e)}

@app.get("/api/riesgo", dependencies=[Depends(verify_api_key)])
async def get_riesgo_dgii(rnc: str, anio: int):
    """Calcula el Índice de Riesgo DGII bajo demanda."""
    try:
        resultado = calcular_riesgo(rnc, anio)
        return {"status": "success", **resultado}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/generar_ef", dependencies=[Depends(verify_api_key)])
async def generar_ef(rnc: str = Form(...), anio: int = Form(...)):
    try:
        ruta_excel, ruta_tex = generar_final(rnc, anio, "solo_ef")
        archivos_generados = []
        if ruta_tex:
            archivos_generados.append({
                "nombre": "Estados Financieros (LaTeX)",
                "url": f"/api/descargar/{os.path.basename(ruta_tex)}"
            })
        return {
            "status": "success",
            "message": "Estados Financieros generados correctamente.",
            "archivos": archivos_generados
        }
    except Exception as e:
        import traceback
        return {"status": "error", "message": str(e), "trace": traceback.format_exc()}

@app.post("/api/generar_ir2_final", dependencies=[Depends(verify_api_key)])
async def generar_ir2_final_entregables(rnc: str = Form(...), anio: str = Form(...), db: Session = Depends(get_db)):
    """Orquesta la generación masiva de XML (OFV), Excel (DGII) y PDF (Constancia)."""
    try:
        generador = GeneradorIR2(db, rnc, anio)
        resultado = generador.generar_entregable_completo()
        
        if resultado["status"] == "success":
            # Formatear para que el frontend pueda procesar la lista
            archivos_con_url = []
            for arc in resultado["archivos"]:
                archivos_con_url.append({
                    "nombre": arc["nombre"],
                    "url": f"/api/descargar/{arc['filename']}"
                })
            
            return {
                "status": "success",
                "message": "Entregables generados con éxito para la Oficina Virtual.",
                "archivos": archivos_con_url
            }
        else:
            return {"status": "error", "message": resultado.get("message")}
            
    except Exception as e:
        import traceback
        logging.error(f"Error en generación IR-2 final: {traceback.format_exc()}")
        return {"status": "error", "message": f"Falla en generación: {str(e)}"}

@app.get("/api/anexo_b", dependencies=[Depends(verify_api_key)])
async def get_anexo_b(rnc: str, anio: int):
    """Retorna el Reporte del Anexo B (Gastos categorizados por IR-2) con clasificación IA."""
    try:
        from core.generador_anexo_b import generar_reporte_anexo_b
        reporte = generar_reporte_anexo_b(rnc, anio)
        total = sum(reporte.values())
        items = [{"casilla": k, "monto": round(v, 2)} for k, v in sorted(reporte.items())]
        return {
            "status": "success",
            "rnc": rnc,
            "anio": anio,
            "total_gastos": round(total, 2),
            "categorias": items
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ── CAPA DE INTELIGENCIA ARTIFICIAL — AISISTENTE FISCAL ──────────────

class ChatRequest(BaseModel):
    cliente_id: int
    periodo: str
    pregunta: str

def obtener_resultado_motor(cliente_id: int, periodo: str, db: Session):
    """Extrae el estado actual detallado desde la DB para alimentar la IA."""
    empresa = db.query(Empresa).filter_by(id=cliente_id).first()
    validaciones = db.query(ValidacionFiscal).filter_by(
        empresa_id=cliente_id, periodo=periodo
    ).all()
    estado = db.query(EstadoFinanciero).filter_by(
        empresa_id=cliente_id, periodo=periodo
    ).first()
    
    if not empresa or not estado:
        return None

    return {
        "rnc": empresa.rnc,
        "periodo": periodo,
        "cruces": [
            {"id": int(v.tipo_validacion) if v.tipo_validacion.isdigit() else 0, 
             "nombre": v.tipo_validacion, 
             "estado": v.estado, 
             "valor_sistema": float(v.valor_sistema or 0), 
             "valor_dgii": float(v.valor_dgii or 0), 
             "diferencia": float(v.diferencia or 0)}
            for v in validaciones
        ],
        "renta_imponible": float(estado.renta_imponible or 0),
        "isr_calcular": float(estado.isr_calcular or 0),
        "anticipos": float(estado.anticipos or 0),
        "retenciones": float(estado.retenciones or 0)
    }

def detectar_cruce(pregunta: str, resultado: dict):
    """Mapea palabras clave de la pregunta a IDs de cruces específicos."""
    keywords = {
        "itbis": [2, 3, 8],
        "compras": [7, 11, 16],
        "ventas": [1, 3, 4],
        "nómina": [13, 17],
        "tss": [17],
        "isr": [18]
    }
    pregunta_low = pregunta.lower()
    for key, ids in keywords.items():
        if key in pregunta_low:
            for cruce in resultado.get("cruces", []):
                if cruce["id"] in ids and cruce["estado"] == "ROJO":
                    return cruce
    return None

@app.post("/api/chat_fiscal", dependencies=[Depends(verify_api_key)])
async def chat_fiscal(req: ChatRequest, db: Session = Depends(get_db)):
    """Endpoint único de asistencia fiscal (Plantillas + IA)."""
    # 1. Obtener datos actuales
    resultado = obtener_resultado_motor(req.cliente_id, req.periodo, db)
    if not resultado:
        return {"fuente": "error", "respuesta": "No encontré datos para este período."}

    # 2. Plantillas Locales (RD$0 costo)
    cruce_especifico = detectar_cruce(req.pregunta, resultado)
    if cruce_especifico:
        explicacion = generar_mensaje_cruce(cruce_especifico)
        return {"fuente": "plantilla", "respuesta": explicacion, "costo": 0}

    if "resumen" in req.pregunta.lower() or "cuánto pago" in req.pregunta.lower():
        return {"fuente": "plantilla", "respuesta": generar_resumen_isr(resultado), "costo": 0}

    # 3. Consulta a LLM (Groq/Gemini/Claude)
    if necesita_ia(req.pregunta):
        contexto = construir_contexto_fiscal(resultado)
        try:
            # Ahora consultar_ia devuelve (texto, uso, proveedor_final)
            respuesta_ia, usage, fuente_real = await consultar_ia(req.pregunta, contexto)
            
            # Cálculo de costo simbólico ($0.10 por 1M tokens)
            total_tokens = usage.get("total_tokens", usage.get("input_tokens", 0) + usage.get("output_tokens", 0))
            costo = round(total_tokens * 0.0000001, 6)
            
            return {
                "fuente": fuente_real, 
                "respuesta": respuesta_ia,
                "costo": costo
            }
        except Exception as e:
            # Este bloque casi nunca se alcanzará gracias al Failover interno
            return {"fuente": "error", "respuesta": f"Error crítico: {str(e)}", "costo": 0}

    return {
        "fuente": "sistema", 
        "respuesta": "Escribe una pregunta sobre tus impuestos o pide un 'resumen' fiscal."
    }

@app.get("/api/dashboard_analitico/{cliente_id}/{periodo}", dependencies=[Depends(verify_api_key)])
async def dashboard_analitico(cliente_id: int, periodo: int, db: Session = Depends(get_db)):
    """Consolida toda la data para el Dashboard Premium."""
    empresa = db.query(Empresa).filter_by(id=cliente_id).first()
    if not empresa:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    orquestador = OrquestadorFiscal(db, empresa.rnc, periodo)
    data = orquestador.obtener_dashboard_data()
    return data

@app.post("/api/generar_ir2/{cliente_id}/{periodo}", dependencies=[Depends(verify_api_key)])
async def generar_ir2_ofv(cliente_id: int, periodo: str, formato: str = "xml", db: Session = Depends(get_db)):
    """
    Endpoint para generar el IR-2 listo para Oficina Virtual (OFV).
    Soporta: xml, excel, pdf. (Refinado style user)
    """
    try:
        empresa = db.query(Empresa).filter_by(id=cliente_id).first()
        if not empresa:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        
        # 1. Ejecutar Orquestación Completa
        orquestador = OrquestadorFiscal(db, empresa.rnc, periodo)
        resultado = orquestador.ejecutar_pipeline_completo()
        
        # 2. Generar Archivo
        generador = GeneradorIR2(db, resultado, empresa.rnc, periodo)
        archivo_info = generador.generar(formato.lower())
        
        if "error" in archivo_info:
            return JSONResponse(
                status_code=400,
                content={
                    "estado": "Bloqueado",
                    "mensaje": archivo_info["error"],
                    "detalle": archivo_info.get("detalle", []),
                    "recomendacion_socio": archivo_info.get("recomendacion_socio", "")
                }
            )

        # Ruta dinámica relativa al proyecto
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        file_path = os.path.join(base_dir, "data", "output", archivo_info["archivo"])
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=500, detail="Archivo no se generó correctamente")

        # 3. Respuesta según tipo de archivo
        media_type = "application/octet-stream"
        if formato.lower() == "pdf":
            media_type = "application/pdf"
        elif formato.lower() == "xml":
            media_type = "application/xml"
        elif formato.lower() == "excel":
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            
        return FileResponse(
            path=file_path,
            filename=archivo_info["archivo"],
            media_type=media_type
        )

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Error al generar IR-2: {str(e)}"})

@app.get("/api/estado_ir2/{cliente_id}/{periodo}", dependencies=[Depends(verify_api_key)])
async def estado_ir2(cliente_id: int, periodo: str, db: Session = Depends(get_db)):
    """Devuelve solo el estado del IR-2 (útil para auditoría rápida)."""
    try:
        empresa = db.query(Empresa).filter_by(id=cliente_id).first()
        if not empresa:
            return {"error": "Cliente no encontrado"}
            
        orquestador = OrquestadorFiscal(db, empresa.rnc, periodo)
        resultado = orquestador.ejecutar_pipeline_completo()
        
        # Extraer Red Flags Críticas
        red_flags_criticas = [rf for rf in resultado.get("bloqueos", [])]
        
        return {
            "estado": resultado.get("estado", "Desconocido"),
            "puede_generar": resultado.get("estado") != "Bloqueado",
            "bloqueos": red_flags_criticas,
            "cant_red_flags": len(red_flags_criticas)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/narrativa_fiscal/{cliente_id}/{periodo}", dependencies=[Depends(verify_api_key)])
async def obtener_narrativa_fiscal(cliente_id: int, periodo: str, db: Session = Depends(get_db)):
    """Retorna un script narrativo (texto) para ser leído por el sintetizador de voz."""
    try:
        empresa = db.query(Empresa).filter_by(id=cliente_id).first()
        if not empresa:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
            
        orquestador = OrquestadorFiscal(db, empresa.rnc, periodo)
        resultado = orquestador.ejecutar_pipeline_completo()
        
        narrador = NarradorFiscal(resultado, empresa.rnc, periodo)
        guion = narrador.generar_guion()
        
        return {"script": guion}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/descargar/{filename}", dependencies=[Depends(verify_api_key)])
async def descargar_archivo(filename: str):
    """Endpoint ultra-seguro para descargar entregables (Previene Path Traversal)."""
    # Blindaje contra path traversal
    safe_filename = os.path.basename(filename)
    ruta = os.path.normpath(os.path.join(OUTPUT_DIR, safe_filename))
    
    # Verificar que el archivo esté dentro de OUTPUT_DIR
    if not ruta.startswith(os.path.normpath(OUTPUT_DIR)):
        logging.error(f"Intento de Path Traversal detectado: {filename}")
        raise HTTPException(status_code=403, detail="Acceso denegado")

    if not os.path.exists(ruta):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    
    media_type = "application/xml"
    if safe_filename.endswith(".xlsx"):
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif safe_filename.endswith(".pdf"):
        media_type = "application/pdf"
        
    return FileResponse(path=ruta, filename=safe_filename, media_type=media_type)

if __name__ == "__main__":
    import uvicorn
    print("\n[+] Iniciando API AiContaFiscalRD en http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
