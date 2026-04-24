from config import GHL_API_KEY, GHL_LOCATION_ID

def get_headers() -> dict:
    """
    GHL usa Bearer token en todas las llamadas.
    El token viene de una Private Integration en tu cuenta.
    """
    return {
        "Authorization": f"Bearer {GHL_API_KEY}",
        "Content-Type": "application/json",
        "Version": "2021-04-15",
    }

def get_location_id() -> str:
    return GHL_LOCATION_ID
