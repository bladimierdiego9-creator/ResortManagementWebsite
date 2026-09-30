from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from app.blueprints.reservations import reservations_bp
from app.decorators import admin_required, log_action
from app.models import Reservation, Booking, Guest, Facility, Payment, Account
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
    view_archived = request.args.get('archived', '') == 'true'

    # Build facilities map
    facilities_map = {str(f.id): f.facility_name for f in Facility.query.all()}

    # Fetch reservations (admin-created) - exclude archived by default
    res_query = Reservation.query.filter_by(archived=view_archived)
    if status_filter:
        res_query = res_query.filter_by(status=status_filter)
    if date_from:
        try:
            res_query = res_query.filter(Reservation.event_date >= datetime.strptime(date_from, '%Y-%m-%d').date())
        except ValueError:
            pass
    if date_to:
        try:
            res_query = res_query.filter(Reservation.event_date <= datetime.strptime(date_to, '%Y-%m-%d').date())
        except ValueError:
            pass
    reservations_list = res_query.order_by(Reservation.created_at.desc()).all()

    # Fetch bookings (guest-created) - exclude archived by default
    book_query = Booking.query.filter_by(archived=view_archived)
    if status_filter:
        book_query = book_query.filter_by(status=status_filter)
    if date_from:
        try:
            book_query = book_query.filter(Booking.check_in >= datetime.strptime(date_from, '%Y-%m-%d').date())
        except ValueError:
            pass
    if date_to:
        try:
            book_query = book_query.filter(Booking.check_out <= datetime.strptime(date_to, '%Y-%m-%d').date())
        except ValueError:
            pass
    bookings_list = book_query.order_by(Booking.created_at.desc()).all()

    # Merge into unified list
    combined = []
    for res in reservations_list:
        created = res.created_at.replace(tzinfo=None) if res.created_at and hasattr(res.created_at, 'tzinfo') and res.created_at.tzinfo else res.created_at
        combined.append({
            'type': 'reservation',
            'id': res.id,
            'guest_name': res.guest.full_name if res.guest else '(Guest removed)',
            'guest_contact': res.guest.email or res.guest.phone if res.guest else '—',
            'facility': facilities_map.get(res.facility_id, 'Unknown') if res.facility_id else '—',
            'event_date': res.event_date,
            'time': f"{res.start_time.strftime('%I:%M %p')} – {res.end_time.strftime('%I:%M %p')}",
            'guests': res.guest_count,
            'amount': res.payment.amount if res.payment else 0,
            'status': res.status,
            'payment_status': res.payment.status if res.payment else None,
            'created_at': created,
            'detail_url': url_for('reservations.detail', id=res.id),
            'delete_url': url_for('reservations.delete', id=res.id)
        })
    
    for booking in bookings_list:
        guest_name = f"{booking.account.first_name} {booking.account.last_name}" if booking.account else 'Unknown'
        created = booking.created_at.replace(tzinfo=None) if booking.created_at and hasattr(booking.created_at, 'tzinfo') and booking.created_at.tzinfo else booking.created_at
        combined.append({
            'type': 'booking',
            'id': str(booking.id),
            'guest_name': guest_name,
            'guest_contact': booking.account.email if booking.account else '—',
            'facility': booking.facility_type.replace('_', ' ').title(),
            'event_date': booking.check_in,
            'time': f"Check-in: {booking.check_in.strftime('%b %d')} | Out: {booking.check_out.strftime('%b %d')}",
            'guests': booking.guests,
            'amount': float(booking.total_amount),
            'status': booking.status,
            'payment_status': 'paid' if booking.payment_method else None,
            'created_at': created,
            'detail_url': None,  # No detail page for bookings yet
            'delete_url': None
        })

    # Sort by created_at
    combined.sort(key=lambda x: x['created_at'] or datetime.min, reverse=True)

    # Manual pagination
    per_page = 8
    total = len(combined)
    start = (page - 1) * per_page
    end = start + per_page
    items = combined[start:end]
    
    # Build pagination object manually
    class Pagination:
        def __init__(self, page, per_page, total, items):
            self.page = page
            self.per_page = per_page
            self.total = total
            self.items = items
            self.pages = (total + per_page - 1) // per_page
            self.has_prev = page > 1
            self.has_next = page < self.pages
            self.prev_num = page - 1 if self.has_prev else None
            self.next_num = page + 1 if self.has_next else None
        
        def iter_pages(self, left_edge=1, right_edge=1, left_current=2, right_current=2):
            last = 0
            for num in range(1, self.pages + 1):
                if num <= left_edge or \
                   (num > self.page - left_current - 1 and num < self.page + right_current) or \
                   num > self.pages - right_edge:
                    if last + 1 != num:
                        yield None
                    yield num
                    last = num

    pagination = Pagination(page, per_page, total, items)

    return render_template('reservations/index.html',
                           reservations=items,
                           pagination=pagination,
                           status_filter=status_filter,
                           date_from=date_from,
                           date_to=date_to,
                           facilities_map=facilities_map,
                           view_archived=view_archived)


