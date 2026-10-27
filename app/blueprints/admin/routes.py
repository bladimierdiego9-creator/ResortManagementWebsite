from flask import render_template, jsonify, request as req, render_template_string
from flask_login import login_required, current_user
from app.blueprints.admin import admin_bp
from app.decorators import admin_required
from app.models import Reservation, Payment, Staff, AttendanceLog, AIChatLog, Guest, Facility
from app.extensions import db
from datetime import datetime, date, timedelta
import calendar as cal_module
from sqlalchemy import func


def _fmt_clock_time(value):
    """Format a datetime.time as '9:00 AM' (no leading zero) or '—' when missing."""
    if not value:
        return '—'
    return value.strftime('%I:%M %p').lstrip('0')


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
                'start_time': _fmt_clock_time(r.start_time),
                'end_time':   _fmt_clock_time(r.end_time),
                'date_label': r.event_date.strftime('%b %d, %Y'),
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
        elif b.status in ['pending', 'cancel_requested']:
            color = '#f59e0b'  # Amber / orange
        else:
            color = '#64748b'  # Slate gray (cancelled)
        
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

        # The scheduled clock times live on check_in_at / check_out_at. The
        # check_in_time / check_out_time columns are the fallback for bookings
        # created before those timestamps existed.
        check_in_clock = b.check_in_time or (b.check_in_at.time() if b.check_in_at else None)
        check_out_clock = b.check_out_time or (b.check_out_at.time() if b.check_out_at else None)
        
        # Create multi-day event for bookings
        events.append({
            'id':        f'book-{b.id}',
            'title':     f"{guest_name} • {facility_display}",
            'start':     b.check_in.isoformat(),
            'end':       (b.check_out + timedelta(days=1)).isoformat(),  # FullCalendar end date is exclusive
            'color':     color,
            'textColor': '#ffffff',
            'extendedProps': {
                'type':       'booking',
                'status':     b.status,
                'facility':   facility_display,
                'guest':      guest_name,
                'phone':      phone or '—',
                'start_time': _fmt_clock_time(check_in_clock),
                'end_time':   _fmt_clock_time(check_out_clock),
                'date_label': f"{b.check_in.strftime('%b %d')} → {b.check_out.strftime('%b %d, %Y')}",
                'guests':     b.guests,
                'amount':     float(b.total_amount),
                'ref':        f'BOOK-{str(b.id)[:8].upper()}',
                'notes':      b.cancellation_reason if b.status == 'cancelled' else (b.cancellation_request_reason or ''),
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
    todays_bookings_active = Booking.query.filter(
        Booking.check_in <= today,
        Booking.check_out > today,
        Booking.archived == False
    ).count()
    todays_bookings = todays_reservations + todays_bookings_active

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
    ).limit(6).all()
    
    # Get recent bookings
    bookings = db.session.query(Booking).order_by(
        Booking.created_at.desc()
    ).limit(6).all()
    
    # Combine and sort by created_at
    recent_items = []
    
    # Process reservations
    for r in reservations:
        try:
            # Ensure created_at is timezone-naive for comparison
            created_at = r.created_at.replace(tzinfo=None) if r.created_at and r.created_at.tzinfo else r.created_at
            recent_items.append({
                'type': 'reservation',
                'id': r.id,
                'guest_name': r.guest.full_name if r.guest else '(Guest removed)',
                'facility': facilities_map.get(str(r.facility_id), 'Unknown Facility') if r.facility_id else '—',
                'event_date': r.event_date.isoformat() if r.event_date else None,
                'start_time': r.start_time.strftime('%H:%M:%S') if r.start_time else None,
                'amount': float(r.payment.amount) if r.payment and r.payment.amount else 0,
                'status': r.status,
                'created_at': created_at.isoformat() if created_at else None,
            })
        except Exception as e:
            print(f"Error processing reservation {r.id}: {e}")
            continue
    
    # Process bookings
    for b in bookings:
        try:
            # Ensure created_at is timezone-naive for comparison
            created_at = b.created_at.replace(tzinfo=None) if b.created_at and b.created_at.tzinfo else b.created_at
            
            # Get guest name from account
            guest_name = 'Unknown Guest'
            if b.account:
                if hasattr(b.account, 'full_name') and b.account.full_name:
                    guest_name = b.account.full_name
                elif hasattr(b.account, 'first_name') and hasattr(b.account, 'last_name'):
                    guest_name = f"{b.account.first_name} {b.account.last_name}"
                elif hasattr(b.account, 'username'):
                    guest_name = b.account.username
            
            recent_items.append({
                'type': 'booking',
                'id': str(b.id),  # Convert UUID to string for JSON serialization
                'guest_name': guest_name,
                'facility': b.facility_type.replace('_', ' ').title() if b.facility_type else 'Unknown',
                'event_date': b.check_in.isoformat() if b.check_in else None,
                'start_time': b.check_in_time.strftime('%H:%M:%S') if b.check_in_time else None,
                'amount': float(b.total_amount) if b.total_amount else 0,
                'status': b.status,
                'created_at': created_at.isoformat() if created_at else None,
            })
        except Exception as e:
            print(f"Error processing booking {b.id}: {e}")
            continue
    
    # Sort by created_at and take top 10
    recent_items.sort(key=lambda x: datetime.fromisoformat(x['created_at']) if x['created_at'] else datetime.min, reverse=True)
    recent_bookings = recent_items[:10]

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
        
        # Count reservations for this date
        res_count = Reservation.query.filter_by(event_date=d).count()
        
        # Count bookings that include this date (check_in <= d <= check_out)
        book_count = Booking.query.filter(
            Booking.check_in <= d,
            Booking.check_out > d,  # Use > instead of >= to avoid double counting
            Booking.archived == False
        ).count()
        
        booking_chart_data.append(res_count + book_count)

    # Last month booking chart
    last_month_days = (last_month_end - last_month_start).days + 1
    last_month_labels, last_month_data = [], []
    for i in range(last_month_days):
        d = last_month_start + timedelta(days=i)
        last_month_labels.append(d.strftime('%b %d'))
        
        # Count reservations for this date
        res_count = Reservation.query.filter_by(event_date=d).count()
        
        # Count bookings that include this date
        book_count = Booking.query.filter(
            Booking.check_in <= d,
            Booking.check_out > d,
            Booking.archived == False
        ).count()
        
        last_month_data.append(res_count + book_count)

    # Occupancy - include both reservations and bookings
    total_facilities = Facility.query.count()
    
    # Count distinct facilities booked today (reservations)
    booked_by_reservations = db.session.query(func.count(func.distinct(Reservation.facility_id))).filter(
        Reservation.event_date == today,
        Reservation.status == 'confirmed'
    ).scalar() or 0
    
    # Count bookings active today (simplified - count all active bookings as occupying facilities)
    active_bookings_today = Booking.query.filter(
        Booking.check_in <= today,
        Booking.check_out > today,
        Booking.status.in_(['confirmed', 'pending']),
        Booking.archived == False
    ).count()
    
    # Total booked (reservations + active bookings, but cap at total facilities)
    booked_facilities = min(booked_by_reservations + active_bookings_today, total_facilities)
    
    blocked_facilities = Facility.query.filter_by(status='maintenance').count()
    available_facilities = max(0, total_facilities - booked_facilities - blocked_facilities)

    chart_data = {
        'booking':      {'labels': booking_chart_labels, 'data': booking_chart_data},
        'last_booking': {'labels': last_month_labels,    'data': last_month_data},
        'occupancy':    {'booked': booked_facilities, 'available': available_facilities, 'blocked': blocked_facilities},
    }

    # Sparkline (last 7 days combined reservations + bookings)
    sparkline = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        res_count = Reservation.query.filter_by(event_date=day).count()
        book_count = Booking.query.filter(
            Booking.check_in <= day,
            Booking.check_out > day,
            Booking.archived == False
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
