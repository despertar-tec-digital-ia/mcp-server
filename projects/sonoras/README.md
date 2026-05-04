# Sonora's Carbón y Sal — Módulo de Ofertas

Automatización del ciclo: **Facebook → GHL → AI Agent (MCP) → Página web**.

Cuando el restaurante publica una oferta en Facebook, el agente la analiza, determina si es una oferta, y la registra automáticamente. Se desactiva sola al expirar o cuando el agente lo indique.

---

## Flujo

1. Sonora's publica un post en su página de Facebook.
2. **GHL Workflow** se dispara con el Facebook trigger.
3. **AI Agent** recibe el post, lo analiza y decide si es una oferta.
4. Si es oferta, el agente extrae título, descripción, imagen, horarios y fecha de vigencia.
5. El agente llama `create_sonoras_offer` → guarda en SQLite.
6. **Funnel page** hace `fetch` a `/sonoras/offers/list` y renderiza dinámicamente.
7. Al expirar, el agente llama `deactivate_sonoras_offer`.

---

## Estructura

```
projects/sonoras/
├── __init__.py
├── offers.py       # lógica de DB usada por los MCP tools
├── db.py          # conexión SQLite + init
├── seed.sql        # schema de la tabla offers
└── README.md

data/
└── sonoras.db      # archivo SQLite — montado como volumen Docker
```

---

## MCP Tools

| Tool | Auth | Quién lo llama |
|---|---|---|
| `create_sonoras_offer` | `x-api-key` | AI Agent |
| `list_sonoras_offers` | `x-api-key` | AI Agent |
| `deactivate_sonoras_offer` | `x-api-key` | AI Agent |

`list_sonoras_offers` también es usado por el agente para verificar duplicados antes de crear.

---

## Schema (resumen)

Detalle completo en `seed.sql`. Campos clave:

- `fb_post_id` → UNIQUE, evita duplicados si Facebook reenvía el mismo post.
- `expires_at` → nullable. Si tiene fecha, `list_sonoras_offers` la filtra al pasar.
- `schedule_notes` → horarios o días en que aplica la oferta.
- `is_active` → para desactivación por el agente.

`list_sonoras_offers` aplica doble filtro: `is_active = 1` AND `expires_at > NOW()`.

---

## Variables de entorno

```env
MCP_API_KEY=...   # misma que usa Sofía
```

---

## Deploy en Hostinger (Docker)

Volumen en `docker-compose.yml`:

```yaml
services:
  ghl-mcp:
    volumes:
      - ./data:/app/data
```

`init_db()` corre automáticamente al arrancar el servidor desde el lifespan de FastAPI.

---

## Próximos pasos

- Configurar Facebook Webhook → GHL.
- Crear GHL Workflow con AI Agent conectado al MCP.
- Bloque HTML/JS en la Funnel page que consuma `list_sonoras_offers` y renderice las ofertas activas.
- Agregar tools MCP para reservaciones en el restaurante.

---

## Notas

- El módulo está aislado en `projects/sonoras/`. No comparte código con `projects/sofia/`.
- SQLite es suficiente para este caso de uso. Si crece, migración a Postgres es directa — solo cambia `db.py`.
