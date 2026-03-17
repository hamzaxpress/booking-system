"""
Shipments Router — /shipments
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
POST /shipments                   → Book a new shipment  [Staff/Admin]
GET  /shipments                   → List all shipments   [Admin]
GET  /shipments/mine              → My shipments         [Staff/Admin]
GET  /shipments/{id}              → Shipment detail      [Staff/Admin]
PUT  /shipments/{id}/status       → Update status        [Staff/Admin]
GET  /shipments/statuses          → All status codes     [Staff/Admin]
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin, require_staff
from app.models.models import ShipmentStatus, User
from app.schemas.schemas import (
    MessageResponse,
    PaginatedShipments,
    ShipmentCreate,
    ShipmentOut,
    ShipmentStatusOut,
    StatusUpdateRequest,
)
from app.services import shipment as svc

router = APIRouter(prefix="/shipments", tags=["Shipments"])


@router.post(
    "",
    response_model=ShipmentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Book a new shipment",
)
def book_shipment(
    payload: ShipmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """
    Creates a shipment booking:
    - Upserts sender and receiver records by phone number
    - Generates a unique docket number (LGS + YYYYMMDD + 5-digit seq)
    - Calculates freight, GST, and total charge
    - Writes the first tracking event (BOOKED)

    Returns the full shipment object including docket number.
    """
    return svc.create_shipment(db, payload, current_user.id)


@router.get(
    "",
    response_model=PaginatedShipments,
    summary="List all shipments (Admin)",
)
def list_all_shipments(
    page:        int           = Query(1,  ge=1),
    size:        int           = Query(20, ge=1, le=100),
    status_code: Optional[str] = Query(None, description="Filter by status code e.g. IN_TRANSIT"),
    db:          Session       = Depends(get_db),
    _user:       User          = Depends(require_staff),
):
    return svc.list_shipments(db, page=page, size=size, status_code=status_code)


@router.get(
    "/mine",
    response_model=PaginatedShipments,
    summary="List shipments created by the logged-in staff member",
)
def list_my_shipments(
    page:        int           = Query(1,  ge=1),
    size:        int           = Query(20, ge=1, le=100),
    status_code: Optional[str] = Query(None),
    db:          Session       = Depends(get_db),
    current_user: User         = Depends(require_staff),
):
    return svc.list_shipments(
        db, page=page, size=size,
        status_code=status_code,
        user_id=current_user.id,
    )


@router.get(
    "/statuses",
    response_model=list[ShipmentStatusOut],
    summary="Get all shipment status codes",
)
def get_statuses(
    db: Session = Depends(get_db),
    _user: User = Depends(require_staff),
):
    """Must be defined BEFORE /{shipment_id} to avoid route shadowing."""
    return (
        db.query(ShipmentStatus)
        .order_by(ShipmentStatus.sort_order)
        .all()
    )


@router.get(
    "/{shipment_id}",
    response_model=ShipmentOut,
    summary="Get shipment detail by ID",
)
def get_shipment(
    shipment_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_staff),
):
    from app.services.shipment import _load_shipment
    return _load_shipment(db, shipment_id)


@router.put(
    "/{shipment_id}/status",
    response_model=ShipmentOut,
    summary="Update shipment status",
)
def update_status(
    shipment_id: int,
    payload:     StatusUpdateRequest,
    db:          Session = Depends(get_db),
    current_user: User   = Depends(require_staff),
):
    """
    Updates the current status of a shipment and appends a tracking event.

    Business rules:
    - Terminal statuses (DELIVERED, LOST, CANCELLED, DAMAGED) cannot be changed.
    - The `status_code` must be a valid code from the `shipment_status` table.
    - Optionally include `location`, `remarks`, and GPS coordinates.
    """
    return svc.update_shipment_status(db, shipment_id, payload, current_user.id)