@reservations_bp.route('/new', methods=['GET', 'POST'])
@login_required
@admin_required
def new():
    facilities = Facility.query.filter_by(is_available=True).order_by(Facility.facility_name).all()
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
            # Validate date is not in the past
            event_date_obj = datetime.strptime(event_date, '%Y-%m-%d').date()
            today = datetime.now().date()
            
            if event_date_obj < today:
                flash('Cannot create booking for past dates.', 'error')
                return render_template('reservations/detail.html',
                                       mode='new',
                                       facilities=facilities,
                                       guests=guests,
                                       facilities_map={str(f.id): f.facility_name for f in facilities},
                                       reservation=None)
            
            reservation = Reservation(
                guest_id=int(guest_id) if guest_id else None,
                facility_id=facility_id,  # UUID string — no int() cast
                event_date=event_date_obj,
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
            flash('Booking created successfully.', 'success')
            return redirect(url_for('reservations.index'))
        except Exception as e:
            db.session.rollback()
            flash('Error creating booking: {str(e)}', 'error')

    return render_template('reservations/detail.html',
                           mode='new',
                           facilities=facilities,
                           guests=guests,
                           facilities_map={str(f.id): f.facility_name for f in facilities},
                           reservation=None,
                           today=datetime.now().date().isoformat())


@reservations_bp.route('/<path:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def detail(id):
    # Check if it's a booking (starts with 'book-' or is a UUID)
    if isinstance(id, str) and (id.startswith('book-') or len(id) > 10):
        booking_id = id.replace('book-', '')
        booking = Booking.query.get_or_404(booking_id)
        
        # Handle status update
        if request.method == 'POST':
            action = request.form.get('action')
            if action == 'update_status':
                new_status = request.form.get('status')
                if new_status in ['pending', 'confirmed', 'cancelled']:
                    booking.status = new_status
                    if new_status == 'cancelled' and not booking.cancelled_at:
                        booking.cancelled_at = datetime.utcnow()
                        booking.cancellation_reason = request.form.get('cancellation_reason', 'Cancelled by admin')
                    db.session.commit()
                    log_action(f'Updated booking status to {new_status}', 'Booking', str(booking.id))
                    flash('Booking status updated.', 'success')
                    return redirect(url_for('reservations.detail', id=f'book-{booking.id}'))
        
        # Booking detail view
        guest_name = f"{booking.account.first_name} {booking.account.last_name}" if booking.account else 'Unknown'
        return render_template('reservations/booking_detail.html',
                               booking=booking,
                               guest_name=guest_name)
    
    # Regular reservation
    try:
        res_id = int(id)
    except ValueError:
        flash('Invalid reservation ID.', 'error')
        return redirect(url_for('reservations.index'))
    
    reservation = Reservation.query.get_or_404(res_id)
    facilities = Facility.query.order_by(Facility.facility_name).all()
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
                           guests=guests,
                           facilities_map={str(f.id): f.facility_name for f in facilities})


@reservations_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(id):
    reservation = Reservation.query.get_or_404(id)
    
    # Check if already archived - if yes, permanent delete
    if reservation.archived:
        db.session.delete(reservation)
        db.session.commit()
        log_action('Permanently deleted reservation', 'Reservation', id)
        flash('Booking permanently deleted.', 'success')
    else:
        flash('Please archive the booking first before deleting.', 'warning')
    
    return redirect(url_for('reservations.index', archived='true' if reservation.archived else ''))


@reservations_bp.route('/<int:id>/archive', methods=['POST'])
@login_required
@admin_required
def archive(id):
    reservation = Reservation.query.get_or_404(id)
    reservation.archived = True
    db.session.commit()
    log_action('Archived reservation', 'Reservation', id)
    flash('Booking archived.', 'success')
    return redirect(url_for('reservations.index'))


@reservations_bp.route('/<int:id>/restore', methods=['POST'])
@login_required
@admin_required
def restore(id):
    reservation = Reservation.query.get_or_404(id)
    reservation.archived = False
    db.session.commit()
    log_action('Restored reservation', 'Reservation', id)
    flash('Booking restored.', 'success')
    return redirect(url_for('reservations.index', archived='true'))


@reservations_bp.route('/book-<booking_id>/archive', methods=['POST'])
@login_required
@admin_required
def archive_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    booking.archived = True
    db.session.commit()
    log_action('Archived booking', 'Booking', str(booking.id))
    flash('Booking archived.', 'success')
    return redirect(url_for('reservations.index'))


@reservations_bp.route('/book-<booking_id>/restore', methods=['POST'])
@login_required
@admin_required
def restore_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    booking.archived = False
    db.session.commit()
    log_action('Restored booking', 'Booking', str(booking.id))
    flash('Booking restored.', 'success')
    return redirect(url_for('reservations.index', archived='true'))


@reservations_bp.route('/book-<booking_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    
    if booking.archived:
        db.session.delete(booking)
        db.session.commit()
        log_action('Permanently deleted booking', 'Booking', str(booking.id))
        flash('Booking permanently deleted.', 'success')
    else:
        flash('Please archive the booking first before deleting.', 'warning')
    
    return redirect(url_for('reservations.index', archived='true' if booking.archived else ''))
