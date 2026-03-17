from sqlalchemy import (
    CheckConstraint, Column, Float, ForeignKey,
    Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    full_name       = Column(String(100), nullable=False)
    email           = Column(String(255), nullable=False, unique=True, index=True)
    hashed_password = Column(Text, nullable=False)
    role            = Column(String(10), nullable=False, default="staff")
    is_active       = Column(Integer, nullable=False, default=1)
    created_at      = Column(String, nullable=False, default="datetime('now')")
    updated_at      = Column(String, nullable=False, default="datetime('now')")

    __table_args__ = (
        CheckConstraint("role IN ('admin','staff')", name="ck_users_role"),
        CheckConstraint("is_active IN (0,1)",        name="ck_users_active"),
    )

    shipments_created = relationship("Shipment", back_populates="creator",
                                     foreign_keys="Shipment.created_by")
    tracking_updates  = relationship("TrackingHistory", back_populates="updater")


class Customer(Base):
    __tablename__ = "customers"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    full_name    = Column(String(100), nullable=False)
    email        = Column(String(255), unique=True)
    phone        = Column(String(20), nullable=False, index=True)
    address_line = Column(Text, nullable=False)
    city         = Column(String(100), nullable=False)
    state        = Column(String(100), nullable=False)
    pincode      = Column(String(10), nullable=False)
    country      = Column(String(50), nullable=False, default="India")
    created_at   = Column(String, nullable=False, default="datetime('now')")
    updated_at   = Column(String, nullable=False, default="datetime('now')")

    shipments_sent = relationship("Shipment", back_populates="sender",
                                  foreign_keys="Shipment.sender_id")


class Receiver(Base):
    __tablename__ = "receivers"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    full_name    = Column(String(100), nullable=False)
    email        = Column(String(255))
    phone        = Column(String(20), nullable=False, index=True)
    address_line = Column(Text, nullable=False)
    city         = Column(String(100), nullable=False)
    state        = Column(String(100), nullable=False)
    pincode      = Column(String(10), nullable=False)
    country      = Column(String(50), nullable=False, default="India")
    created_at   = Column(String, nullable=False, default="datetime('now')")
    updated_at   = Column(String, nullable=False, default="datetime('now')")

    shipments_received = relationship("Shipment", back_populates="receiver",
                                      foreign_keys="Shipment.receiver_id")


class ShipmentStatus(Base):
    __tablename__ = "shipment_status"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    code        = Column(String(30), nullable=False, unique=True)
    label       = Column(String(100), nullable=False)
    description = Column(Text)
    color_hex   = Column(String(10), default="#64748B")
    is_terminal = Column(Integer, nullable=False, default=0)
    sort_order  = Column(Integer, nullable=False, default=0)

    shipments = relationship("Shipment", back_populates="status")
    history   = relationship("TrackingHistory", back_populates="status")


class DocketCounter(Base):
    """
    Single-row counter table — used inside a transaction to
    guarantee unique, sequential docket numbers per date.
    """
    __tablename__ = "docket_counter"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    date_key     = Column(String(8), nullable=False, unique=True)  # YYYYMMDD
    last_seq     = Column(Integer, nullable=False, default=0)

    __table_args__ = (UniqueConstraint("date_key", name="uq_docket_date"),)


class Shipment(Base):
    __tablename__ = "shipments"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    docket_number   = Column(String(30), nullable=False, unique=True, index=True)
    sender_id       = Column(Integer, ForeignKey("customers.id",    ondelete="RESTRICT"), nullable=False)
    receiver_id     = Column(Integer, ForeignKey("receivers.id",    ondelete="RESTRICT"), nullable=False)
    status_id       = Column(Integer, ForeignKey("shipment_status.id", ondelete="RESTRICT"), nullable=False)
    created_by      = Column(Integer, ForeignKey("users.id",        ondelete="RESTRICT"), nullable=False)

    weight_kg       = Column(Float, nullable=False)
    dimensions_cm   = Column(String(30))
    shipment_type   = Column(String(20), nullable=False, default="standard")
    contents_desc   = Column(Text)
    declared_value  = Column(Float, default=0.0)

    freight_charge  = Column(Float, nullable=False, default=0.0)
    tax_amount      = Column(Float, nullable=False, default=0.0)
    total_amount    = Column(Float, nullable=False, default=0.0)

    booking_date        = Column(String, nullable=False)
    estimated_delivery  = Column(String)
    actual_delivery     = Column(String)

    origin_hub      = Column(String(100))
    destination_hub = Column(String(100))
    special_instructions = Column(Text)

    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "shipment_type IN ('standard','express','overnight','cargo')",
            name="ck_shipment_type",
        ),
    )

    sender   = relationship("Customer",       back_populates="shipments_sent",     foreign_keys=[sender_id])
    receiver = relationship("Receiver",       back_populates="shipments_received", foreign_keys=[receiver_id])
    status   = relationship("ShipmentStatus", back_populates="shipments")
    creator  = relationship("User",           back_populates="shipments_created",  foreign_keys=[created_by])
    history  = relationship("TrackingHistory", back_populates="shipment",
                            order_by="TrackingHistory.event_time")


class TrackingHistory(Base):
    __tablename__ = "tracking_history"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    shipment_id = Column(Integer, ForeignKey("shipments.id", ondelete="CASCADE"),  nullable=False, index=True)
    status_id   = Column(Integer, ForeignKey("shipment_status.id", ondelete="RESTRICT"), nullable=False)
    updated_by  = Column(Integer, ForeignKey("users.id",    ondelete="RESTRICT"),  nullable=False)

    location    = Column(String(200))
    remarks     = Column(Text)
    latitude    = Column(Float)
    longitude   = Column(Float)
    event_time  = Column(String, nullable=False, index=True)

    shipment = relationship("Shipment",       back_populates="history")
    status   = relationship("ShipmentStatus", back_populates="history")
    updater  = relationship("User",           back_populates="tracking_updates")
