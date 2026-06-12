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
