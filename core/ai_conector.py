"""
ai_conector.py — Conector de IA con failover: Gemini → OpenRouter → Groq
========================================================================
Usa Gemini 2.0 Flash como default (gratis, 1500 req/día).
Fallback automático si un proveedor falla.
"""
import os
import json
import httpx
from typing import Tuple

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
    proveedor_preferido: str = "gemini",
    max_tokens: int = 600
) -> Tuple[str, dict, str]:
    """
    Sistema de FAILOVER. Prueba Gemini, OpenRouter, Groq en ese orden.
    """
    prompt = f"DATOS FISCALES:\n{contexto_fiscal}\n\nPREGUNTA: {pregunta}"
    fallback_order = ["gemini", "openrouter", "groq"]

    if proveedor_preferido in fallback_order:
        fallback_order.remove(proveedor_preferido)
        fallback_order.insert(0, proveedor_preferido)

    for prov in fallback_order:
        key = os.getenv(f"{prov.upper()}_API_KEY", "")
        if not key or len(key) < 8:
            continue
        try:
            if prov == "gemini":
                content, usage = await _llamar_gemini(key, prompt, max_tokens)
            elif prov == "openrouter":
                content, usage = await _llamar_openai(
                    "https://openrouter.ai/api/v1/chat/completions",
                    key, "google/gemini-2.5-flash-exp:free",
                    prompt, max_tokens
                )
            else:  # groq
                content, usage = await _llamar_openai(
                    "https://api.groq.com/openai/v1/chat/completions",
                    key, "llama-3.3-70b-versatile",
                    prompt, max_tokens
                )
            return content, usage, prov
        except Exception as e:
            print(f"[-] {prov}: {e}")
            continue

    return (
        "No hay conexión con los servicios de IA. Revisá las API keys en el .env.",
        {"total_tokens": 0}, "error"
    )


async def _llamar_gemini(key: str, prompt: str, max_tokens: int) -> Tuple[str, dict]:
    """Llama a Gemini 2.0 Flash API (gratis 1500 req/día)."""
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    body = {
        "contents": [{"parts": [{"text": f"{SYSTEM_PROMPT_FISCAL}\n\n{prompt}"}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.3},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{url}?key={key}", json=body)
        if r.status_code != 200:
            raise Exception(f"Gemini HTTP {r.status_code}: {r.text[:200]}")
        data = r.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        usage = {"total_tokens": len(prompt) + len(text)}
        return text, usage


async def _llamar_openai(url: str, key: str, model: str, prompt: str, max_tokens: int) -> Tuple[str, dict]:
    """Llama a cualquier API compatible con OpenAI (OpenRouter, Groq)."""
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_FISCAL},
            {"role": "user", "content": prompt},
        ],
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, json=body)
        r.raise_for_status()
        data = r.json()
        text = data["choices"][0]["message"]["content"].strip()
        usage = data.get("usage", {})
        return text, usage


def construir_contexto_fiscal(resultado_motor: dict) -> str:
    alertas = [c for c in resultado_motor.get("cruces", []) if c.get("estado") == "ROJO"]
    return (
        f"Período: {resultado_motor.get('periodo', 'N/D')}. "
        f"RNC: {resultado_motor.get('rnc', 'N/D')}. "
        f"ISR Estimado: RD${resultado_motor.get('isr_calcular', 0):,.2f}. "
        f"Alertas: {len(alertas)}."
    )


PROVEEDOR_CHAT = "gemini"
