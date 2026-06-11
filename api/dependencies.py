"""
dependencies.py — Autenticación y Autorización Multi-Contador.
============================================================
Usa JWT de Supabase Auth (GoTrue) validado localmente con PyJWT.
Tres roles: admin, contador, cliente.

Flujo:
  1. Frontend login con email/password → Supabase Auth devuelve JWT
  2. Frontend envía JWT en header Authorization: Bearer <token>
  3. Este módulo valida el JWT y extrae el perfil de usuario
  4. Filtra datos según empresas_ids[] del perfil
"""
import os
import json
import logging
import jwt as pyjwt
from datetime import datetime
from typing import List, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database import SessionLocal, UserProfile

# Scheme para extraer el Bearer token del header
security = HTTPBearer(auto_error=False)

# La clave pública para verificar JWT de Supabase
# Supabase usa HS256 con el anon_key como secreto
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")


class UsuarioActual:
    """Representa el usuario autenticado y sus permisos."""
    def __init__(self, user_id: int, auth_user_id: str, email: str, nombre: str,
                 role: str, empresas_ids: List[int], empresa_id: Optional[int]):
        self.id = user_id
        self.auth_user_id = auth_user_id
        self.email = email
        self.nombre = nombre
        self.role = role
        self.empresas_ids = empresas_ids      # IDs de empresas que puede ver
        self.empresa_id = empresa_id           # Empresa específica (role=cliente)
        self.es_admin = role == "admin"
        self.es_contador = role == "contador"
        self.es_cliente = role == "cliente"

    def puede_ver_empresa(self, empresa_id: int) -> bool:
        """Verifica si el usuario tiene acceso a una empresa específica."""
        if self.es_admin:
            return True
        return empresa_id in self.empresas_ids

    def puede_editar(self) -> bool:
        """Solo admin y contador pueden ejecutar el pipeline."""
        return self.role in ("admin", "contador")


def verificar_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """
    Verifica el JWT de Supabase.
    Si no hay token, devuelve None (para endpoints públicos).
    """
    if credentials is None:
        return None

    token = credentials.credentials
    if not token:
        return None

    try:
        # Verificar JWT con el anon_key de Supabase (HS256)
        payload = pyjwt.decode(
            token,
            SUPABASE_ANON_KEY,
            algorithms=["HS256"],
            options={"verify_aud": False}  # Supabase no siempre setea aud
        )
        return payload
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión expirada. Inicia sesión nuevamente."
        )
    except pyjwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token inválido: {str(e)}"
        )


def obtener_usuario(
    payload: dict = Depends(verificar_token),
    db: Session = Depends(SessionLocal)
) -> UsuarioActual:
    """
    Obtiene el perfil completo del usuario desde la DB.
    Dependencia principal para rutas protegidas.
    """
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere autenticación. Enviá un token JWT en el header Authorization: Bearer."
        )

    auth_user_id = payload.get("sub")
    if not auth_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido: no contiene subject (sub)."
        )

    perfil = db.query(UserProfile).filter_by(auth_user_id=auth_user_id).first()
    if not perfil:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no registrado. Contactá al administrador."
        )

    if not perfil.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cuenta desactivada. Contactá al administrador."
        )

    # Actualizar último acceso
    perfil.ultimo_acceso = datetime.utcnow()
    db.commit()

    # Parsear empresas_ids desde JSON
    try:
        empresas_ids = json.loads(perfil.empresas_ids or "[]")
    except (json.JSONDecodeError, TypeError):
        empresas_ids = []

    return UsuarioActual(
        user_id=perfil.id,
        auth_user_id=perfil.auth_user_id,
        email=perfil.email,
        nombre=perfil.nombre,
        role=perfil.role,
        empresas_ids=empresas_ids,
        empresa_id=perfil.empresa_id,
    )


def require_admin(usuario: UsuarioActual = Depends(obtener_usuario)):
    """Solo administradores."""
    if not usuario.es_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de administrador."
        )
    return usuario


def require_contador(usuario: UsuarioActual = Depends(obtener_usuario)):
    """Admin o contador."""
    if not usuario.puede_editar():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de administrador o contador."
        )
    return usuario
