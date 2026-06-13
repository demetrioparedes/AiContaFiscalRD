"""
dependencies.py — Autenticación y Autorización Multi-Contador.
"""
import os
import json
import logging
from datetime import datetime
from typing import List, Optional
import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from core.database import SessionLocal, AiContaUserProfile

security = HTTPBearer(auto_error=False)
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")


class UsuarioActual:
    def __init__(self, user_id: int, auth_user_id: str, email: str, nombre: str,
                 role: str, empresas_ids: List[int], empresa_id: Optional[int]):
        self.id = user_id
        self.auth_user_id = auth_user_id
        self.email = email
        self.nombre = nombre
        self.role = role
        self.empresas_ids = empresas_ids
        self.empresa_id = empresa_id
        self.es_admin = role == "admin"
        self.es_contador = role == "contador"

    def puede_ver_empresa(self, empresa_id: int) -> bool:
        if self.es_admin:
            return True
        return empresa_id in self.empresas_ids

    def puede_editar(self) -> bool:
        return self.role in ("admin", "contador")


async def verificar_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    if credentials is None:
        return None
    token = credentials.credentials
    if not token:
        return None
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise HTTPException(500, detail="Supabase no configurado")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{SUPABASE_URL}/auth/v1/user",
                headers={"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {token}"},
            )
            if resp.status_code != 200:
                raise HTTPException(401, detail="Token inválido o expirado.")
            user_data = resp.json()
            return {"sub": user_data["id"], "email": user_data.get("email", ""),
                    "user_metadata": user_data.get("user_metadata", {})}
    except httpx.TimeoutException:
        raise HTTPException(503, detail="Servicio de autenticación no disponible.")


async def obtener_usuario(payload: dict = Depends(verificar_token)) -> UsuarioActual:
    if payload is None:
        raise HTTPException(401, detail="Se requiere autenticación.")
    auth_user_id = payload.get("sub")
    if not auth_user_id:
        raise HTTPException(401, detail="Token inválido.")
    email = payload.get("email", "")

    # Gestion propia de sesion DB para evitar conflictos con el ciclo de vida de Depends
    db = SessionLocal()
    try:
        perfil = db.query(AiContaUserProfile).filter_by(auth_user_id=auth_user_id).first()
        if not perfil:
            nombre = payload.get("user_metadata", {}).get("full_name", email.split("@")[0] if email else "Usuario")
            perfil = AiContaUserProfile(
                auth_user_id=auth_user_id, email=email, nombre=nombre,
                role="contador", empresas_ids="[]", activo=True,
            )
            db.add(perfil)
            db.commit()
            db.refresh(perfil)
        if not perfil.activo:
            raise HTTPException(403, detail="Cuenta desactivada.")
        perfil.ultimo_acceso = datetime.utcnow()
        db.commit()
        try:
            empresas_ids = json.loads(perfil.empresas_ids or "[]")
        except (json.JSONDecodeError, TypeError):
            empresas_ids = []
        return UsuarioActual(
            user_id=perfil.id, auth_user_id=perfil.auth_user_id, email=perfil.email,
            nombre=perfil.nombre, role=perfil.role, empresas_ids=empresas_ids,
            empresa_id=perfil.empresa_id,
        )
    finally:
        db.close()


def require_admin(usuario: UsuarioActual = Depends(obtener_usuario)):
    if not usuario.es_admin:
        raise HTTPException(403, detail="Se requiere rol de administrador.")
    return usuario


def require_contador(usuario: UsuarioActual = Depends(obtener_usuario)):
    if not usuario.puede_editar():
        raise HTTPException(403, detail="Se requiere rol de administrador o contador.")
    return usuario
