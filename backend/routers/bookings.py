from fastapi import APIRouter

from vein.db.database import get_bookings, get_utilization

router = APIRouter()


@router.get("")
def list_bookings(instrument_id: str | None = None):
    return get_bookings(instrument_id)


@router.get("/utilization")
def utilization():
    return get_utilization()
