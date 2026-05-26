from fastapi import APIRouter

from vein.db.database import get_bookings, get_lab_day_bookings, get_utilization

router = APIRouter()


@router.get("")
def list_bookings(instrument_id: str | None = None, email: str | None = None):
    """All bookings, or — when `email` is supplied — only that researcher's.

    The frontend passes `email` for non-admin users so they only ever see their
    own bookings; admins call without it to see the whole facility.
    """
    return get_bookings(instrument_id, email=email)


@router.get("/lab-day")
def lab_day(email: str):
    """Today's bookings at the labs where this user has a booking (lab-mate
    awareness), without exposing the full facility schedule."""
    return get_lab_day_bookings(email)


@router.get("/utilization")
def utilization():
    return get_utilization()
