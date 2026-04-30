# Sonora's Carbón y Sal — Módulo de Ofertas

Automatización del ciclo: **Facebook → GHL → MCP → Página web**.

Cuando el restaurante publica una oferta en Facebook, esta se publica automáticamente en la página web del cliente (hosteada en GHL Funnel) y se desactiva sola al expirar.

---

## Flujo

1. Sonora's publica oferta en su página de Facebook.
2. **GHL Workflow** se dispara con el Facebook trigger.
3. **AI Decision Maker** filtra: ¿el post es una oferta? Si no, termina.
4. **GPT-OpenAI** parsea el post y extrae: título, descripción, imagen, fecha de vigencia.
5. **Webhook** → `POST /sonoras/offers/create` → guarda en SQLite.
6. **Funnel page** hace `fetch` a `/sonoras/offers/list` y renderiza dinámicamente.
7. Workflow espera hasta `expires_at` (Wait node) → `PATCH /sonoras/offers/deactivate/{id}`.

---

## Estructura

```
projects/sonoras/
├── __init__.py
├── offers.py   # endpoints (FastAPI router)
├── db.py       # conexión SQLite + init
├── seed.sql    # schema de la tabla offers
└── README.md   

data/
└── sonoras.db      # archivo SQLite — montado como volumen Docker
```

---

## Endpoints

| Método | Ruta | Auth | Quién lo llama |
|---|---|---|---|
| `POST` | `/sonoras/offers/create` | `x-api-key` | GHL Workflow |
| `GET` | `/sonoras/offers/list` | público | JS de la funnel page |
| `PATCH` | `/sonoras/offers/deactivate/{id}` | `x-api-key` | GHL Workflow (post-Wait) |

`GET /list` es público a propósito — lo consume el JS de la página web.

---

## Schema (resumen)

Detalle completo en `seed.sql`. Campos clave:

- `fb_post_id` → UNIQUE, evita duplicados si Facebook reenvía el mismo post.
- `expires_at` → **nullable y editable**. Si es `null`, la oferta no expira automáticamente. Si tiene fecha, `GET /list` la filtra al pasar.
- `is_active` → para desactivación manual desde el Workflow.

`GET /list` aplica doble filtro: `is_active = 1` AND `expires_at > NOW()`. Así, si por alguna razón el Workflow no llama `deactivate`, la oferta igual deja de mostrarse al expirar.

---

## Variables de entorno

```env
MCP_API_KEY=...   # misma que usa Sofía
```

---

## Deploy en Hostinger (Docker)

Agregar el volumen al `docker-compose.yml`:

```yaml
services:
  mcp:
    volumes:
      - ./data:/app/data    
```

En `main.py`, registrar el router e inicializar la DB al arranque:

```python
from projects.sonoras.offers import router as sonoras_router
from projects.sonoras.db import init_db

init_db()
app.include_router(sonoras_router)
```

---

## Próximos pasos (fuera del MCP)

- Configurar Facebook Webhook -> GHL.
- Crear GHL Workflow con: AI Decision Maker -> GPT-OpenAI -> Webhook al MCP -> Wait -> Webhook deactivate.
- Bloque Custom HTML/JS en la Funnel page que haga `fetch` a `/sonoras/offers/list` y renderice las ofertas activas.

---

## Notas

- El módulo está aislado en `projects/sonoras/`. No comparte código con `projects/sofia/`.
- SQLite es suficiente para este caso de uso (volumen bajo de ofertas, lectura mayormente). Si crece, migración a Postgres es directa — solo cambiar`db.py`.
