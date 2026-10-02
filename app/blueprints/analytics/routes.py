from flask import render_template, request
from flask_login import login_required
from app.blueprints.analytics import analytics_bp
from app.decorators import admin_required
from app.models import Reservation, Payment, AttendanceLog, Staff
from app.extensions import db
from datetime import datetime, date, timedelta
from sqlalchemy import func


@analytics_bp.route('/')
@login_required
@admin_required
def index():
    today = date.today()
    date_from_str = request.args.get('date_from', (today - timedelta(days=29)).strftime('%Y-%m-%d'))
    date_to_str = request.args.get('date_to', today.strftime('%Y-%m-%d'))

    try:
        date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
        date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
    except ValueError:
        date_from = today - timedelta(days=29)
        date_to = today

    # Booking trends: daily count
    booking_labels = []
    booking_data = []
    delta = date_to - date_from
    for i in range(delta.days + 1):
        d = date_from + timedelta(days=i)
        count = Reservation.query.filter_by(event_date=d).count()
        booking_labels.append(d.strftime('%b %d'))
        booking_data.append(count)

    # Revenue by payment mode
    modes = ['cash', 'gcash', 'bank', 'card']
    revenue_by_mode = {}
    for mode in modes:
        total = db.session.query(func.sum(Payment.amount)).filter_by(
            payment_mode=mode, status='paid'
        ).scalar() or 0
        revenue_by_mode[mode] = total

    # Attendance summary
    on_time = AttendanceLog.query.filter(
        func.date(AttendanceLog.time_in) >= date_from,
        func.date(AttendanceLog.time_in) <= date_to,
        AttendanceLog.status == 'on_time'
    ).count()
    late = AttendanceLog.query.filter(
        func.date(AttendanceLog.time_in) >= date_from,
        func.date(AttendanceLog.time_in) <= date_to,
        AttendanceLog.status == 'late'
    ).count()

    # Reservation status breakdown
    confirmed = Reservation.query.filter_by(status='confirmed').count()
    pending = Reservation.query.filter_by(status='pending').count()
    cancelled = Reservation.query.filter_by(status='cancelled').count()

    chart_data = {
        'bookingTrends': {'labels': booking_labels, 'data': booking_data},
        'revenueByMode': revenue_by_mode,
        'attendance': {'on_time': on_time, 'late': late},
        'reservationStatus': {'confirmed': confirmed, 'pending': pending, 'cancelled': cancelled},
    }

    return render_template('analytics/index.html',
                           chart_data=chart_data,
                           date_from=date_from_str,
                           date_to=date_to_str)
