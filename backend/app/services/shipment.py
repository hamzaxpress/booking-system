"""
Shipment Service
━━━━━━━━━━━━━━━
All business logic for creating, listing, and updating shipments.
Routers stay thin — they only validate input and delegate here.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.models.models import (
    Customer, DocketCounter, Receiver,
    Shipment, ShipmentStatus, TrackingHistory,
)
from app.schemas.schemas import ShipmentCreate, StatusUpdateRequest
from app.services.docket import generate_docket
from app.services.pricing import calculate_freight


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _estimated_delivery(shipment_type: str) -> str:
    days = {"standard": 5, "express": 2, "overnight": 1, "cargo": 7}
    delta = timedelta(days=days.get(shipment_type, 5))
    return (datetime.now(timezone.utc) + delta).strftime("%Y-%m-%d")


def _get_status_by_code(db: Session, code: str) -> ShipmentStatus:
    st = db.query(ShipmentStatus).filter(ShipmentStatus.code == code).first()
    if not st:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Status code '{code}' not found.",
        )
    return st


def _parse_dt_utc(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def should_redact_public(shipment: Shipment) -> bool:
    """Public tracking redaction rule: only after delivered + retention window."""
    if not shipment.actual_delivery or not shipment.status:
        return False
    if shipment.status.code != "DELIVERED":
        return False

    delivered_at = _parse_dt_utc(shipment.actual_delivery)
    if not delivered_at:
        return False

    now = datetime.now(timezone.utc)
    return (now - delivered_at) >= timedelta(minutes=settings.RETENTION_MINUTES)


def _upsert_customer(db: Session, data) -> Customer:
    """Find existing customer by phone or create a new one."""
    customer = db.query(Customer).filter(Customer.phone == data.phone).first()
    if not customer:
        customer = Customer(**data.model_dump())
        db.add(customer)
        db.flush()
    return customer


def _upsert_receiver(db: Session, data) -> Receiver:
    """Find existing receiver by phone or create a new one."""
    receiver = db.query(Receiver).filter(Receiver.phone == data.phone).first()
    if not receiver:
        receiver = Receiver(**data.model_dump())
        db.add(receiver)
        db.flush()
    return receiver


def _load_shipment(db: Session, shipment_id: int) -> Shipment:
    shipment = (
        db.query(Shipment)
        .options(
            joinedload(Shipment.sender),
            joinedload(Shipment.receiver),
            joinedload(Shipment.status),
            joinedload(Shipment.creator),
            joinedload(Shipment.history).joinedload(TrackingHistory.status),
        )
        .filter(Shipment.id == shipment_id)
        .first()
    )
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found.")
    return shipment


# ── Public API ────────────────────────────────────────────────────────────────

def create_shipment(db: Session, payload: ShipmentCreate, current_user_id: int) -> Shipment:
    """
    Book a new shipment atomically.

    Transaction flow:
      1. Upsert sender (customer) by phone number
      2. Upsert receiver by phone number
      3. Atomically allocate next docket number (via DocketCounter)
      4. Calculate freight + GST
      5. Persist Shipment row
      6. Write first TrackingHistory event (BOOKED)
      7. Commit — all or nothing
    """
    try:
        # 1 & 2 — resolve parties
        sender   = _upsert_customer(db, payload.sender)
        receiver = _upsert_receiver(db, payload.receiver)

        # 3 — docket (atomic, inside same transaction)
        docket_no = generate_docket(db)

        # 4 — pricing
        pricing = calculate_freight(payload.weight_kg, payload.shipment_type)

        # 5 — initial status
        booked_status = _get_status_by_code(db, "BOOKED")

        now = _now_str()

        # 6 — create shipment record
        shipment = Shipment(
            docket_number   = docket_no,
            sender_id       = sender.id,
            receiver_id     = receiver.id,
            status_id       = booked_status.id,
            created_by      = current_user_id,
            weight_kg       = payload.weight_kg,
            dimensions_cm   = payload.dimensions_cm,
            shipment_type   = payload.shipment_type,
            contents_desc   = payload.contents_desc,
            declared_value  = payload.declared_value,
            freight_charge  = pricing["freight_charge"],
            tax_amount      = pricing["tax_amount"],
            total_amount    = pricing["total_amount"],
            booking_date    = now,
            estimated_delivery = _estimated_delivery(payload.shipment_type),
            origin_hub      = payload.origin_hub,
            destination_hub = payload.destination_hub,
            special_instructions = payload.special_instructions,
            created_at      = now,
            updated_at      = now,
        )
        db.add(shipment)
        db.flush()  # get shipment.id before writing history

        # 7 — first tracking event
        history = TrackingHistory(
            shipment_id = shipment.id,
            status_id   = booked_status.id,
            updated_by  = current_user_id,
            location    = payload.origin_hub or "Origin Hub",
            remarks     = "Shipment booked. Docket generated.",
            event_time  = now,
        )
        db.add(history)
        db.commit()
        db.refresh(shipment)

    except Exception:
        db.rollback()
        raise

    return _load_shipment(db, shipment.id)


def list_shipments(
    db: Session,
    page: int = 1,
    size: int = 20,
    status_code: Optional[str] = None,
    user_id: Optional[int] = None,
) -> dict:
    """Paginated shipment list with optional filters."""
    query = db.query(Shipment).options(
        joinedload(Shipment.sender),
        joinedload(Shipment.receiver),
        joinedload(Shipment.status),
        joinedload(Shipment.creator),
    )

    if status_code:
        st = db.query(ShipmentStatus).filter(ShipmentStatus.code == status_code).first()
        if st:
            query = query.filter(Shipment.status_id == st.id)

    if user_id:
        query = query.filter(Shipment.created_by == user_id)

    total = query.count()
    items = (
        query
        .order_by(Shipment.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return {"total": total, "page": page, "size": size, "items": items}


def update_shipment_status(
    db: Session,
    shipment_id: int,
    payload: StatusUpdateRequest,
    current_user_id: int,
) -> Shipment:
    """
    Update shipment status and append a tracking event.

    Business rules enforced:
      • Cannot update a terminal status (DELIVERED / LOST / CANCELLED / DAMAGED).
      • New status must exist in shipment_status table.
    """
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found.")

    # Guard: current status is terminal?
    current_status = db.query(ShipmentStatus).get(shipment.status_id)
    if current_status and current_status.is_terminal:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot update a shipment with terminal status '{current_status.code}'.",
        )

    new_status = _get_status_by_code(db, payload.status_code)
    now = _now_str()

    try:
        shipment.status_id  = new_status.id
        shipment.updated_at = now

        # Mark actual_delivery timestamp
        if new_status.code == "DELIVERED":
            shipment.actual_delivery = now

        event = TrackingHistory(
            shipment_id = shipment.id,
            status_id   = new_status.id,
            updated_by  = current_user_id,
            location    = payload.location,
            remarks     = payload.remarks,
            latitude    = payload.latitude,
            longitude   = payload.longitude,
            event_time  = now,
        )
        db.add(event)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return _load_shipment(db, shipment.id)


def get_shipment_by_docket(db: Session, docket_number: str) -> Shipment:
    """Public tracking — look up by docket number."""
    shipment = (
        db.query(Shipment)
        .options(
            joinedload(Shipment.sender),
            joinedload(Shipment.receiver),
            joinedload(Shipment.status),
            joinedload(Shipment.history).joinedload(TrackingHistory.status),
        )
        .filter(Shipment.docket_number == docket_number.upper())
        .first()
    )
    if not shipment:
        raise HTTPException(
            status_code=404,
            detail=f"No shipment found for docket number '{docket_number}'.",
        )
    return shipment
