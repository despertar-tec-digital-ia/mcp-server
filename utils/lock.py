import hashlib
import time
from filelock import FileLock, Timeout
from pathlib import Path

LOCK_DIR = Path("/tmp/ghl_locks")
LOCK_DIR.mkdir(exist_ok=True)

def get_slot_lock(slot_start_iso: str) -> FileLock:
    """
    Genera un lock único por horario.
    Evita que dos usuarios reserven el mismo slot al mismo tiempo.
    """
    slot_hash = hashlib.md5(slot_start_iso.encode()).hexdigest()[:10]
    lock_path = LOCK_DIR / f"slot_{slot_hash}.lock"
    return FileLock(str(lock_path), timeout=5)

class SlotAlreadyBookedError(Exception):
    pass

def acquire_slot(slot_start_iso: str):
    """
    Context manager: ocupa el slot mientras se procesa la reserva.
    Lanza SlotAlreadyBookedError si otro proceso ya lo está reservando.
    """
    lock = get_slot_lock(slot_start_iso)
    try:
        lock.acquire()
        return lock
    except Timeout:
        raise SlotAlreadyBookedError(
            f"El horario {slot_start_iso} está siendo reservado por otro usuario en este momento."
        )
