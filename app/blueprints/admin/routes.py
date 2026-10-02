from flask import render_template, jsonify, request as req
from flask_login import login_required, current_user
from app.blueprints.admin import admin_bp
from app.decorators import admin_required
from app.models import Reservation, Payment, Staff, AttendanceLog, AIChatLog, Guest, Facility
from app.extensions import db
from datetime import datetime, date, timedelta
import calendar as cal_module
from sqlalchemy import func


# ── API: FullCalendar events endpoint ─────────────────────────────────────────
@admin_bp.route('/api/bookings')
@login_required
@admin_required
def api_bookings():
    """Return reservations and bookings as FullCalendar-compatible JSON events.
    FullCalendar sends ?start=YYYY-MM-DD&end=YYYY-MM-DD when navigating months."""
    from app.models import Booking
    
    start_str = req.args.get('start')
    end_str   = req.args.get('end')

    # Query reservations (admin-created)
    res_query = db.session.query(Reservation).filter_by(archived=False)

    if start_str:
        try:
            res_query = res_query.filter(Reservation.event_date >= date.fromisoformat(start_str[:10]))
        except ValueError:
            pass
    if end_str:
        try:
            res_query = res_query.filter(Reservation.event_date <= date.fromisoformat(end_str[:10]))
        except ValueError:
            pass

    reservations = res_query.order_by(Reservation.event_date).all()

    # Query bookings (guest-created)
    book_query = db.session.query(Booking).filter_by(archived=False)

    if start_str:
        try:
            start_date = date.fromisoformat(start_str[:10])
            # Include bookings that overlap with the date range
            book_query = book_query.filter(Booking.check_out >= start_date)
        except ValueError:
            pass
    if end_str:
        try:
            end_date = date.fromisoformat(end_str[:10])
            book_query = book_query.filter(Booking.check_in <= end_date)
        except ValueError:
            pass

    bookings = book_query.order_by(Booking.check_in).all()

    # Get facilities map
    facilities = Facility.query.all()
    facilities_map = {str(f.id): f.facility_name for f in facilities}

    events = []
    
    # Add reservations to events
    for r in reservations:
        if r.status == 'confirmed':
            color = '#10b981'  # Green
        elif r.status == 'pending':
            color = '#ee9800'  # Orange
        else:
            color = '#6f8e7d'  # Gray (cancelled)

        events.append({
            'id':        r.id,
            'title':     r.guest.full_name if r.guest else 'Guest',
            'start':     r.event_date.isoformat(),
            'end':       r.event_date.isoformat(),
            'color':     color,
            'textColor': '#ffffff',
            'extendedProps': {
                'type':       'reservation',
                'status':     r.status,
                'facility':   facilities_map.get(r.facility_id, 'Unknown Facility') if r.facility_id else '—',
                'guest':      r.guest.full_name if r.guest else '—',
                'phone':      r.guest.phone if r.guest else '—',
                'start_time': r.start_time.strftime('%I:%M %p') if r.start_time else '—',
                'end_time':   r.end_time.strftime('%I:%M %p') if r.end_time else '—',
                'guests':     r.guest_count,
                'amount':     r.payment.amount if r.payment else 0,
                'ref':        f'RES-{r.id:04d}',
                'notes':      r.notes or '',
            }
        })
    
    # Add bookings to events
    for b in bookings:
        if b.status == 'confirmed':
            color = '#10b981'  # Green
        elif b.status == 'pending':
            color = '#ee9800'  # Orange
        else:
            color = '#6f8e7d'  # Gray (cancelled)
        
        guest_name = f"{b.account.first_name} {b.account.last_name}" if b.account else 'Unknown Guest'
        
        # Create multi-day event for bookings
        events.append({
            'id':        f'book-{b.id}',
            'title':     guest_name,
            'start':     b.check_in.isoformat(),
            'end':       (b.check_out + timedelta(days=1)).isoformat(),  # FullCalendar end date is exclusive
            'color':     color,
            'textColor': '#ffffff',
            'extendedProps': {
                'type':       'booking',
                'status':     b.status,
                'facility':   b.facility_type.replace('_', ' ').title(),
                'guest':      guest_name,
                'phone':      b.account.email if b.account else '—',
                'start_time': f"Check-in: {b.check_in.strftime('%b %d')}",
                'end_time':   f"Check-out: {b.check_out.strftime('%b %d')}",
                'guests':     b.guests,
                'amount':     float(b.total_amount),
                'ref':        f'BOOK-{str(b.id)[:8].upper()}',
                'notes':      b.cancellation_reason if b.status == 'cancelled' else '',
            }
        })

    return jsonify(events), 200, {
        'Cache-Control': 'no-store, no-cache, must-revalidate',
        'Pragma': 'no-cache',
    }


# ── Reservation Calendar page ──────────────────────────────────────────────────
@admin_bp.route('/calendar')
@login_required
@admin_required
def calendar():
    return render_template('admin/calendar.html')


