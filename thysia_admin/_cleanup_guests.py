"""
Cleanup: delete old seed guests (ids 1-11).
reservations.guest_id will be SET NULL automatically by the FK.
"""
import sys
sys.path.insert(0, '.')

from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    with db.engine.connect() as conn:

        # Show what will be affected
        result = conn.execute(text("""
            SELECT g.id, g.full_name, COUNT(r.id) AS reservation_count
            FROM guests g
            LEFT JOIN reservations r ON r.guest_id = g.id
            WHERE g.id <= 11
            GROUP BY g.id, g.full_name
            ORDER BY g.id
        """))
        rows = result.fetchall()
        print("Guests to delete and their reservations (will be SET NULL):")
        for row in rows:
            print(f"  guests.id={row[0]:3d}  {row[1]:25s}  reservations={row[2]}")

        print()

        # Delete guests 1-11 — FK cascade sets reservations.guest_id = NULL
        result = conn.execute(text("DELETE FROM guests WHERE id <= 11"))
        conn.commit()
        print(f"Deleted {result.rowcount} old guest rows.")

        # Verify guests table
        result = conn.execute(text("SELECT id, full_name, account_id FROM guests ORDER BY id"))
        remaining = result.fetchall()
        print(f"\nRemaining guests ({len(remaining)} rows):")
        for row in remaining:
            print(f"  id={row[0]}  {row[1]:25s}  account_id={row[2]}")

        # Verify reservations with NULL guest_id
        result = conn.execute(text("SELECT COUNT(*) FROM reservations WHERE guest_id IS NULL"))
        null_count = result.scalar()
        print(f"\nReservations with guest_id=NULL (preserved): {null_count}")
