from flask import render_template, request, redirect, url_for, flash, Response, session, make_response
from flask_login import login_required, current_user
from app.blueprints.payments import payments_bp
from app.decorators import admin_required, log_action
from app.models import Payment, Reservation, GCashConfig, GCashTransaction, PaymentReceipt, Booking
from app.extensions import db
from datetime import datetime, timedelta
from sqlalchemy import func, or_
import base64
import time
from functools import wraps
import secrets


def validate_session_access(f):
    """Decorator to validate session access with URL session param, cookies, and cache control"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 1. Retrieve session token from server session and cookie
        session_token = session.get('payment_verification_token')
        cookie_token = request.cookies.get('payment_session')
        
        # Use existing valid session or generate new secure token
        valid_token = session_token or cookie_token
        if not valid_token:
            valid_token = secrets.token_urlsafe(32)
        
        # Ensure session consistency on server
        session['payment_verification_token'] = valid_token
        session.permanent = True
        
        # 2. Check session in URL query parameters
        url_session = request.args.get('session')
        
        # If GET request and URL session is missing or was changed/tampered with,
        # redirect back to the exact same page with the valid session attached.
        # "para kahit palitan yung url hindi parin aalis sa page kung saan ka nandon"
        if request.method == 'GET' and url_session != valid_token:
            query_params = request.args.to_dict()
            query_params['session'] = valid_token
            redirect_url = url_for(request.endpoint, **query_params, **kwargs)
            
            resp = redirect(redirect_url)
            # Set cookie and cache headers on redirect
            resp.set_cookie(
                'payment_session',
                valid_token,
                max_age=24 * 60 * 60,
                secure=request.is_secure,
                httponly=True,
                samesite='Lax'
            )
            resp.headers['Cache-Control'] = 'private, no-cache, no-store, must-revalidate, max-age=0'
            resp.headers['Pragma'] = 'no-cache'
            resp.headers['Expires'] = '0'
            return resp
        
        # 3. Execute view function
        result = f(*args, **kwargs)
        
        # 4. Attach cookies and cache headers to response
        response = make_response(result)
        response.headers['Cache-Control'] = 'private, no-cache, no-store, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        response.set_cookie(
            'payment_session',
            valid_token,
            max_age=24 * 60 * 60,
            secure=request.is_secure,
            httponly=True,
            samesite='Lax'
        )
        
        return response
    return decorated_function


@payments_bp.route('/')
@login_required
@admin_required
@validate_session_access
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


# ═══════════════════════════════════════════════════════════════════════════
# GCash Verification System
# ═══════════════════════════════════════════════════════════════════════════

@payments_bp.route('/verification')
@login_required
@admin_required
@validate_session_access
def verification():
    """Payment verification dashboard with full management capabilities"""
    # 1. QR Codes (both active and inactive so admin can manage)
    qr_codes = GCashConfig.query.order_by(
        GCashConfig.is_active.desc(),
        GCashConfig.created_at.desc()
    ).all()
    
    # 2. Get unverified payment receipts from new payment_receipts table
    unverified_receipts = PaymentReceipt.query.filter_by(
        verification_status='pending'
    ).order_by(PaymentReceipt.created_at.desc()).all()
    
    # 3. Get verified and rejected receipts
    verified_receipts = PaymentReceipt.query.filter_by(
        verification_status='verified'
    ).order_by(PaymentReceipt.verified_at.desc()).limit(100).all()
    
    rejected_receipts = PaymentReceipt.query.filter_by(
        verification_status='rejected'
    ).order_by(PaymentReceipt.verified_at.desc()).limit(50).all()
    
    # 4. Legacy payments (for backward compatibility)
    unverified_payments = Payment.query.filter_by(
        payment_mode='gcash',
        verification_status='unverified'
    ).order_by(Payment.created_at.desc()).all()
    
    pending_payments = Payment.query.filter_by(
        payment_mode='gcash',
        verification_status='pending'
    ).order_by(Payment.created_at.desc()).all()

    verified_payments = Payment.query.filter_by(
        payment_mode='gcash',
        verification_status='verified'
    ).order_by(Payment.verified_at.desc(), Payment.created_at.desc()).limit(100).all()

    rejected_payments = Payment.query.filter_by(
        payment_mode='gcash',
        verification_status='rejected'
    ).order_by(Payment.verified_at.desc(), Payment.created_at.desc()).limit(50).all()
    
    # 5. All recorded transactions (legacy)
    all_transactions = GCashTransaction.query.order_by(
        GCashTransaction.transaction_date.desc(),
        GCashTransaction.created_at.desc()
    ).all()

    unlinked_transactions = [t for t in all_transactions if t.payment_id is None]
    
    # 6. Recent bookings for upload receipt modal
    recent_bookings = Booking.query.order_by(Booking.created_at.desc()).limit(50).all()
    
    # 7. Smart Matching Engine for modern Payment Receipts and legacy payments
    matches = []
    
    # Priority A: Match Payment Receipts
    for receipt in unverified_receipts:
        receipt_matches = []
        guest_name = ''
        guest_phone = ''
        if receipt.booking and receipt.booking.account:
            acc = receipt.booking.account
            guest_name = f"{acc.first_name or ''} {acc.last_name or ''}".strip().lower()
            if getattr(acc, 'guest_profile', None):
                guest_phone = (acc.guest_profile.phone or '').strip()
            else:
                guest_phone = (getattr(acc, 'mobile', '') or '').strip()

        eff_ref = (receipt.effective_reference_number or '').strip().lower()
        eff_payer = (receipt.effective_payer_name or '').strip().lower()
        eff_amount = receipt.effective_amount
        if eff_amount is None and receipt.booking:
            eff_amount = receipt.booking.total_amount

        for txn in unlinked_transactions:
            matched = False
            match_type = ''
            confidence = ''
            badge_class = ''

            # Priority 1: Exact Reference Match
            if eff_ref and txn.reference_number:
                if eff_ref == txn.reference_number.strip().lower():
                    matched = True
                    match_type = 'Reference Number Match'
                    confidence = 'Exact Match (100%)'
                    badge_class = 'badge-success'

            # Priority 2: Amount + Sender Match
            if not matched and eff_amount and txn.amount:
                if abs(float(txn.amount) - float(eff_amount)) < 0.01:
                    sender_name = (txn.sender_name or '').strip().lower()
                    sender_num = (txn.sender_number or '').strip()

                    name_match = (
                        (guest_name and sender_name and (guest_name in sender_name or sender_name in guest_name)) or
                        (eff_payer and sender_name and (eff_payer in sender_name or sender_name in eff_payer))
                    )
                    phone_match = (guest_phone and sender_num and (guest_phone[-7:] == sender_num[-7:]))

                    if name_match or phone_match:
                        matched = True
                        match_type = 'Amount & Sender Match'
                        confidence = 'High Confidence (95%)'
                        badge_class = 'badge-success'
                    else:
                        matched = True
                        match_type = 'Amount Match'
                        confidence = 'Medium Confidence (80%)'
                        badge_class = 'badge-warning'

            if matched:
                receipt_matches.append({
                    'transaction': txn,
                    'match_type': match_type,
                    'confidence': confidence,
                    'badge_class': badge_class
                })

        if receipt_matches:
            matches.append({
                'type': 'receipt',
                'receipt': receipt,
                'matched_items': receipt_matches
            })

    # Priority B: Match Legacy Payments
    candidates = unverified_payments + pending_payments
    for payment in candidates:
        payment_matches = []
        guest_name = ''
        guest_phone = ''
        if payment.reservation and payment.reservation.guest:
            guest_name = (payment.reservation.guest.full_name or '').strip().lower()
            guest_phone = (payment.reservation.guest.phone or '').strip()

        for txn in unlinked_transactions:
            matched = False
            match_type = ''
            confidence = ''
            badge_class = ''

            # Priority 1: Exact Reference Match
            if payment.gcash_reference_number and txn.reference_number:
                if payment.gcash_reference_number.strip().lower() == txn.reference_number.strip().lower():
                    matched = True
                    match_type = 'Reference Number Match'
                    confidence = 'Exact Match (100%)'
                    badge_class = 'badge-success'

            # Priority 2: Amount + Sender Match
            if not matched and payment.amount and txn.amount:
                if abs(float(txn.amount) - float(payment.amount)) < 0.01:
                    sender_name = (txn.sender_name or '').strip().lower()
                    sender_num = (txn.sender_number or '').strip()
                    
                    name_match = (guest_name and sender_name and (guest_name in sender_name or sender_name in guest_name))
                    phone_match = (guest_phone and sender_num and (guest_phone[-7:] == sender_num[-7:]))
                    
                    if name_match or phone_match:
                        matched = True
                        match_type = 'Amount & Sender Match'
                        confidence = 'High Confidence (95%)'
                        badge_class = 'badge-success'
                    else:
                        matched = True
                        match_type = 'Amount Match'
                        confidence = 'Medium Confidence (80%)'
                        badge_class = 'badge-warning'

            if matched:
                payment_matches.append({
                    'transaction': txn,
                    'match_type': match_type,
                    'confidence': confidence,
                    'badge_class': badge_class
                })

        if payment_matches:
            matches.append({
                'type': 'payment',
                'payment': payment,
                'matched_items': payment_matches
            })

    return render_template('payments/verification.html',
                          qr_codes=qr_codes,
                          unverified_receipts=unverified_receipts,
                          verified_receipts=verified_receipts,
                          rejected_receipts=rejected_receipts,
                          unverified_payments=unverified_payments,
                          pending_payments=pending_payments,
                          verified_payments=verified_payments,
                          rejected_payments=rejected_payments,
                          recent_transactions=all_transactions,
                          unlinked_transactions=unlinked_transactions,
                          recent_bookings=recent_bookings,
                          matches=matches)


# ── QR Code Management ───────────────────────────────────────────────────────

@payments_bp.route('/verification/upload-qr', methods=['POST'])
@login_required
@admin_required
def upload_qr():
    """Upload new GCash QR code configuration"""
    qr_name = request.form.get('qr_name', '').strip()
    account_name = request.form.get('account_name', '').strip()
    account_number = request.form.get('account_number', '').strip()
    qr_file = request.files.get('qr_file')
    
    if not qr_name or not account_name or not account_number or not qr_file or not qr_file.filename:
        flash('All fields and QR image are required.', 'error')
        return redirect(url_for('payments.verification') + '#qrcodes')
    
    if not qr_file.mimetype.startswith('image/'):
        flash('Please upload a valid image file (PNG, JPG, JPEG, WEBP).', 'error')
        return redirect(url_for('payments.verification') + '#qrcodes')
    
    qr_data = base64.b64encode(qr_file.read()).decode('utf-8')
    
    config = GCashConfig(
        qr_code_name=qr_name,
        qr_code_filename=qr_file.filename,
        qr_code_mimetype=qr_file.mimetype,
        qr_code_data=qr_data,
        gcash_account_name=account_name,
        gcash_account_number=account_number,
        is_active=True,
        created_by_id=current_user.id
    )
    
    db.session.add(config)
    db.session.commit()
    log_action(f'Uploaded GCash QR Code: {qr_name}', 'GCashConfig', config.id)
    
    flash('GCash QR code uploaded successfully!', 'success')
    return redirect(url_for('payments.verification') + '#qrcodes')


@payments_bp.route('/verification/qr/<int:id>/toggle-active', methods=['POST'])
@login_required
@admin_required
def toggle_qr_active(id):
    """Toggle QR code active/inactive status"""
    config = GCashConfig.query.get_or_404(id)
    config.is_active = not config.is_active
    config.updated_at = datetime.utcnow()
    db.session.commit()
    status_str = "Active" if config.is_active else "Inactive"
    log_action(f'Toggled GCash QR Code #{config.id} to {status_str}', 'GCashConfig', config.id)
    flash(f'QR Code "{config.qr_code_name}" marked as {status_str}.', 'success')
    return redirect(url_for('payments.verification') + '#qrcodes')


@payments_bp.route('/verification/qr/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_qr(id):
    """Delete a GCash QR code"""
    config = GCashConfig.query.get_or_404(id)
    name = config.qr_code_name
    db.session.delete(config)
    db.session.commit()
    log_action(f'Deleted GCash QR Code #{id} ({name})', 'GCashConfig', id)
    flash(f'QR Code "{name}" deleted.', 'success')
    return redirect(url_for('payments.verification') + '#qrcodes')


# ═══════════════════════════════════════════════════════════════════════════
# Payment Receipts Management (New System)
# ═══════════════════════════════════════════════════════════════════════════

@payments_bp.route('/verification/receipt/<receipt_id>')
@login_required
@admin_required
def receipt_detail(receipt_id):
    """View detailed payment receipt information"""
    receipt = PaymentReceipt.query.get_or_404(receipt_id)
    return render_template('payments/receipt_detail.html', receipt=receipt)


@payments_bp.route('/verification/receipt/<receipt_id>/verify', methods=['POST'])
@login_required
@admin_required
def verify_receipt(receipt_id):
    """Verify a payment receipt (from detail page, quick action, modal, or suggested match)"""
    receipt = PaymentReceipt.query.get_or_404(receipt_id)
    
    # Get manual overrides if provided
    manual_ref = request.form.get('manual_reference_number', '').strip()
    manual_payer = request.form.get('manual_payer_name', '').strip()
    manual_amount = request.form.get('manual_amount', '').strip()
    verification_notes = request.form.get('verification_notes', '').strip()
    transaction_id = request.form.get('transaction_id')
    
    # Link with GCashTransaction if matched
    if transaction_id:
        try:
            txn = GCashTransaction.query.get(int(transaction_id))
            if txn:
                if not manual_ref and txn.reference_number:
                    manual_ref = txn.reference_number
                if not manual_payer and txn.sender_name:
                    manual_payer = txn.sender_name
                if not manual_amount and txn.amount:
                    manual_amount = str(txn.amount)
                
                link_note = f"[Linked to Receipt #{str(receipt.id)[:8]}]"
                if txn.notes:
                    if link_note not in txn.notes:
                        txn.notes = txn.notes + " " + link_note
                else:
                    txn.notes = link_note
        except Exception:
            pass

    # Apply manual overrides
    if manual_ref:
        receipt.manual_reference_number = manual_ref
        if not receipt.reference_number:
            receipt.reference_number = manual_ref
    if manual_payer:
        receipt.manual_payer_name = manual_payer
        if not receipt.payer_name:
            receipt.payer_name = manual_payer
    if manual_amount:
        try:
            parsed_amt = float(manual_amount)
            receipt.manual_amount = parsed_amt
            if not receipt.amount_paid:
                receipt.amount_paid = parsed_amt
        except ValueError:
            flash('Invalid amount format.', 'error')
            return redirect(url_for('payments.receipt_detail', receipt_id=receipt_id))
    
    # Update verification status
    receipt.verification_status = 'verified'
    receipt.verified_by = current_user.id
    receipt.verified_at = datetime.utcnow()
    if verification_notes:
        receipt.verification_notes = verification_notes
    
    # Update the associated booking status
    if receipt.booking:
        receipt.booking.status = 'confirmed'
        receipt.booking.payment_status = 'paid'
        receipt.booking.payment_verified_at = datetime.utcnow()
        receipt.booking.payment_verified_by = current_user.id
        if verification_notes:
            receipt.booking.payment_notes = verification_notes
    
    db.session.commit()
    log_action(f'Verified payment receipt #{receipt.id[:8]}', 'PaymentReceipt', str(receipt.id))
    
    flash(f'Payment receipt #{receipt.id[:8]} verified successfully!', 'success')
    return redirect(url_for('payments.verification') + '#verified')


@payments_bp.route('/verification/receipt/<receipt_id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_receipt(receipt_id):
    """Reject a payment receipt"""
    receipt = PaymentReceipt.query.get_or_404(receipt_id)
    rejection_reason = request.form.get('rejection_reason', '').strip()
    if not rejection_reason:
        rejection_reason = request.form.get('notes', '').strip()
    if not rejection_reason:
        rejection_reason = 'Payment receipt rejected by administrator'
    
    receipt.verification_status = 'rejected'
    receipt.verified_by = current_user.id
    receipt.verified_at = datetime.utcnow()
    receipt.verification_notes = rejection_reason
    
    if receipt.booking:
        receipt.booking.payment_status = 'pending'
        receipt.booking.payment_notes = f"Receipt rejected: {rejection_reason}"
    
    db.session.commit()
    log_action(f'Rejected payment receipt #{receipt.id[:8]}: {rejection_reason}', 'PaymentReceipt', str(receipt.id))
    
    flash(f'Payment receipt #{receipt.id[:8]} marked as rejected.', 'warning')
    return redirect(url_for('payments.verification') + '#unverified')


@payments_bp.route('/verification/receipt/<receipt_id>/reset', methods=['POST'])
@login_required
@admin_required
def reset_receipt(receipt_id):
    """Reset a verified or rejected receipt back to pending status"""
    receipt = PaymentReceipt.query.get_or_404(receipt_id)
    receipt.verification_status = 'pending'
    receipt.verified_by = None
    receipt.verified_at = None
    
    if receipt.booking:
        receipt.booking.payment_status = 'pending'
    
    db.session.commit()
    log_action(f'Reset payment receipt #{receipt.id[:8]} to pending', 'PaymentReceipt', str(receipt.id))
    flash(f'Receipt #{receipt.id[:8]} reset to pending verification.', 'info')
    return redirect(url_for('payments.verification') + '#receipts')


@payments_bp.route('/verification/receipt/<receipt_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_receipt(receipt_id):
    """Delete a payment receipt"""
    receipt = PaymentReceipt.query.get_or_404(receipt_id)
    receipt_short = str(receipt.id)[:8]
    db.session.delete(receipt)
    db.session.commit()
    log_action(f'Deleted payment receipt #{receipt_short}', 'PaymentReceipt', receipt_short)
    flash(f'Payment receipt #{receipt_short} deleted.', 'success')
    return redirect(url_for('payments.verification') + '#receipts')


@payments_bp.route('/verification/receipt/<receipt_id>/image')
@login_required
@admin_required
def receipt_image(receipt_id):
    """Stream payment receipt image"""
    receipt = PaymentReceipt.query.get_or_404(receipt_id)
    image_bytes = receipt.receipt_image_bytes
    if not image_bytes:
        return "No receipt image found", 404
    return Response(image_bytes, mimetype=receipt.receipt_mimetype or 'image/jpeg')


@payments_bp.route('/verification/upload-receipt', methods=['POST'])
@login_required
@admin_required
def upload_receipt():
    """Upload a new payment receipt for verification"""
    booking_id = request.form.get('booking_id', '').strip()
    payment_method = request.form.get('payment_method', 'gcash')
    receipt_file = request.files.get('receipt_file')
    
    # Manual data entry
    manual_ref = request.form.get('manual_reference_number', '').strip()
    manual_payer = request.form.get('manual_payer_name', '').strip()
    manual_amount = request.form.get('manual_amount', '').strip()
    
    if not booking_id or not receipt_file or not receipt_file.filename:
        flash('Booking ID and receipt image are required.', 'error')
        return redirect(url_for('payments.verification') + '#receipts')
    
    if not receipt_file.mimetype.startswith('image/'):
        flash('Please upload a valid image file (PNG, JPG, JPEG, WEBP).', 'error')
        return redirect(url_for('payments.verification') + '#receipts')
    
    # Handle booking ID format
    clean_booking_id = booking_id.replace('book-', '').strip()
    booking = Booking.query.get(clean_booking_id)
    if not booking and len(clean_booking_id) >= 6:
        # Search by prefix
        matching = [b for b in Booking.query.all() if str(b.id).lower().startswith(clean_booking_id.lower())]
        if matching:
            booking = matching[0]
            clean_booking_id = str(booking.id)
            
    if not booking:
        flash(f'Booking "{booking_id}" not found. Please select an existing booking.', 'error')
        return redirect(url_for('payments.verification') + '#receipts')
    
    # Store receipt image
    receipt_data = base64.b64encode(receipt_file.read()).decode('utf-8')
    
    parsed_amount = None
    if manual_amount:
        try:
            parsed_amount = float(manual_amount)
        except ValueError:
            parsed_amount = None
    
    # Create payment receipt record
    receipt = PaymentReceipt(
        booking_id=clean_booking_id,
        payment_method=payment_method,
        receipt_image_data=receipt_data,
        receipt_filename=receipt_file.filename,
        receipt_mimetype=receipt_file.mimetype,
        manual_reference_number=manual_ref or None,
        manual_payer_name=manual_payer or None,
        manual_amount=parsed_amount,
        reference_number=manual_ref or None,
        payer_name=manual_payer or None,
        amount_paid=parsed_amount,
        uploaded_by=current_user.id,
        upload_source='admin',
        ocr_status='manual' if (manual_ref and parsed_amount) else 'pending',
        verification_status='pending'
    )
    
    db.session.add(receipt)
    db.session.commit()
    
    log_action(f'Uploaded payment receipt for booking #{clean_booking_id[:8]}', 'PaymentReceipt', str(receipt.id))
    flash('Payment receipt uploaded successfully!', 'success')
    return redirect(url_for('payments.verification') + '#receipts')


# ═══════════════════════════════════════════════════════════════════════════
# Legacy GCash Management (Existing System)
# ═══════════════════════════════════════════════════════════════════════════



@payments_bp.route('/verification/upload-transaction', methods=['POST'])
@login_required
@admin_required
def upload_transaction():
    """Upload GCash transaction screenshot with optional manual details"""
    screenshot = request.files.get('screenshot')
    if not screenshot or not screenshot.filename:
        flash('Please select a screenshot to upload.', 'error')
        return redirect(url_for('payments.verification') + '#transactions')
    
    if not screenshot.mimetype.startswith('image/'):
        flash('Please upload a valid image file (PNG, JPG, JPEG, WEBP).', 'error')
        return redirect(url_for('payments.verification') + '#transactions')
    
    screenshot_data = base64.b64encode(screenshot.read()).decode('utf-8')
    screenshot_filename = screenshot.filename
    screenshot_mimetype = screenshot.mimetype

    reference_number = request.form.get('reference_number', '').strip()
    if not reference_number:
        reference_number = f"GC-{int(time.time())}"

    # Check unique reference
    existing = GCashTransaction.query.filter_by(reference_number=reference_number).first()
    if existing:
        reference_number = f"{reference_number}-{int(time.time() % 1000)}"

    amount_str = request.form.get('amount', '').strip()
    try:
        amount = float(amount_str) if amount_str else 0.0
    except ValueError:
        amount = 0.0

    sender_name = request.form.get('sender_name', '').strip() or 'GCash Sender'
    sender_number = request.form.get('sender_number', '').strip() or '—'
    notes = request.form.get('notes', '').strip() or 'Uploaded screenshot'

    txn = GCashTransaction(
        reference_number=reference_number,
        transaction_date=datetime.utcnow(),
        sender_name=sender_name,
        sender_number=sender_number,
        amount=amount,
        notes=notes,
        screenshot_filename=screenshot_filename,
        screenshot_mimetype=screenshot_mimetype,
        screenshot_data=screenshot_data,
        uploaded_by_id=current_user.id
    )

    db.session.add(txn)
    db.session.commit()
    log_action(f'Uploaded GCash Screenshot #{txn.id} (Ref {reference_number})', 'GCashTransaction', txn.id)
    flash(f'Screenshot uploaded & recorded as Ref #{reference_number}.', 'success')
    return redirect(url_for('payments.verification') + '#transactions')



@payments_bp.route('/verification/transaction/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_transaction(id):
    """Edit an existing GCash transaction details"""
    txn = GCashTransaction.query.get_or_404(id)
    ref = request.form.get('reference_number', '').strip()
    sender_name = request.form.get('sender_name', '').strip()
    sender_number = request.form.get('sender_number', '').strip()
    amount_str = request.form.get('amount', '').strip()
    notes = request.form.get('notes', '').strip()

    if ref and ref != txn.reference_number:
        existing = GCashTransaction.query.filter_by(reference_number=ref).first()
        if existing:
            flash(f'Reference #{ref} is already taken by another transaction.', 'error')
            return redirect(url_for('payments.verification') + '#transactions')
        txn.reference_number = ref

    if sender_name:
        txn.sender_name = sender_name
    if sender_number:
        txn.sender_number = sender_number
    if amount_str:
        try:
            txn.amount = float(amount_str)
        except ValueError:
            pass
    txn.notes = notes

    db.session.commit()
    log_action(f'Updated GCash Transaction #{id}', 'GCashTransaction', id)
    flash('Transaction details updated.', 'success')
    return redirect(url_for('payments.verification') + '#transactions')


@payments_bp.route('/verification/transaction/<int:id>/unlink', methods=['POST'])
@login_required
@admin_required
def unlink_transaction(id):
    """Unlink a transaction from its payment"""
    txn = GCashTransaction.query.get_or_404(id)
    if txn.payment_id:
        payment = Payment.query.get(txn.payment_id)
        if payment:
            payment.verification_status = 'pending'
            payment.verification_notes = (payment.verification_notes or '') + f' [Unlinked from Txn #{txn.id}]'
        txn.payment_id = None
        db.session.commit()
        log_action(f'Unlinked GCash Transaction #{id} from Payment #{payment.id if payment else "?"}', 'GCashTransaction', id)
        flash('Transaction unlinked from payment. Payment status is now Pending.', 'info')
    return redirect(url_for('payments.verification') + '#transactions')


@payments_bp.route('/verification/transaction/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_transaction(id):
    """Delete a GCash transaction record"""
    txn = GCashTransaction.query.get_or_404(id)
    ref = txn.reference_number
    if txn.payment_id:
        payment = Payment.query.get(txn.payment_id)
        if payment:
            payment.verification_status = 'unverified'
    db.session.delete(txn)
    db.session.commit()
    log_action(f'Deleted GCash Transaction #{id} ({ref})', 'GCashTransaction', id)
    flash(f'Transaction {ref} deleted.', 'success')
    return redirect(url_for('payments.verification') + '#transactions')


# ── Payment Verification Actions ─────────────────────────────────────────────

@payments_bp.route('/verification/<int:payment_id>/verify', methods=['POST'])
@login_required
@admin_required
def verify_payment(payment_id):
    """Verify a payment either by linking to a transaction or direct manual verification"""
    payment = Payment.query.get_or_404(payment_id)
    transaction_id = request.form.get('transaction_id')
    confirm_booking = request.form.get('confirm_booking', '1') == '1'

    if transaction_id:
        # Link to existing GCash Transaction
        transaction = GCashTransaction.query.get_or_404(int(transaction_id))
        payment.gcash_reference_number = transaction.reference_number
        payment.gcash_sender_name = transaction.sender_name
        payment.gcash_sender_number = transaction.sender_number
        transaction.payment_id = payment.id
    else:
        # Direct verification with manual details
        ref = request.form.get('reference_number', '').strip()
        sender_name = request.form.get('sender_name', '').strip()
        sender_number = request.form.get('sender_number', '').strip()
        notes = request.form.get('notes', '').strip()
        auto_record_txn = request.form.get('auto_record_txn') == '1'

        if ref:
            payment.gcash_reference_number = ref
        if sender_name:
            payment.gcash_sender_name = sender_name
        if sender_number:
            payment.gcash_sender_number = sender_number
        if notes:
            payment.verification_notes = notes

        # Auto-create linked transaction if requested and reference exists
        if auto_record_txn and ref:
            existing_txn = GCashTransaction.query.filter_by(reference_number=ref).first()
            if not existing_txn:
                new_txn = GCashTransaction(
                    reference_number=ref,
                    transaction_date=datetime.utcnow(),
                    sender_name=sender_name or (payment.reservation.guest.full_name if payment.reservation and payment.reservation.guest else 'Guest'),
                    sender_number=sender_number or (payment.reservation.guest.phone if payment.reservation and payment.reservation.guest else '—'),
                    amount=payment.amount,
                    payment_id=payment.id,
                    notes=notes or f"Auto-recorded upon verifying Payment #{payment.id}",
                    uploaded_by_id=current_user.id
                )
                db.session.add(new_txn)
            else:
                existing_txn.payment_id = payment.id

    payment.verification_status = 'verified'
    payment.status = 'paid'
    payment.paid_at = datetime.utcnow()
    payment.verified_by_id = current_user.id
    payment.verified_at = datetime.utcnow()

    # Automatically confirm reservation if pending
    if confirm_booking and payment.reservation and payment.reservation.status == 'pending':
        payment.reservation.status = 'confirmed'

    db.session.commit()
    log_action(f'Verified GCash Payment #{payment.id} for Reservation #{payment.reservation_id}', 'Payment', payment.id)
    
    flash(f'Payment #{payment.id} verified and confirmed successfully!', 'success')
    return redirect(url_for('payments.verification') + '#verified')


@payments_bp.route('/verification/<int:payment_id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_payment(payment_id):
    """Reject a payment verification"""
    payment = Payment.query.get_or_404(payment_id)
    notes = request.form.get('notes', '').strip()
    
    if not notes:
        flash('Please provide a reason for rejecting the payment.', 'error')
        return redirect(url_for('payments.verification') + '#unverified')

    # If linked to any transaction(s), release them
    linked_txns = GCashTransaction.query.filter_by(payment_id=payment.id).all()
    for t in linked_txns:
        t.payment_id = None

    payment.verification_status = 'rejected'
    payment.verification_notes = notes
    payment.verified_by_id = current_user.id
    payment.verified_at = datetime.utcnow()
    
    db.session.commit()
    log_action(f'Rejected GCash Payment #{payment.id}. Reason: {notes}', 'Payment', payment.id)
    
    flash(f'Payment #{payment.id} rejected.', 'warning')
    return redirect(url_for('payments.verification') + '#unverified')


@payments_bp.route('/verification/<int:payment_id>/reset', methods=['POST'])
@login_required
@admin_required
def reset_payment(payment_id):
    """Reset a verified or rejected payment back to unverified status"""
    payment = Payment.query.get_or_404(payment_id)
    
    # Release any linked transactions
    linked_txns = GCashTransaction.query.filter_by(payment_id=payment.id).all()
    for t in linked_txns:
        t.payment_id = None

    payment.verification_status = 'unverified'
    payment.status = 'pending'
    payment.verified_by_id = None
    payment.verified_at = None
    db.session.commit()
    log_action(f'Reset GCash Payment #{payment.id} to Unverified', 'Payment', payment.id)
    flash(f'Payment #{payment.id} reset to unverified.', 'info')
    return redirect(url_for('payments.verification') + '#unverified')


@payments_bp.route('/verification/<int:payment_id>/attach-proof', methods=['POST'])
@login_required
@admin_required
def attach_proof(payment_id):
    """Attach guest payment screenshot or reference details to an existing payment"""
    payment = Payment.query.get_or_404(payment_id)
    screenshot = request.files.get('screenshot')
    ref_no = request.form.get('reference_number', '').strip()
    sender_name = request.form.get('sender_name', '').strip()
    sender_number = request.form.get('sender_number', '').strip()

    if screenshot and screenshot.filename:
        if screenshot.mimetype.startswith('image/'):
            payment.gcash_screenshot_data = base64.b64encode(screenshot.read()).decode('utf-8')
            payment.gcash_screenshot_filename = screenshot.filename
            payment.gcash_screenshot_mimetype = screenshot.mimetype
        else:
            flash('File must be an image.', 'error')
            return redirect(url_for('payments.verification') + '#unverified')

    if ref_no:
        payment.gcash_reference_number = ref_no
    if sender_name:
        payment.gcash_sender_name = sender_name
    if sender_number:
        payment.gcash_sender_number = sender_number

    if payment.verification_status == 'unverified':
        payment.verification_status = 'pending'

    db.session.commit()
    log_action(f'Attached GCash proof to Payment #{payment.id}', 'Payment', payment.id)
    flash(f'Proof attached to Payment #{payment.id}.', 'success')
    return redirect(url_for('payments.verification') + '#unverified')


# ── Streaming / Image Endpoints ──────────────────────────────────────────────

@payments_bp.route('/gcash-qr/<int:id>')
@login_required
@admin_required
def gcash_qr(id):
    """Stream GCash QR code image"""
    config = GCashConfig.query.get_or_404(id)
    image_bytes = config.qr_code_bytes
    if not image_bytes:
        return "No QR code found", 404
    return Response(image_bytes, mimetype=config.qr_code_mimetype)


@payments_bp.route('/gcash-transaction/<int:id>/screenshot')
@login_required
@admin_required
def gcash_transaction_screenshot(id):
    """Stream transaction screenshot"""
    txn = GCashTransaction.query.get_or_404(id)
    image_bytes = txn.screenshot_bytes
    if not image_bytes:
        return "No screenshot found", 404
    return Response(image_bytes, mimetype=txn.screenshot_mimetype)


@payments_bp.route('/<int:id>/gcash-screenshot')
@login_required
@admin_required
def gcash_screenshot(id):
    """Stream payment GCash screenshot"""
    payment = Payment.query.get_or_404(id)
    image_bytes = payment.gcash_screenshot_bytes
    if not image_bytes:
        return "No screenshot found", 404
    return Response(image_bytes, mimetype=payment.gcash_screenshot_mimetype)
