import logging
import os
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.server import TransportSecuritySettings

from app.clients.sofia.slots import get_available_slots as _get_slots
from app.clients.sofia.booking import book_appointment as _book_appointment
from app.clients.sonoras.offers import _create as _sonoras_create
from app.clients.sonoras.offers import _list as _sonoras_list
from app.clients.sonoras.offers import _deactivate as _sonoras_deactivate
from app.utils.datetime_parser import parse_natural_datetime
from app.utils.lock import SlotAlreadyBookedError
from app.utils.fb_cache import get_image as _get_cached_fb_image
from app.clients.sonoras.media import list_media as _list_media
from app.clients.auditoria.seo import audit_seo as _audit_seo
from app.clients.auditoria.health import check_site as _check_site
from app.clients.validacion.agent import validate_niche as _validate_niche
from app.config import VAULT_PATH

os.makedirs("/tmp/ghl_locks", exist_ok=True)
try:
    os.chmod("/tmp/ghl_locks", 0o777)
except PermissionError:
    pass

log = logging.getLogger(__name__)

mcp = FastMCP(
    "GHL Calendar",
    stateless_http=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


@mcp.tool(name="get_available_slots", description=(
    "Consulta disponibilidad real del calendario de GHL y devuelve hasta 3 horarios "
    "disponibles distribuidos en diferentes dias, basado en texto natural en espanol. "
    "Usar cuando el lead exprese intencion de agendar."
))
async def mcp_get_available_slots(natural_text: str, max_slots: int = 3) -> dict:
    log.info(f"MCP get_available_slots | input: '{natural_text}'")

    parsed = parse_natural_datetime(natural_text)

    if parsed.get("no_slots_message"):
        return {
            "slots": [],
            "parsed_description": parsed["parsed_description"],
            "count": 0,
            "confirmation_prompt": parsed["no_slots_message"],
        }

    slots = await _get_slots(
        start_dt=parsed["start"],
        end_dt=parsed["end"],
        hour_start=parsed["hour_start"],
        hour_end=parsed["hour_end"],
        max_slots=max_slots,
    )

    if not slots:
        return {
            "slots": [],
            "parsed_description": parsed["parsed_description"],
            "count": 0,
            "confirmation_prompt": (
                "No encontre disponibilidad para esa fecha. "
                "¿Tienes otra preferencia de dia u horario?"
            ),
        }

    return {
        "slots": slots,
        "parsed_description": parsed["parsed_description"],
        "count": len(slots),
        "confirmation_prompt": (
            "¿Te funciona alguno de estos horarios? "
            "Dime cual y te confirmo la cita."
        ),
    }


@mcp.tool(name="book_appointment", description=(
    "Crea una cita en el calendario de GHL para el contacto dado. "
    "Llamar solo despues de que el lead haya confirmado el horario especifico."
))
async def mcp_book_appointment(
    contact_id: str,
    start_iso: str,
    end_iso: str,
    title: str = "Auditoria Gratuita - Restaurante",
) -> dict:
    log.info(f"MCP book_appointment | contact: {contact_id} | slot: {start_iso}")

    try:
        return await _book_appointment(
            contact_id=contact_id,
            start_iso=start_iso,
            end_iso=end_iso,
            title=title,
        )
    except SlotAlreadyBookedError:
        return {
            "success": False,
            "message": "Ese horario acaba de ser reservado. ¿Quieres ver otros disponibles?",
        }
    except Exception as e:
        log.error(f"Error en MCP book_appointment: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Error al crear la cita: {str(e)}",
        }


@mcp.tool(name="create_sonoras_offer", description=(
    "Crea una oferta de Sonora's Carbon y Sal a partir de un post de Facebook. "
    "Llamar SOLO cuando el post haya sido identificado como una oferta o promocion. "
    "Del texto del post extraer: "
    "title (nombre corto de la oferta, ej: '2x1 en alitas'), "
    "promo_text (texto LITERAL de la promocion copiado del post, NO estas instrucciones), "
    "expires_at (ISO 8601 si el post menciona duracion o fecha limite; null si no), "
    "schedule_notes (horarios o dias en que aplica, ej: 'Lunes a jueves 6pm-10pm', "
    "'Solo fines de semana', 'Consumo minimo $300'; null si no se menciona), "
    "fb_post_id (ID del post para evitar duplicados), "
    "image_url (URL de la imagen; si no se proporciona, llamar list_sonoras_media con el titulo del platillo antes de crear; null si no hay imagen relevante o el usuario indica que no quiere imagen). "
    "Antes de crear, verificar con list_sonoras_offers si ya existe una oferta similar activa."
))
def mcp_create_sonoras_offer(
    title: str,
    fb_post_id: str,
    promo_text: str = None,
    image_url: str = None,
    expires_at: str = None,
    schedule_notes: str = None,
) -> dict:
    fb_post_id = fb_post_id or None
    if not image_url:
        image_url = _get_cached_fb_image() or ""
    log.info(f"MCP create_sonoras_offer | title: '{title}' | fb_post_id: {fb_post_id} | promo_text: {repr(promo_text)} | image_url: {repr(image_url)}")
    try:
        return _sonoras_create(
            title=title,
            fb_post_id=fb_post_id,
            description=promo_text,
            image_url=image_url,
            expires_at=expires_at,
            schedule_notes=schedule_notes,
        )
    except Exception as e:
        log.error(f"Error en MCP create_sonoras_offer: {e}", exc_info=True)
        return {"duplicate": False, "error": str(e)}


@mcp.tool(name="list_sonoras_offers", description=(
    "Devuelve las ofertas activas y vigentes de Sonora's Carbon y Sal. "
    "Usar antes de crear una oferta nueva para verificar si ya existe una similar activa. "
    "Tambien util para confirmar que una oferta fue creada correctamente."
))
def mcp_list_sonoras_offers() -> dict:
    log.info("MCP list_sonoras_offers")
    try:
        offers = _sonoras_list()
        return {"offers": offers, "count": len(offers)}
    except Exception as e:
        log.error(f"Error en MCP list_sonoras_offers: {e}", exc_info=True)
        return {"offers": [], "count": 0, "error": str(e)}


@mcp.tool(name="deactivate_sonoras_offer", description=(
    "Desactiva una oferta de Sonora's por su ID. "
    "Llamar cuando la oferta haya expirado o el restaurante indique que ya no aplica. "
    "El ID lo devuelve create_sonoras_offer al momento de crear la oferta."
))
def mcp_deactivate_sonoras_offer(offer_id: int) -> dict:
    log.info(f"MCP deactivate_sonoras_offer | id: {offer_id}")
    try:
        if not _sonoras_deactivate(offer_id):
            return {"deactivated": False, "error": f"Oferta {offer_id} no encontrada"}
        return {"id": offer_id, "deactivated": True}
    except Exception as e:
        log.error(f"Error en MCP deactivate_sonoras_offer: {e}", exc_info=True)
        return {"deactivated": False, "error": str(e)}


@mcp.tool(name="read_vault_file", description=(
    "Lee un archivo .md del vault de DDTIA y devuelve su contenido. "
    "Usar para consultar contexto de clientes, pendientes, ADRs, infra, etc. "
    "Ejemplo de path: 'clientes/sonoras/CONTEXT.md'"
))
def mcp_read_vault_file(path: str) -> dict:
    import os as _os
    full_path = _os.path.join(VAULT_PATH, path)
    if not _os.path.realpath(full_path).startswith(_os.path.realpath(VAULT_PATH)):
        return {"error": "Acceso denegado"}
    if not full_path.endswith(".md"):
        return {"error": "Solo archivos .md"}
    log.info(f"MCP read_vault_file | path: {path}")
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            return {"path": path, "content": f.read()}
    except FileNotFoundError:
        return {"error": f"Archivo no encontrado: {path}"}
    except Exception as e:
        log.error(f"Error en MCP read_vault_file: {e}", exc_info=True)
        return {"error": str(e)}


@mcp.tool(name="audit_seo", description=(
    "Audita el SEO on-page de una URL de un sitio de cliente y devuelve un score 0-100 "
    "con la lista de problemas. Revisa title, meta description, H1, indexabilidad, lang, "
    "canonical, viewport, Open Graph, datos estructurados (JSON-LD), alt de imagenes, "
    "HTTPS, robots.txt, sitemap.xml y el certificado TLS. "
    "Usar cuando el usuario pida auditar, analizar o revisar el SEO de un sitio."
))
async def mcp_audit_seo(url: str) -> dict:
    log.info(f"MCP audit_seo | url: {url}")
    try:
        return await _audit_seo(url)
    except Exception as e:
        log.error(f"Error en MCP audit_seo: {e}", exc_info=True)
        return {"url": url, "error": str(e)}


@mcp.tool(name="health_check_site", description=(
    "Verifica si un sitio esta arriba: codigo de estado HTTP, tiempo de respuesta, "
    "redirecciones y estado del certificado TLS (dias para expirar). "
    "Usar cuando el usuario pregunte si un sitio esta caido, lento, o por el estado del "
    "certificado/SSL de un cliente."
))
async def mcp_health_check_site(url: str) -> dict:
    log.info(f"MCP health_check_site | url: {url}")
    try:
        return await _check_site(url)
    except Exception as e:
        log.error(f"Error en MCP health_check_site: {e}", exc_info=True)
        return {"url": url, "up": False, "error": str(e)}


@mcp.tool(name="validar_nicho", description=(
    "Valida un nicho o idea de negocio midiendo señales reales de demanda en Hacker News, "
    "Reddit, YouTube y Google Trends. Devuelve un score 1-10 y una decision (aprobado si >=7). "
    "Usar cuando el usuario pida validar, evaluar o medir el mercado/demanda de una idea o nicho. "
    "Opcional: geo (ciudad/region) para acotar. Nota: Reddit/YouTube/Trends solo aportan al "
    "score si tienen credenciales configuradas; el resultado se re-normaliza sobre las fuentes "
    "disponibles."
))
async def mcp_validar_nicho(niche: str, geo: str = None) -> dict:
    log.info(f"MCP validar_nicho | niche: '{niche}' | geo: {geo}")
    try:
        return await _validate_niche(niche, geo=geo)
    except Exception as e:
        log.error(f"Error en MCP validar_nicho: {e}", exc_info=True)
        return {"error": str(e)}


@mcp.tool(name="list_sonoras_media", description=(
    "Busca imagenes en el banco de fotos de Sonora's Carbon y Sal (almacenadas en GHL). "
    "Usar ANTES de crear una oferta si el usuario no proporciono imagen y el titulo menciona "
    "un platillo especifico (rib eye, hamburguesa, ensalada, etc.). "
    "Pasar query con el nombre del platillo en espanol para filtrar. "
    "Si no hay matches o query es vacio -> devuelve lista vacia -> NO insistir con imagen. "
    "Flujo de respuesta al usuario: "
    "1) Si hay matches: mostrar lista con nombre de cada foto y preguntar cual usar. "
    "2) Si el usuario dice 'ninguna' o 'no pongas imagen' -> crear oferta sin imagen. "
    "3) Si el usuario dice 'aleatoria' o 'pon cualquiera' -> usar la primera de la lista. "
    "NUNCA buscar imagen en internet si el usuario no lo pide explicitamente."
))
async def mcp_list_sonoras_media(query: str = "") -> dict:
    log.info(f"MCP list_sonoras_media | query: '{query}'")
    try:
        q = query.strip() or None
        images = await _list_media(query=q)
        return {
            "images": images,
            "count": len(images),
            "query": query,
        }
    except Exception as e:
        log.error(f"Error en MCP list_sonoras_media: {e}", exc_info=True)
        return {"images": [], "count": 0, "error": str(e)}
