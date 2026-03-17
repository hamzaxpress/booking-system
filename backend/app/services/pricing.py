"""
Freight Pricing Service
━━━━━━━━━━━━━━━━━━━━━━
Simple rule-based pricing engine.
Replace with a rate-card database table for production use.
"""

TAX_RATE = 0.18  # 18% GST

# Base rate per kg by shipment type (INR)
_BASE_RATE: dict[str, float] = {
    "standard":  40.0,
    "express":   80.0,
    "overnight": 150.0,
    "cargo":     25.0,
}

# Minimum freight per shipment type (INR)
_MIN_FREIGHT: dict[str, float] = {
    "standard":  60.0,
    "express":   120.0,
    "overnight": 250.0,
    "cargo":     200.0,
}


def calculate_freight(weight_kg: float, shipment_type: str) -> dict:
    """
    Returns a dict with:
        freight_charge  – pre-tax amount
        tax_amount      – GST
        total_amount    – freight + tax
    """
    rate       = _BASE_RATE.get(shipment_type, _BASE_RATE["standard"])
    min_charge = _MIN_FREIGHT.get(shipment_type, _MIN_FREIGHT["standard"])

    freight    = max(weight_kg * rate, min_charge)
    freight    = round(freight, 2)
    tax        = round(freight * TAX_RATE, 2)
    total      = round(freight + tax, 2)

    return {
        "freight_charge": freight,
        "tax_amount":     tax,
        "total_amount":   total,
    }
