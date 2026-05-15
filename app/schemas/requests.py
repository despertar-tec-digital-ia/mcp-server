from typing import Optional
from pydantic import BaseModel


class SlotsRequest(BaseModel):
    natural_text: str
    max_slots: int = 3


class BookRequest(BaseModel):
    contact_id: str
    start_iso: str
    end_iso: str
    title: str = "Auditoria Gratuita - Restaurante"


class OfferCreate(BaseModel):
    title: str
    fb_post_id: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    expires_at: Optional[str] = None
    schedule_notes: Optional[str] = None
