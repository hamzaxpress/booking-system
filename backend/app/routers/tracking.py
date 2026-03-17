"""
Tracking Router — /track
━━━━━━━━━━━━━━━━━━━━━━━
GET /track/{docket_number}  → Public shipment tracking (no auth required)
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.schemas import TrackingEventOut, TrackingResponse
from app.services.shipment import get_shipment_by_docket, should_redact_public

router = APIRouter(prefix="/track", tags=["Public Tracking"])


@router.get(
    "/{docket_number}",
    response_model=TrackingResponse,
    summary="Track a shipment by docket number (public — no login required)",
)
def track_shipment(docket_number: str, db: Session = Depends(get_db)):
    """
    Public endpoint — no authentication needed.

    Accepts docket numbers in any case (e.g. lgs20260312... is normalised to LGS20260312...).
    Returns current status, sender/receiver cities, booking info, and full tracking timeline.
    """
    shipment = get_shipment_by_docket(db, docket_number)
    redact = should_redact_public(shipment)

    history = []
    for event in shipment.history:
        event_out = TrackingEventOut.model_validate(event, from_attributes=True)
        if redact:
            event_out = event_out.model_copy(update={
                "location": "REDACTED",
                "remarks": "REDACTED",
            })
        history.append(event_out)

    return TrackingResponse(
        docket_number      = shipment.docket_number,
        current_status     = shipment.status,
        sender_city        = "REDACTED" if redact else shipment.sender.city,
        receiver_city      = "REDACTED" if redact else shipment.receiver.city,
        shipment_type      = shipment.shipment_type,
        booking_date       = shipment.booking_date,
        estimated_delivery = shipment.estimated_delivery,
        actual_delivery    = shipment.actual_delivery,
        history            = history,
    )
