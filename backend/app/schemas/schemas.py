from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, field_validator


# ══════════════════════════════════════════════════════════════════════════════
# AUTH
# ══════════════════════════════════════════════════════════════════════════════

class LoginRequest(BaseModel):
    email:    EmailStr
    password: str = Field(..., min_length=6)


class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user_id:      int
    full_name:    str
    role:         str


class UserOut(BaseModel):
    id:        int
    full_name: str
    email:     str
    role:      str
    is_active: int

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email:     EmailStr
    password:  str = Field(..., min_length=6)
    role:      str = Field(default="staff")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ("admin", "staff"):
            raise ValueError("role must be 'admin' or 'staff'")
        return v


# ══════════════════════════════════════════════════════════════════════════════
# CUSTOMER (Sender)
# ══════════════════════════════════════════════════════════════════════════════

class CustomerBase(BaseModel):
    full_name:    str = Field(..., min_length=2, max_length=100)
    email:        Optional[str] = None
    phone:        str = Field(..., min_length=10, max_length=15)
    address_line: str
    city:         str
    state:        str
    pincode:      str = Field(..., min_length=6, max_length=10)
    country:      str = "India"


class CustomerCreate(CustomerBase):
    pass


class CustomerOut(CustomerBase):
    id: int
    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════════════════════
# RECEIVER
# ══════════════════════════════════════════════════════════════════════════════

class ReceiverBase(BaseModel):
    full_name:    str = Field(..., min_length=2, max_length=100)
    email:        Optional[str] = None
    phone:        str = Field(..., min_length=10, max_length=15)
    address_line: str
    city:         str
    state:        str
    pincode:      str = Field(..., min_length=6, max_length=10)
    country:      str = "India"


class ReceiverCreate(ReceiverBase):
    pass


class ReceiverOut(ReceiverBase):
    id: int
    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════════════════════
# SHIPMENT STATUS
# ══════════════════════════════════════════════════════════════════════════════

class ShipmentStatusOut(BaseModel):
    id:          int
    code:        str
    label:       str
    description: Optional[str]
    color_hex:   str
    is_terminal: int
    sort_order:  int

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════════════════════
# SHIPMENT
# ══════════════════════════════════════════════════════════════════════════════

class ShipmentCreate(BaseModel):
    # Inline sender & receiver — service will upsert by phone
    sender:   CustomerCreate
    receiver: ReceiverCreate

    weight_kg:    float  = Field(..., gt=0)
    dimensions_cm: Optional[str] = None
    shipment_type: str   = Field(default="standard")
    contents_desc: Optional[str] = None
    declared_value: float = 0.0

    origin_hub:      Optional[str] = None
    destination_hub: Optional[str] = None
    special_instructions: Optional[str] = None

    @field_validator("shipment_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        valid = {"standard", "express", "overnight", "cargo"}
        if v not in valid:
            raise ValueError(f"shipment_type must be one of {valid}")
        return v


class StatusUpdateRequest(BaseModel):
    status_code: str = Field(..., description="Code from shipment_status table e.g. IN_TRANSIT")
    location:    Optional[str] = None
    remarks:     Optional[str] = None
    latitude:    Optional[float] = None
    longitude:   Optional[float] = None


class TrackingEventOut(BaseModel):
    id:         int
    status:     ShipmentStatusOut
    location:   Optional[str]
    remarks:    Optional[str]
    event_time: str

    model_config = {"from_attributes": True}


class ShipmentOut(BaseModel):
    id:             int
    docket_number:  str
    sender:         CustomerOut
    receiver:       ReceiverOut
    status:         ShipmentStatusOut
    creator:        Optional[UserOut] = None
    weight_kg:      float
    dimensions_cm:  Optional[str]
    shipment_type:  str
    contents_desc:  Optional[str]
    declared_value: float
    freight_charge: float
    tax_amount:     float
    total_amount:   float
    booking_date:   str
    estimated_delivery: Optional[str]
    actual_delivery:    Optional[str]
    origin_hub:      Optional[str]
    destination_hub: Optional[str]
    special_instructions: Optional[str]
    created_at:     str

    model_config = {"from_attributes": True}


class TrackingResponse(BaseModel):
    docket_number:  str
    current_status: ShipmentStatusOut
    sender_city:    str
    receiver_city:  str
    shipment_type:  str
    booking_date:   str
    estimated_delivery: Optional[str]
    actual_delivery:    Optional[str]
    history:        List[TrackingEventOut]

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════════════════════
# GENERIC
# ══════════════════════════════════════════════════════════════════════════════

class MessageResponse(BaseModel):
    message: str
    detail:  Optional[str] = None


class PaginatedShipments(BaseModel):
    total:  int
    page:   int
    size:   int
    items:  List[ShipmentOut]
