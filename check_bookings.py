from app import create_app
from app.models import Reservation, Booking, Facility
from datetime import datetime

app = create_app()
with app.app_context():
    reservations = Reservation.query.filter_by(archived=False).all()
    bookings = Booking.query.filter_by(archived=False).all()
    facilities = Facility.query.all()
    
    print(f"\n=== DATABASE CHECK ===")
    print(f"Total Reservations: {len(reservations)}")
    print(f"Total Bookings: {len(bookings)}")
    print(f"Total Facilities: {len(facilities)}")
    
    print(f"\n=== RESERVATIONS ===")
    for r in reservations[:5]:  # Show first 5
        guest_name = r.guest.full_name if r.guest else 'No guest'
        print(f"ID: {r.id}, Guest: {guest_name}, Date: {r.event_date}, Status: {r.status}")
    
    print(f"\n=== BOOKINGS ===")
    for b in bookings[:5]:  # Show first 5
        guest_name = f"{b.account.first_name} {b.account.last_name}" if b.account else 'No account'
        print(f"ID: {b.id}, Guest: {guest_name}, Check-in: {b.check_in}, Status: {b.status}")
    
    print(f"\n=== FACILITIES ===")
    for f in facilities:
        print(f"ID: {f.id}, Name: {f.facility_name}")
