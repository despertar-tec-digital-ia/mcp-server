# ddtia-mcp-server — Claude Code Instructions

## Qué es este repo
MCP server principal de DDTIA. Expone tools vía MCP (FastMCP) y REST
para los agentes de GHL Agent Studio. Actualmente sirve a dos clientes:
Sofía (agendamiento) y Sonoras Carbón y Sal (ofertas). Cada cliente
vive en app/clients/{cliente}/. A futuro cada cliente tendrá su propio
repo separado.

## Contexto del ecosistema
- MCP endpoint: POST /mcp (Streamable HTTP)
- SSE fallback: GET /sse
- REST tools: POST /tools/* (auth: x-api-key header)
- Webhooks: POST /webhooks/facebook (Sonoras)
- Base de datos: SQLite por cliente en /data/
- Depende de: GHL API (calendarios), Meta Graph API (imágenes FB)

## Stack
Python 3.12, FastAPI, FastMCP, httpx, SQLite, Docker

## Comandos esenciales
```bash
# Arrancar en local
docker compose up --build

# Tests
pytest

# Logs
docker compose logs -f
```

## Estructura de carpetas
app/
├── main.py          → solo orquestación (lifespan, middleware, mounts)
├── routes/          → endpoints HTTP por dominio
├── mcp/             → FastMCP server y tools registrados
├── clients/         → lógica de negocio por cliente (sin HTTP)
├── schemas/         → Pydantic models compartidos
└── utils/           → helpers sin dependencias de negocio

## Convenciones
- Idioma del código: inglés
- Comentarios técnicos: inglés
- Commits: conventional commits (feat:, fix:, docs:, chore:)
- Rama de trabajo: dev — nunca push directo a main
- Tests: obligatorios para lógica de negocio

## Reglas de git para Claude Code
- NO hacer commit sin confirmación explícita
- NO push a main directamente
- Presentar diff antes de cualquier cambio destructivo

## Lo que NO tocar
- .env (nunca leer ni modificar)
- data/sonoras.db
- docker-compose.yml (salvo que se pida explícitamente)
