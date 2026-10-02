from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.blueprints.payments import payments_bp
from app.decorators import admin_required
from app.models import Payment, Reservation
from app.extensions import db
from datetime import datetime
from sqlalchemy import func


@payments_bp.route('/')
@login_required
@admin_required
def index():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    mode_filter = request.args.get('mode', '')

    query = Payment.query.order_by(Payment.created_at.desc())

    if status_filter:
        query = query.filter_by(status=status_filter)
    if mode_filter:
        query = query.filter_by(payment_mode=mode_filter)

    pagination = query.paginate(page=page, per_page=20, error_out=False)
    payments = pagination.items

    total_revenue = db.session.query(func.sum(Payment.amount)).filter_by(status='paid').scalar() or 0
    pending_amount = db.session.query(func.sum(Payment.amount)).filter_by(status='pending').scalar() or 0

    return render_template('payments/index.html',
                           payments=payments,
                           pagination=pagination,
                           status_filter=status_filter,
                           mode_filter=mode_filter,
                           total_revenue=total_revenue,
                           pending_amount=pending_amount)


@payments_bp.route('/<int:id>/update', methods=['POST'])
@login_required
@admin_required
def update(id):
    payment = Payment.query.get_or_404(id)
    payment.status = request.form.get('status', payment.status)
    if payment.status == 'paid' and not payment.paid_at:
        payment.paid_at = datetime.utcnow()
    db.session.commit()
    flash('Payment updated.', 'success')
    return redirect(url_for('payments.index'))
