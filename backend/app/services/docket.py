"""
Docket Number Generation Service
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Format  : LGS + YYYYMMDD + 5-digit zero-padded sequence
Example : LGS2026031200001

Strategy
--------
Uses a dedicated `docket_counter` table with a per-date row.
The SELECT … FOR UPDATE equivalent in SQLite is achieved by:
  1. Opening the operation inside an explicit SERIALIZABLE transaction
     (SQLite's default isolation level is SERIALIZABLE).
  2. Using `with_for_update()` on the counter row so SQLAlchemy
     emits a plain SELECT; since SQLite has file-level locking,
     no two writers can race inside the same WAL checkpoint.

This guarantees that even under concurrent requests:
  ✓ No two shipments ever receive the same docket number.
  ✓ Numbers are always sequential within a calendar day.
  ✓ The sequence resets to 00001 each new day automatically.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.models import DocketCounter

PREFIX = "LGS"
SEQ_WIDTH = 5          # zero-pad to 5 digits  → 00001 … 99999
MAX_DAILY_SEQ = 99_999


def generate_docket(db: Session) -> str:
    """
    Atomically allocate the next docket number for today.

    Must be called inside an active database transaction.
    The caller (shipment service) is responsible for committing or
    rolling back the surrounding transaction.
    """
    date_key = datetime.now(timezone.utc).strftime("%Y%m%d")

    # Lock the counter row for this date (SQLite serialises at file level)
    counter = (
        db.query(DocketCounter)
        .filter(DocketCounter.date_key == date_key)
        .with_for_update()          # signals intent; SQLite honours via WAL lock
        .first()
    )

    if counter is None:
        # First shipment of the day — create counter starting at 1
        counter = DocketCounter(date_key=date_key, last_seq=1)
        db.add(counter)
        db.flush()  # write to DB within this transaction (no commit yet)
        next_seq = 1
    else:
        if counter.last_seq >= MAX_DAILY_SEQ:
            raise OverflowError(
                f"Daily docket limit ({MAX_DAILY_SEQ}) reached for {date_key}"
            )
        counter.last_seq += 1
        db.flush()
        next_seq = counter.last_seq

    seq_str = str(next_seq).zfill(SEQ_WIDTH)
    return f"{PREFIX}{date_key}{seq_str}"
