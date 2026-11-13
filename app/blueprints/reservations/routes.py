from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.blueprints.reservations import reservations_bp
from app.decorators import admin_required, log_action
from app.models import Reservation, Booking, Guest, Facility, Payment, Account
from app.extensions import db
from datetime import datetime, date
from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload


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

    # Count pending cancellation requests for badge
    pending_cancellations = (
        Booking.query.filter(
            or_(Booking.cancellation_request_status == 'pending', Booking.status == 'cancel_requested'),
            Booking.archived == False
        ).count() +
        Reservation.query.filter_by(cancellation_request_status='pending', archived=False).count()
    )

    # Fetch reservations (admin-created) - exclude archived by default
    res_query = Reservation.query.options(
        joinedload(Reservation.guest),
        joinedload(Reservation.payment)
    ).filter_by(archived=view_archived)
    if status_filter:
        if status_filter == 'cancel_requested':
            res_query = res_query.filter_by(cancellation_request_status='pending')
        else:
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
    book_query = Booking.query.options(
        joinedload(Booking.account)
    ).filter_by(archived=view_archived)
    if status_filter:
        if status_filter == 'cancel_requested':
            book_query = book_query.filter(or_(Booking.status == 'cancel_requested', Booking.cancellation_request_status == 'pending'))
        else:
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
        reason = res.cancellation_request_reason
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
            'cancellation_reason': reason,
            'cancellation_request_status': res.cancellation_request_status,
            'cancellation_requested_at': res.cancellation_requested_at,
            'payment_status': res.payment.status if res.payment else None,
            'created_at': created,
            'detail_url': url_for('reservations.detail', id=res.id),
            'delete_url': url_for('reservations.delete', id=res.id)
        })
    
    for booking in bookings_list:
        acc = booking.account
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

        contact = ''
        if acc:
            if hasattr(acc, 'guest_profile') and acc.guest_profile and acc.guest_profile.phone:
                contact = acc.guest_profile.phone
            elif acc.email:
                contact = acc.email

        created = booking.created_at.replace(tzinfo=None) if booking.created_at and hasattr(booking.created_at, 'tzinfo') and booking.created_at.tzinfo else booking.created_at
        reason = booking.cancellation_reason or booking.cancellation_request_reason
        combined.append({
            'type': 'booking',
            'id': str(booking.id),
            'guest_name': guest_name,
            'guest_contact': contact or '—',
            'facility': booking.facility_type.replace('_', ' ').title() if booking.facility_type else 'Resort',
            'event_date': booking.check_in,
            'time': f"Check-in: {booking.check_in.strftime('%b %d')} | Out: {booking.check_out.strftime('%b %d')}",
            'guests': booking.guests,
            'amount': float(booking.total_amount),
            'status': booking.status,
            'cancellation_reason': reason,
            'cancellation_request_status': booking.cancellation_request_status,
            'cancellation_requested_at': booking.cancellation_requested_at,
            'cancelled_at': booking.cancelled_at,
            'payment_status': booking.payment_status or ('paid' if booking.payment_method else 'pending'),
            'created_at': created,
            'detail_url': url_for('reservations.detail', id=f'book-{booking.id}'),
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
                           view_archived=view_archived,
                           pending_cancellations=pending_cancellations)


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
            
            # Parse start and end times for overlap checking
            start_time_obj = datetime.strptime(start_time, '%H:%M').time()
            end_time_obj = datetime.strptime(end_time, '%H:%M').time()
            
            # Check for overlapping reservations on the same facility and date
            overlapping_reservations = Reservation.query.filter(
                Reservation.facility_id == facility_id,
                Reservation.event_date == event_date_obj,
                Reservation.status.in_(['pending', 'confirmed']),
                Reservation.archived == False,
                # Check if time ranges overlap
                # Two time ranges overlap if: start1 < end2 AND end1 > start2
                Reservation.start_time < end_time_obj,
                Reservation.end_time > start_time_obj
            ).first()
            
            if overlapping_reservations:
                facility_name = next((f.facility_name for f in facilities if str(f.id) == facility_id), 'Selected facility')
                flash(f'Cannot create booking. {facility_name} is already reserved on {event_date_obj.strftime("%B %d, %Y")} from {overlapping_reservations.start_time.strftime("%I:%M %p")} to {overlapping_reservations.end_time.strftime("%I:%M %p")}.', 'error')
                return render_template('reservations/detail.html',
                                       mode='new',
                                       facilities=facilities,
                                       guests=guests,
                                       facilities_map={str(f.id): f.facility_name for f in facilities},
                                       reservation=None,
                                       today=datetime.now().date().isoformat())
            
            reservation = Reservation(
                guest_id=int(guest_id) if guest_id else None,
                facility_id=facility_id,  # UUID string — no int() cast
                event_date=event_date_obj,
                start_time=start_time_obj,
                end_time=end_time_obj,
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
                if new_status in ['pending', 'confirmed', 'cancelled', 'cancel_requested']:
                    booking.status = new_status
                    if new_status == 'cancel_requested':
                        if not booking.cancellation_requested_at:
                            booking.cancellation_requested_at = datetime.utcnow()
                        if booking.cancellation_request_status not in ['approved', 'rejected']:
                            booking.cancellation_request_status = 'pending'
                    elif new_status == 'cancelled' and not booking.cancelled_at:
                        booking.cancelled_at = datetime.utcnow()
                        raw_reason = request.form.get('cancellation_reason', '').strip()
                        if raw_reason and len(raw_reason) >= 10:
                            booking.cancellation_reason = raw_reason[:500]
                        elif raw_reason:
                            booking.cancellation_reason = f"Cancelled by administrator: {raw_reason}"[:500]
                        else:
                            booking.cancellation_reason = "Cancelled by administrator"
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


# ═══════════════════════════════════════════════════════════════════════════
# Cancellation Request Management
# ═══════════════════════════════════════════════════════════════════════════

@reservations_bp.route('/book-<booking_id>/request-cancellation', methods=['POST'])
@login_required
@admin_required
def request_booking_cancellation(booking_id):
    """Admin requests cancellation on behalf of guest"""
    booking = Booking.query.get_or_404(booking_id)
    reason = request.form.get('cancellation_reason', '').strip()
    
    if not reason or len(reason) < 10:
        flash('Cancellation reason must be at least 10 characters long.', 'error')
        return redirect(url_for('reservations.detail', id=f'book-{booking.id}'))
    
    if booking.cancellation_request_status == 'pending' or booking.status == 'cancel_requested':
        flash('Cancellation request already pending.', 'warning')
        return redirect(url_for('reservations.detail', id=f'book-{booking.id}'))
    
    # Create cancellation request
    booking.cancellation_requested_at = datetime.utcnow()
    booking.cancellation_request_reason = reason[:500]
    booking.cancellation_request_status = 'pending'
    booking.status = 'cancel_requested'
    
    db.session.commit()
    log_action(f'Requested cancellation for booking: {reason}', 'Booking', str(booking.id))
    flash('Cancellation request submitted successfully.', 'success')
    
    return redirect(url_for('reservations.detail', id=f'book-{booking.id}'))


@reservations_bp.route('/<int:reservation_id>/request-cancellation', methods=['POST'])
@login_required
@admin_required
def request_reservation_cancellation(reservation_id):
    """Admin requests cancellation for reservation"""
    reservation = Reservation.query.get_or_404(reservation_id)
    reason = request.form.get('cancellation_reason', '').strip()
    
    if not reason:
        flash('Cancellation reason is required.', 'error')
        return redirect(url_for('reservations.detail', id=reservation.id))
    
    if reservation.cancellation_request_status == 'pending':
        flash('Cancellation request already pending.', 'warning')
        return redirect(url_for('reservations.detail', id=reservation.id))
    
    # Create cancellation request
    reservation.cancellation_requested_at = datetime.utcnow()
    reservation.cancellation_request_reason = reason
    reservation.cancellation_request_status = 'pending'
    
    db.session.commit()
    log_action(f'Requested cancellation for reservation: {reason}', 'Reservation', reservation.id)
    flash('Cancellation request submitted successfully.', 'success')
    
    return redirect(url_for('reservations.detail', id=reservation.id))


@reservations_bp.route('/book-<booking_id>/handle-cancellation', methods=['POST'])
@login_required
@admin_required
def handle_booking_cancellation(booking_id):
    """Admin approves or rejects cancellation request for booking"""
    booking = Booking.query.get_or_404(booking_id)
    action = request.form.get('action')  # 'approve' or 'reject'
    admin_notes = request.form.get('admin_notes', '').strip()
    
    if booking.cancellation_request_status != 'pending' and booking.status != 'cancel_requested':
        flash('No pending cancellation request found.', 'error')
        redirect_target = request.referrer or url_for('reservations.detail', id=f'book-{booking.id}')
        return redirect(redirect_target)
    
    if action == 'approve':
        # Approve cancellation
        booking.cancellation_request_status = 'approved'
        booking.status = 'cancelled'
        booking.cancelled_at = datetime.utcnow()
        
        # Build reason meeting database check constraint (>= 10 and <= 500 chars)
        reason = (booking.cancellation_request_reason or booking.cancellation_reason or '').strip()
        if admin_notes:
            reason = f"{reason} | Admin: {admin_notes}".strip()
        if not reason or len(reason) < 10:
            reason = f"Cancellation approved: {reason}" if reason else "Cancellation approved by administrator"
        booking.cancellation_reason = reason[:500]
        
        booking.cancellation_handled_by = current_user.id
        booking.cancellation_handled_at = datetime.utcnow()
        
        log_action('Approved cancellation request and cancelled booking', 'Booking', str(booking.id))
        flash('Cancellation request approved. Booking has been cancelled.', 'success')
        
    elif action == 'reject':
        # Reject cancellation and restore booking status to confirmed
        booking.cancellation_request_status = 'rejected'
        booking.status = 'confirmed'
        booking.cancellation_handled_by = current_user.id
        booking.cancellation_handled_at = datetime.utcnow()
        if admin_notes:
            reason = f"Cancellation request rejected: {admin_notes}"
            booking.cancellation_reason = reason[:500] if len(reason) >= 10 else f"Cancellation rejected by admin: {admin_notes}"[:500]
        
        log_action(f'Rejected cancellation request: {admin_notes}', 'Booking', str(booking.id))
        flash('Cancellation request rejected. Booking restored to confirmed status.', 'info')
    
    db.session.commit()
    redirect_target = request.referrer or url_for('reservations.cancellation_requests')
    return redirect(redirect_target)


@reservations_bp.route('/<int:reservation_id>/handle-cancellation', methods=['POST'])
@login_required
@admin_required
def handle_reservation_cancellation(reservation_id):
    """Admin approves or rejects cancellation request for reservation"""
    reservation = Reservation.query.get_or_404(reservation_id)
    action = request.form.get('action')  # 'approve' or 'reject'
    admin_notes = request.form.get('admin_notes', '').strip()
    
    if reservation.cancellation_request_status != 'pending':
        flash('No pending cancellation request found.', 'error')
        return redirect(url_for('reservations.detail', id=reservation.id))
    
    if action == 'approve':
        # Approve cancellation
        reservation.cancellation_request_status = 'approved'
        reservation.status = 'cancelled'
        
        log_action('Approved cancellation request and cancelled reservation', 'Reservation', reservation.id)
        flash('Cancellation request approved. Reservation has been cancelled.', 'success')
        
    elif action == 'reject':
        # Reject cancellation
        reservation.cancellation_request_status = 'rejected'
        
        log_action(f'Rejected cancellation request: {admin_notes}', 'Reservation', reservation.id)
        flash('Cancellation request rejected.', 'info')
    
    reservation.cancellation_handled_by = current_user.id
    reservation.cancellation_handled_at = datetime.utcnow()
    
    db.session.commit()
    return redirect(url_for('reservations.detail', id=reservation.id))


@reservations_bp.route('/cancellation-requests')
@login_required
@admin_required
def cancellation_requests():
    """View all pending cancellation requests"""
    # Get pending booking cancellation requests (support both status=cancel_requested and cancellation_request_status=pending)
    pending_bookings = Booking.query.filter(
        or_(Booking.cancellation_request_status == 'pending', Booking.status == 'cancel_requested'),
        Booking.archived == False
    ).order_by(
        func.coalesce(Booking.cancellation_requested_at, Booking.updated_at).desc()
    ).all()
    
    # Get pending reservation cancellation requests
    pending_reservations = Reservation.query.filter_by(
        cancellation_request_status='pending',
        archived=False
    ).order_by(Reservation.cancellation_requested_at.desc()).all()
    
    # Get recently handled requests (last 30 days)
    from datetime import timedelta
    cutoff_date = datetime.utcnow() - timedelta(days=30)
    
    handled_bookings = Booking.query.filter(
        Booking.cancellation_request_status.in_(['approved', 'rejected']),
        Booking.cancellation_handled_at >= cutoff_date,
        Booking.archived == False
    ).order_by(Booking.cancellation_handled_at.desc()).limit(20).all()
    
    handled_reservations = Reservation.query.filter(
        Reservation.cancellation_request_status.in_(['approved', 'rejected']),
        Reservation.cancellation_handled_at >= cutoff_date,
        Reservation.archived == False
    ).order_by(Reservation.cancellation_handled_at.desc()).limit(20).all()
    
    return render_template('reservations/cancellation_requests.html',
                         pending_bookings=pending_bookings,
                         pending_reservations=pending_reservations,
                         handled_bookings=handled_bookings,
                         handled_reservations=handled_reservations)
