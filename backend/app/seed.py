"""
Database Seeder
━━━━━━━━━━━━━━
Run once to initialise tables and seed essential data:
  • All shipment_status rows
  • Default admin user  (admin@logistics.com / Admin@123)
  • Default staff user  (staff@logistics.com / Staff@123)

Usage:
    python -m app.seed
"""

from app.database import engine, SessionLocal
from app.models.models import Base, DocketCounter, ShipmentStatus, User
from app.core.security import hash_password


def seed():
    # 1 — Create all tables
    Base.metadata.create_all(bind=engine)
    print("✓ Tables created.")

    db = SessionLocal()
    try:
        # 2 — Seed shipment statuses
        statuses = [
            dict(code="BOOKED",             label="Booked",               description="Shipment booked, docket generated",              color_hex="#3B82F6", is_terminal=0, sort_order=1),
            dict(code="PICKUP_SCHEDULED",   label="Pickup Scheduled",     description="Pickup assigned to delivery agent",              color_hex="#8B5CF6", is_terminal=0, sort_order=2),
            dict(code="PICKED_UP",          label="Picked Up",            description="Package collected from sender",                  color_hex="#F59E0B", is_terminal=0, sort_order=3),
            dict(code="AT_ORIGIN_HUB",      label="At Origin Hub",        description="Package arrived at origin sorting hub",          color_hex="#F97316", is_terminal=0, sort_order=4),
            dict(code="IN_TRANSIT",         label="In Transit",           description="Package on the way between hubs",                color_hex="#06B6D4", is_terminal=0, sort_order=5),
            dict(code="AT_DESTINATION_HUB", label="At Destination Hub",   description="Package arrived at destination city hub",        color_hex="#6366F1", is_terminal=0, sort_order=6),
            dict(code="OUT_FOR_DELIVERY",   label="Out for Delivery",     description="Package dispatched for final delivery",          color_hex="#10B981", is_terminal=0, sort_order=7),
            dict(code="DELIVERED",          label="Delivered",            description="Package successfully delivered",                 color_hex="#22C55E", is_terminal=1, sort_order=8),
            dict(code="DELIVERY_ATTEMPTED", label="Delivery Attempted",   description="Delivery attempted, receiver unavailable",       color_hex="#EAB308", is_terminal=0, sort_order=9),
            dict(code="RETURNED_TO_HUB",    label="Returned to Hub",      description="Package returned after failed delivery",         color_hex="#F87171", is_terminal=0, sort_order=10),
            dict(code="LOST",               label="Lost",                 description="Package reported as lost",                      color_hex="#EF4444", is_terminal=1, sort_order=11),
            dict(code="CANCELLED",          label="Cancelled",            description="Shipment cancelled before pickup",              color_hex="#94A3B8", is_terminal=1, sort_order=12),
            dict(code="DAMAGED",            label="Damaged",              description="Package damaged during transit",                 color_hex="#DC2626", is_terminal=1, sort_order=13),
        ]

        added = 0
        for s in statuses:
            exists = db.query(ShipmentStatus).filter_by(code=s["code"]).first()
            if not exists:
                db.add(ShipmentStatus(**s))
                added += 1
        db.commit()
        print(f"✓ {added} shipment statuses seeded.")

        # 3 — Seed users
        users = [
            dict(full_name="System Admin", email="admin@logistics.com",
                 password="Admin@123", role="admin"),
            dict(full_name="Demo Staff",   email="staff@logistics.com",
                 password="Staff@123", role="staff"),
        ]
        for u in users:
            exists = db.query(User).filter_by(email=u["email"]).first()
            if not exists:
                db.add(User(
                    full_name       = u["full_name"],
                    email           = u["email"],
                    hashed_password = hash_password(u["password"]),
                    role            = u["role"],
                    created_at      = "2026-03-12 00:00:00",
                    updated_at      = "2026-03-12 00:00:00",
                ))
        db.commit()
        print("✓ Default users seeded.")
        print()
        print("  Admin  → admin@logistics.com  / Admin@123")
        print("  Staff  → staff@logistics.com  / Staff@123")
        print()
        print("✓ Database ready. Run: uvicorn app.main:app --reload")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