# ── Overview page ──────────────────────────────────────────────────────────────
@admin_bp.route('/')
@admin_bp.route('/overview')
@login_required
@admin_required
def overview():
    now = datetime.now()
    today = now.date()
    month_start = today.replace(day=1)
    last_month_start = (month_start - timedelta(days=1)).replace(day=1)
    last_month_end = month_start - timedelta(days=1)

    # Today's bookings (include both reservations and bookings)
    from app.models import Booking
    
    todays_reservations = Reservation.query.filter_by(event_date=today).count()
    todays_bookings_checkin = Booking.query.filter(
        Booking.check_in <= today,
        Booking.check_out >= today
    ).count()
    todays_bookings = todays_reservations + todays_bookings_checkin

    # Revenue this month
    revenue_this_month = db.session.query(func.sum(Payment.amount)).join(
        Reservation, Payment.reservation_id == Reservation.id
    ).filter(
        Payment.status == 'paid',
        Reservation.event_date >= month_start,
        Reservation.event_date <= today
    ).scalar() or 0

    # Revenue last month
    revenue_last_month = db.session.query(func.sum(Payment.amount)).join(
        Reservation, Payment.reservation_id == Reservation.id
    ).filter(
        Payment.status == 'paid',
        Reservation.event_date >= last_month_start,
        Reservation.event_date <= last_month_end
    ).scalar() or 1

    revenue_change = ((revenue_this_month - revenue_last_month) / revenue_last_month * 100) if revenue_last_month else 0

    # Staff
    total_staff = Staff.query.filter_by(status='active').count()
    clocked_in_today = AttendanceLog.query.filter(
        func.date(AttendanceLog.time_in) == today,
        AttendanceLog.time_out == None
    ).count()

    # Needs attention
    needs_attention = Reservation.query.filter_by(status='pending').count()
    ai_unread = AIChatLog.query.filter_by(escalated=True, resolved=False).count()

    # Create facilities map FIRST (needed for recent items)
    facilities = Facility.query.all()
    facilities_map = {str(f.id): f.facility_name for f in facilities}

    # Recent reservations and bookings combined
    from app.models import Booking
    
    # Get recent reservations
    reservations = db.session.query(Reservation).order_by(
        Reservation.created_at.desc()
    ).limit(4).all()
    
    # Get recent bookings
    bookings = db.session.query(Booking).order_by(
        Booking.created_at.desc()
    ).limit(4).all()
    
    # Combine and sort by created_at
    recent_items = []
    for r in reservations:
        # Ensure created_at is timezone-naive for comparison
        created_at = r.created_at.replace(tzinfo=None) if r.created_at and r.created_at.tzinfo else r.created_at
        recent_items.append({
            'type': 'reservation',
            'id': r.id,
            'guest_name': r.guest.full_name if r.guest else '(Guest removed)',
            'facility': facilities_map.get(str(r.facility_id), 'Unknown Facility') if r.facility_id else '—',
            'event_date': r.event_date,
            'start_time': r.start_time,
            'amount': r.payment.amount if r.payment else 0,
            'status': r.status,
            'created_at': created_at,
        })
    
    for b in bookings:
        # Ensure created_at is timezone-naive for comparison
        created_at = b.created_at.replace(tzinfo=None) if b.created_at and b.created_at.tzinfo else b.created_at
        recent_items.append({
            'type': 'booking',
            'id': b.id,
            'guest_name': f"{b.account.first_name} {b.account.last_name}" if b.account else 'Unknown Guest',
            'facility': b.facility_type.replace('_', ' ').title(),
            'event_date': b.check_in,
            'start_time': None,  # Bookings don't have specific time
            'amount': float(b.total_amount),
            'status': b.status,
            'created_at': created_at,
        })
    
    # Sort by created_at and take top 8
    recent_items.sort(key=lambda x: x['created_at'] or datetime.min, reverse=True)
    recent_bookings = recent_items[:8]

    # AI queue
    ai_queue = AIChatLog.query.filter_by(escalated=True, resolved=False).order_by(
        AIChatLog.created_at.desc()
    ).limit(5).all()

    # Booking chart (combined reservations + bookings per day this month)
    days_in_month = (today - month_start).days + 1
    booking_chart_labels, booking_chart_data = [], []
    for i in range(days_in_month):
        d = month_start + timedelta(days=i)
        booking_chart_labels.append(d.strftime('%b %d'))
        res_count = Reservation.query.filter_by(event_date=d).count()
        book_count = Booking.query.filter(
            Booking.check_in <= d,
            Booking.check_out >= d
        ).count()
        booking_chart_data.append(res_count + book_count)

    # Occupancy
    total_facilities = Facility.query.count()
    booked_facilities = db.session.query(func.count(func.distinct(Reservation.facility_id))).filter(
        Reservation.event_date == today,
        Reservation.status == 'confirmed'
    ).scalar() or 0
    blocked_facilities = Facility.query.filter_by(status='maintenance').count()
    available_facilities = max(0, total_facilities - booked_facilities - blocked_facilities)

    chart_data = {
        'booking':   {'labels': booking_chart_labels, 'data': booking_chart_data},
        'occupancy': {'booked': booked_facilities, 'available': available_facilities, 'blocked': blocked_facilities},
    }

    # Sparkline (last 7 days combined reservations + bookings)
    sparkline = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        res_count = Reservation.query.filter_by(event_date=day).count()
        book_count = Booking.query.filter(
            Booking.check_in <= day,
            Booking.check_out >= day
        ).count()
        sparkline.append(res_count + book_count)

    stats = {
        'todays_bookings':   todays_bookings,
        'revenue_this_month': revenue_this_month,
        'revenue_change':    round(revenue_change, 1),
        'total_staff':       total_staff,
        'clocked_in':        clocked_in_today,
        'needs_attention':   needs_attention,
        'ai_unread':         ai_unread,
        'sparkline':         sparkline,
    }

    return render_template('admin/overview.html',
                           stats=stats,
                           chart_data=chart_data,
                           recent_bookings=recent_bookings,
                           facilities_map=facilities_map,
                           ai_queue=ai_queue,
                           today=today,
                           now=now)
