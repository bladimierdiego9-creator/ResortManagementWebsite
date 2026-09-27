from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from app.blueprints.reservations import reservations_bp
from app.decorators import admin_required, log_action
from app.models import Reservation, Guest, Facility, Payment
from app.extensions import db
from datetime import datetime, date


@reservations_bp.route('/')
@login_required
@admin_required
def index():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    query = Reservation.query.order_by(Reservation.created_at.desc())

    if status_filter:
        query = query.filter_by(status=status_filter)
    if date_from:
        try:
            query = query.filter(Reservation.event_date >= datetime.strptime(date_from, '%Y-%m-%d').date())
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(Reservation.event_date <= datetime.strptime(date_to, '%Y-%m-%d').date())
        except ValueError:
            pass

    pagination = query.paginate(page=page, per_page=8, error_out=False)
    reservations = pagination.items

    return render_template('reservations/index.html',
                           reservations=reservations,
                           pagination=pagination,
                           status_filter=status_filter,
                           date_from=date_from,
                           date_to=date_to)


@reservations_bp.route('/new', methods=['GET', 'POST'])
@login_required
@admin_required
def new():
    facilities = Facility.query.filter_by(status='available').all()
    guests = Guest.query.order_by(Guest.full_name).all()

    if request.method == 'POST':
        guest_id = request.form.get('guest_id')
        facility_id = request.form.get('facility_id')
        event_date = request.form.get('event_date')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        guest_count = request.form.get('guest_count', 1)
        notes = request.form.get('notes', '')
        payment_mode = request.form.get('payment_mode', 'cash')
        amount = request.form.get('amount', 0)

        # Check if new guest
        if guest_id == 'new':
            guest = Guest(
                full_name=request.form.get('guest_name'),
                email=request.form.get('guest_email'),
                phone=request.form.get('guest_phone')
            )
            db.session.add(guest)
            db.session.flush()
            guest_id = guest.id

        try:
            reservation = Reservation(
                guest_id=int(guest_id),
                facility_id=int(facility_id),
                event_date=datetime.strptime(event_date, '%Y-%m-%d').date(),
                start_time=datetime.strptime(start_time, '%H:%M').time(),
                end_time=datetime.strptime(end_time, '%H:%M').time(),
                guest_count=int(guest_count),
                status='pending',
                notes=notes
            )
            db.session.add(reservation)
            db.session.flush()

            import random, string
            receipt_num = 'RCP-' + ''.join(random.choices(string.digits, k=8))
            payment = Payment(
                reservation_id=reservation.id,
                amount=float(amount) if amount else 0,
                payment_mode=payment_mode,
                status='pending',
                receipt_number=receipt_num
            )
            db.session.add(payment)
            db.session.commit()
            log_action('Created reservation', 'Reservation', reservation.id)
            flash('Reservation created successfully.', 'success')
            return redirect(url_for('reservations.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating reservation: {str(e)}', 'error')

    return render_template('reservations/detail.html',
                           mode='new',
                           facilities=facilities,
                           guests=guests,
                           reservation=None)


@reservations_bp.route('/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def detail(id):
    reservation = Reservation.query.get_or_404(id)
    facilities = Facility.query.all()
    guests = Guest.query.order_by(Guest.full_name).all()

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'update_status':
            new_status = request.form.get('status')
            reservation.status = new_status
            db.session.commit()
            log_action(f'Updated reservation status to {new_status}', 'Reservation', id)
            flash('Status updated.', 'success')
        elif action == 'update_payment':
            if reservation.payment:
                reservation.payment.status = request.form.get('payment_status')
                if reservation.payment.status == 'paid':
                    reservation.payment.paid_at = datetime.utcnow()
                db.session.commit()
                flash('Payment updated.', 'success')
        return redirect(url_for('reservations.detail', id=id))

    return render_template('reservations/detail.html',
                           mode='detail',
                           reservation=reservation,
                           facilities=facilities,
                           guests=guests)


@reservations_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(id):
    reservation = Reservation.query.get_or_404(id)
    db.session.delete(reservation)
    db.session.commit()
    log_action('Deleted reservation', 'Reservation', id)
    flash('Reservation deleted.', 'success')
    return redirect(url_for('reservations.index'))
