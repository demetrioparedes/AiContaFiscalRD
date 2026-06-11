# AiContaFiscalRD — Guía de Despliegue en Render

## Requisitos

1. Cuenta en [Render.com](https://render.com) (free tier suficiente)
2. Tu repositorio en GitHub (o cualquier git)

## Pasos

### 1. Configurar variables de entorno en Render

| Variable | Valor | Obligatoria |
|----------|-------|-------------|
| `API_SECRET_KEY` | Una clave secreta de tu elección (ej: `AiConta-Prod-2026`) | ✅ Sí |
| `DATABASE_URL` | `postgresql://postgres.ronevguwdmadgwodxqft:MasterOdyn2025%23@aws-1-us-east-1.pooler.supabase.com:6543/postgres` | ⬜ No (si se omite, usa SQLite local) |

### 2. Crear el Web Service

1. En Render Dashboard: **New + → Web Service**
2. Conectá tu repositorio de GitHub
3. Render detecta automáticamente `render.yaml` con la configuración
4. Agregá las variables de entorno arriba mencionadas
5. Hacé clic en **Create Web Service**

### 3. Verificar

Una vez desplegado (aprox 2-3 minutos):

```
curl https://tu-app.onrender.com/api/health
# {"status":"ok","checks":{"database":"connected","storage":"writable"}}
```

### 4. Probar pipeline completo

```bash
# Crear cliente
curl -X POST https://tu-app.onrender.com/api/clientes \
  -H "X-API-KEY: tu-clave" \
  -H "Content-Type: application/json" \
  -d '{"rnc":"130826552","razon_social":"Elvira Comercial SRL"}'

# Consultar riesgo
curl -H "X-API-KEY: tu-clave" \
  "https://tu-app.onrender.com/api/riesgo?rnc=130826552&anio=2025"
```

### 5. Notas importantes

- Render free tier tiene cold start (~30-60s)
- El plan gratuito se duerme a los 15 min sin actividad
- La DB PostgreSQL via Supabase es externa a Render (no se duerme)
