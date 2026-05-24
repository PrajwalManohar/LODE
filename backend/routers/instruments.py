from fastapi import APIRouter

from vein.db.database import get_instrument, get_instruments, get_maintenance_logs

router = APIRouter()


@router.get("")
def list_instruments():
    return get_instruments()


@router.get("/{instrument_id}")
def get_one(instrument_id: str):
    inst = get_instrument(instrument_id)
    if not inst:
        from fastapi import HTTPException
        raise HTTPException(404, "Instrument not found")
    inst["maintenance"] = get_maintenance_logs(instrument_id)
    return inst
