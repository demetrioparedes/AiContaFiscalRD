import os
import httpx
import asyncio
from typing import Optional, Tuple
from dotenv import load_dotenv

# Carga forzada de entorno
load_dotenv()

# --- CONFIGURACIÓN DE INTELIGENCIA REAL ---
SYSTEM_PROMPT_FISCAL = """Eres un asesor fiscal experto en el sistema 
tributario de República Dominicana (DGII). Conoces a fondo la Ley 11-92, 
Ley 32-23, Norma General 06-18, formatos 606/607, IT-1, IR-2 y TSS.

Responde SIEMPRE en español dominicano claro y directo. 
Sin tecnicismos innecesarios. El usuario es un contador o empresario.
Sé conciso — máximo 3 párrafos por respuesta.
Cuando cites normativa, incluye el artículo exacto."""

async def consultar_ia(
    pregunta: str,
    contexto_fiscal: str,
    proveedor_preferido: str = None,
    max_tokens: int = 600
) -> Tuple[str, dict, str]:
    """
    Sistema de FAILOVER Dinámico. Sin simulaciones.
    Intenta proveedores en cascada hasta obtener una respuesta real.
    """
    failover_order = ["openrouter", "groq", "gemini", "claude"]
    
    if proveedor_preferido and proveedor_preferido in failover_order:
        failover_order.remove(proveedor_preferido)
        failover_order.insert(0, proveedor_preferido)

    prompt_usuario = (
        f"DATOS FISCALES DEL CLIENTE:\n{contexto_fiscal}\n\n"
        f"PREGUNTA: {pregunta}"
    )

    for prov in failover_order:
        # Carga dinámica de credenciales según el proveedor actual
        key = os.getenv(f"{prov.upper()}_API_KEY")
        
        # Validar si existe clave y no es el marcador de posición
        if not key or "tu_clave" in key.lower() or len(key) < 10:
            continue

        try:
            if prov == "claude":
                content, usage = await _llamar_claude(key, prompt_usuario, max_tokens)
            else:
                model = "google/gemini-2.0-flash-exp:free" if prov == "openrouter" else "llama-3.3-70b-versatile"
                content, usage = await _llamar_openai_compatible(prov, key, model, prompt_usuario, max_tokens)
            
            return content, usage, prov
        except Exception as e:
            print(f"[-] FALLO EN {prov.upper()}: {str(e)}")
            continue

    # FALLBACK FINAL (Sólo si TODO falla por red o cuotas)
    return (
        "¡Lo siento! No he podido conectar con ninguno de los cerebros de IA (OpenRouter/Groq/Gemini). "
        "Por favor, revisa tu conexión a internet o tus llaves de acceso en el archivo .env.",
        {"total_tokens": 0}, "error"
    )

async def _llamar_openai_compatible(prov: str, key: str, model: str, prompt: str, max_tokens: int) -> Tuple[str, dict]:
    url = "https://openrouter.ai/api/v1/chat/completions" if prov == "openrouter" else "https://api.groq.com/openai/v1/chat/completions"
    
    # Reparación de Headers para OpenRouter (Crucial)
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type":  "application/json",
        "X-Title": "AiContaFiscalRD",
        "HTTP-Referer": "http://localhost:8000"
    }

    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_FISCAL},
            {"role": "user", "content": prompt},
        ],
    }
    
    async with httpx.AsyncClient(timeout=45) as client:
        r = await client.post(url, headers=headers, json=body)
        if r.status_code != 200:
            print(f"DEBUG {prov}: {r.status_code} - {r.text}")
        r.raise_for_status()
        res = r.json()
        content = res["choices"][0]["message"]["content"].strip()
        usage = res.get("usage", {"total_tokens": 0})
        return content, usage

async def _llamar_claude(key: str, prompt: str, max_tokens: int) -> Tuple[str, dict]:
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    body = {
        "model": "claude-3-haiku-20240307",
        "max_tokens": max_tokens,
        "system": SYSTEM_PROMPT_FISCAL,
        "messages": [{"role": "user", "content": prompt}],
    }
    async with httpx.AsyncClient(timeout=45) as client:
        r = await client.post(url, headers=headers, json=body)
        r.raise_for_status()
        res = r.json()
        content = res["content"][0]["text"].strip()
        usage = res.get("usage", {"total_tokens": 0})
        return content, usage

def construir_contexto_fiscal(resultado_motor: dict) -> str:
    """Extrae puntos clave del análisis para el LLM."""
    alertas = [c for c in resultado_motor.get("cruces", []) if c.get("estado") == "ROJO"]
    return (
        f"Período: {resultado_motor.get('periodo', 'N/D')}. "
        f"RNC: {resultado_motor.get('rnc', 'N/D')}. "
        f"ISR Estimado: RD${resultado_motor.get('isr_calcular', 0):,.2f}. "
        f"Alertas de Riesgo: {len(alertas)}."
    )

# --- COMPATIBILIDAD ---
PROVEEDOR_CHAT = "openrouter" # Default
