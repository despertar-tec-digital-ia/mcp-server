# ddtia-mcp-server

MCP server de DDTIA. Expone tools vía MCP (FastMCP) y REST para agentes de GHL Agent Studio.

## Clientes
- **Sofía** — Agendamiento de citas vía GHL Calendar
- **Sonoras Carbón y Sal** — Gestión de ofertas desde posts de Facebook

## Endpoints principales
| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/mcp` | MCP Streamable HTTP (configurar en GHL) |
| GET | `/sse` | SSE fallback |
| GET | `/health` | Health check |
| POST | `/tools/get_available_slots` | Slots disponibles (x-api-key) |
| POST | `/tools/book_appointment` | Crear cita (x-api-key) |
| POST | `/webhooks/facebook` | Webhook de Meta para Sonoras |
| GET | `/sonoras/offers/list` | Ofertas activas (público) |
| GET | `/panel/clients` | Lista de clientes (x-api-key) |
| POST | `/panel/onboarding` | Onboarding nuevo cliente (x-api-key) |
| GET | `/auditoria/seo?url=` | Auditoría SEO on-page de un sitio, score 0-100 (x-api-key) |
| GET | `/auditoria/health?url=` | Health-check de un sitio: up/down, latencia, cert TLS (x-api-key) |
| POST | `/validacion/run` | Valida un nicho/idea, score 1-10 + decisión (x-api-key, webhook GHL) |

## MCP tools

`get_available_slots`, `book_appointment`, `create_sonoras_offer`, `list_sonoras_offers`,
`deactivate_sonoras_offer`, `list_sonoras_media`, `read_vault_file`, `audit_seo`,
`health_check_site`, `validar_nicho`.

## Agente de Validación de Mercado (ADR-0004, Fase 1)

`app/clients/validacion/` valida nichos midiendo demanda real en Hacker News (sin clave),
Reddit, YouTube y Google Trends. El score (1-10) se re-normaliza sobre las fuentes
disponibles. Credenciales opcionales (env): `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET`,
`YOUTUBE_API_KEY`. Google Trends queda pendiente (requiere `pytrends`). La generación de
entregables (oferta/PDF/propuesta) es Fase 2.

## Cómo arrancar

```bash
cp .env.example .env
# Editar .env con tus credenciales

docker compose up --build
```

## Tests

```bash
pytest tests/ -v
```

## Stack
Python 3.12 · FastAPI · FastMCP · httpx · SQLite · Docker
