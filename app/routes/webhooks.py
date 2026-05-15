import logging
import os
import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from app.utils.fb_cache import set_image as _cache_fb_image

log = logging.getLogger(__name__)
router = APIRouter()


async def _fetch_fb_image(post_id: str) -> str:
    """Intenta obtener full_picture del post via Graph API. Retorna '' si falla."""
    token = os.getenv("FB_PAGE_ACCESS_TOKEN", "")
    if not token or not post_id:
        return ""
    try:
        url = f"https://graph.facebook.com/v25.0/{post_id}"
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(url, params={"fields": "full_picture", "access_token": token})
            if resp.status_code == 200:
                return resp.json().get("full_picture", "")
    except Exception as e:
        log.warning(f"No se pudo obtener imagen de FB: {e}")
    return ""


@router.get("/webhooks/facebook/verify")
async def facebook_webhook_verify(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    if hub_verify_token != "sonoras2026":
        raise HTTPException(status_code=403, detail="Forbidden")
    return Response(content=hub_challenge, media_type="text/plain")


@router.get("/webhooks/facebook")
async def facebook_webhook_verify_alt(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    if hub_verify_token != "sonoras2026":
        raise HTTPException(status_code=403, detail="Forbidden")
    return Response(content=hub_challenge, media_type="text/plain")


@router.post("/webhooks/facebook")
async def facebook_webhook(request: Request):
    payload = await request.json()
    log.info(f"Facebook webhook received: {payload}")

    value = (
        payload.get("entry", [{}])[0]
        .get("changes", [{}])[0]
        .get("value", {})
    )
    post_text = value.get("message", "")
    post_id = value.get("post_id", "")

    image_url = await _fetch_fb_image(post_id)
    log.info(f"FB post_id: {post_id} | image_url: {image_url or '(none)'}")
    _cache_fb_image(image_url)

    ghl_url = "".join(os.getenv("GHL_INBOUND_WEBHOOK_URL", "").split())
    if not ghl_url:
        log.error("GHL_INBOUND_WEBHOOK_URL not set")
        raise HTTPException(status_code=500, detail="GHL webhook URL not configured")

    ghl_payload = {
        "facebook_post_text": post_text,
        "fb_image_url": image_url,
        "email": "posts@sonoras.local",
        "phone": "+52-sonoras",
        "firstName": "Sonoras Bot",
    }

    import json as _json
    print("=== PAYLOAD ENVIADO A GHL ===")
    print(_json.dumps(ghl_payload, indent=2, ensure_ascii=False))
    print("==============================")

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(ghl_url, json=ghl_payload)
        log.info(f"GHL response: {resp.status_code} {resp.text}")
        resp.raise_for_status()

    return {"success": True}
