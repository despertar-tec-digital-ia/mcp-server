import os
from fastapi import Header, HTTPException
from app.config import GHL_API_KEY, GHL_LOCATION_ID


def get_headers() -> dict:
    return {
        "Authorization": f"Bearer {GHL_API_KEY}",
        "Content-Type": "application/json",
        "Version": "2021-04-15",
    }


def get_location_id() -> str:
    return GHL_LOCATION_ID


def require_api_key(x_api_key: str = Header(...)):
    if x_api_key != os.getenv("MCP_API_KEY", ""):
        raise HTTPException(status_code=401, detail="Invalid API key")
