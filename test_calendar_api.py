from app import create_app
from app.models import Reservation, Booking, Facility, Account
from datetime import datetime, date, timedelta
from flask import jsonify
import json

app = create_app()

with app.app_context():
    # Simulate the API request
    start_str = '2026-09-27'  # Start of calendar view
    end_str = '2026-11-08'    # End of calendar view
    
    # Query reservations
    res_query = Reservation.query.filter_by(archived=False)
    if start_str:
        res_query = res_query.filter(Reservation.event_date >= date.fromisoformat(start_str[:10]))
    if end_str:
        res_query = res_query.filter(Reservation.event_date <= date.fromisoformat(end_str[:10]))
    
    reservations = res_query.order_by(Reservation.event_date).all()
    
    # Query bookings
    book_query = Booking.query.filter_by(archived=False)
    if start_str:
        start_date = date.fromisoformat(start_str[:10])
        book_query = book_query.filter(Booking.check_out >= start_date)
    if end_str:
        end_date = date.fromisoformat(end_str[:10])
        book_query = book_query.filter(Booking.check_in <= end_date)
    
    bookings = book_query.order_by(Booking.check_in).all()
    
    # Get facilities map
    facilities = Facility.query.all()
    facilities_map = {str(f.id): f.facility_name for f in facilities}
    
    events = []
    
    print("\n=== PROCESSING RESERVATIONS ===")
    for r in reservations:
        if r.status == 'confirmed':
            color = '#10b981'
        elif r.status == 'pending':
            color = '#ee9800'
        else:
            color = '#6f8e7d'
        
        event = {
            'id': r.id,
            'title': r.guest.full_name if r.guest else 'Guest',
            'start': r.event_date.isoformat(),
            'end': r.event_date.isoformat(),
            'color': color,
            'textColor': '#ffffff',
            'extendedProps': {
                'type': 'reservation',
                'status': r.status,
                'facility': facilities_map.get(r.facility_id, 'Unknown') if r.facility_id else '—',
                'guest': r.guest.full_name if r.guest else '—',
                'phone': r.guest.phone if r.guest else '—',
                'start_time': r.start_time.strftime('%I:%M %p') if r.start_time else '—',
                'end_time': r.end_time.strftime('%I:%M %p') if r.end_time else '—',
                'guests': r.guest_count,
                'amount': r.payment.amount if r.payment else 0,
                'ref': f'RES-{r.id:04d}',
                'notes': r.notes or '',
            }
        }
        events.append(event)
        print(f"✓ Reservation {r.id}: {event['title']} on {event['start']}")
    
    print(f"\n=== PROCESSING BOOKINGS ===")
    for b in bookings:
        if b.status == 'confirmed':
            color = '#10b981'
        elif b.status in ['pending', 'cancel_requested']:
            color = '#f59e0b'
        else:
            color = '#64748b'
        
        acc = b.account
        guest_name = ''
        if acc:
            if acc.first_name or acc.last_name:
                guest_name = f"{acc.first_name or ''} {acc.last_name or ''}".strip()
            elif hasattr(acc, 'guest_profile') and acc.guest_profile and acc.guest_profile.full_name:
                guest_name = acc.guest_profile.full_name.strip()
            elif acc.username:
                guest_name = acc.username
        if not guest_name:
            guest_name = 'Guest'
        
        phone = ''
        if acc:
            if hasattr(acc, 'guest_profile') and acc.guest_profile and acc.guest_profile.phone:
                phone = acc.guest_profile.phone
            elif acc.email:
                phone = acc.email
        
        facility_display = b.facility_type.replace('_', ' ').title() if b.facility_type else 'Resort'
        
        event = {
            'id': f'book-{b.id}',
            'title': f"{guest_name} • {facility_display}",
            'start': b.check_in.isoformat(),
            'end': (b.check_out + timedelta(days=1)).isoformat(),
            'color': color,
            'textColor': '#ffffff',
            'extendedProps': {
                'type': 'booking',
                'status': b.status,
                'facility': facility_display,
                'guest': guest_name,
                'phone': phone or '—',
                'start_time': f"Check-in: {b.check_in.strftime('%b %d')}",
                'end_time': f"Check-out: {b.check_out.strftime('%b %d')}",
                'guests': b.guests,
                'amount': float(b.total_amount),
                'ref': f'BOOK-{str(b.id)[:8].upper()}',
                'notes': b.cancellation_reason if b.status == 'cancelled' else (b.cancellation_request_reason or ''),
            }
        }
        events.append(event)
        print(f"✓ Booking {str(b.id)[:8]}: {guest_name} from {event['start']} to {event['end']}")
    
    print(f"\n=== TOTAL EVENTS ===")
    print(f"Total events to display: {len(events)}")
    
    print(f"\n=== SAMPLE EVENT JSON ===")
    if events:
        print(json.dumps(events[0], indent=2))
