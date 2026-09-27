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
    """Return reservations as FullCalendar-compatible JSON events.
    FullCalendar sends ?start=YYYY-MM-DD&end=YYYY-MM-DD when navigating months."""
    start_str = req.args.get('start')
    end_str   = req.args.get('end')

    query = db.session.query(Reservation)

    if start_str:
        try:
            query = query.filter(Reservation.event_date >= date.fromisoformat(start_str[:10]))
        except ValueError:
            pass
    if end_str:
        try:
            query = query.filter(Reservation.event_date <= date.fromisoformat(end_str[:10]))
        except ValueError:
            pass

    reservations = query.order_by(Reservation.event_date).all()

    events = []
    for r in reservations:
        if r.status == 'confirmed':
            color = '#2F4A42'
        elif r.status == 'pending':
            color = '#C9975A'
        else:
            color = '#9ca3af'

        events.append({
            'id':        r.id,
            'title':     r.guest.full_name if r.guest else 'Guest',
            'start':     r.event_date.isoformat(),
            'end':       r.event_date.isoformat(),
            'color':     color,
            'textColor': '#ffffff',
            'extendedProps': {
                'status':     r.status,
                'facility':   r.facility.name if r.facility else '—',
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

    # Today's bookings
    todays_bookings = Reservation.query.filter_by(event_date=today).count()

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

    # Recent reservations
    recent_reservations = db.session.query(Reservation).order_by(
        Reservation.created_at.desc()
    ).limit(8).all()

    # AI queue
    ai_queue = AIChatLog.query.filter_by(escalated=True, resolved=False).order_by(
        AIChatLog.created_at.desc()
    ).limit(5).all()

    # Booking chart
    days_in_month = (today - month_start).days + 1
    booking_chart_labels, booking_chart_data = [], []
    for i in range(days_in_month):
        d = month_start + timedelta(days=i)
        booking_chart_labels.append(d.strftime('%b %d'))
        booking_chart_data.append(Reservation.query.filter_by(event_date=d).count())

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

    # Sparkline
    sparkline = [Reservation.query.filter_by(event_date=today - timedelta(days=i)).count() for i in range(6, -1, -1)]

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
                           recent_reservations=recent_reservations,
                           ai_queue=ai_queue,
                           today=today,
                           now=now)
