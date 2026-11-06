import uuid
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db, login_manager
from sqlalchemy import String, TypeDecorator, func


class GUID(TypeDecorator):
    """
    Platform-independent UUID type.
    - PostgreSQL: uses native UUID column
    - SQLite / others: stores as VARCHAR(36) string
    """
    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import UUID as PG_UUID
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == 'postgresql':
            return str(value) if not isinstance(value, uuid.UUID) else value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return str(value)


class Account(UserMixin, db.Model):
    __tablename__ = 'accounts'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(64), nullable=False)
    last_name = db.Column(db.String(64), nullable=False)
    role = db.Column(db.String(32), nullable=False, default='admin')  # admin, super_admin, staff, guest
    rfid_tag = db.Column(db.String(64), unique=True, nullable=True)
    status = db.Column(db.String(16), default='active')  # active, disabled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    # Password reset fields
    reset_token = db.Column(db.String(100), nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)

    # One-to-one bridges to operational/profile tables
    staff_profile = db.relationship(
        'Staff', backref='account', uselist=False,
        foreign_keys='Staff.account_id'
    )
    guest_profile = db.relationship(
        'Guest', backref='account', uselist=False,
        foreign_keys='Guest.account_id'
    )

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_reset_token(self):
        """Generate a 6-digit OTP that expires in 15 minutes."""
        import random
        from datetime import timedelta
        
        # Generate 6-digit OTP
        self.reset_token = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        self.reset_token_expiry = datetime.utcnow() + timedelta(minutes=15)
        return self.reset_token
    
    def verify_reset_token(self, token):
        """Verify if the reset token is valid and not expired."""
        if not self.reset_token or not self.reset_token_expiry:
            return False
        if self.reset_token != token:
            return False
        if datetime.utcnow() > self.reset_token_expiry:
            return False
        return True
    
    def clear_reset_token(self):
        """Clear the reset token after use."""
        self.reset_token = None
        self.reset_token_expiry = None

    @property
    def is_super_admin(self):
        return self.role == 'super_admin'

    @property
    def is_admin(self):
        return self.role in ('admin', 'super_admin')

    def __repr__(self):
        return f'<Account {self.username}>'


@login_manager.user_loader
def load_user(user_id):
    return Account.query.get(int(user_id))


class Guest(db.Model):
    __tablename__ = 'guests'
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id', ondelete='SET NULL'), nullable=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(32), nullable=True)
    address = db.Column(db.String(256), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reservations = db.relationship('Reservation', backref='guest', lazy='dynamic')


class Facility(db.Model):
    __tablename__ = 'facilities'
    id = db.Column(GUID(), primary_key=True, default=lambda: str(uuid.uuid4()))
    facility_name = db.Column(db.String(120), nullable=False, unique=True)
    facility_type = db.Column(db.String(64), nullable=False)
    description = db.Column(db.Text, nullable=True)
    capacity = db.Column(db.Integer, nullable=True)
    base_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    is_available = db.Column(db.Boolean, default=True)
    archived = db.Column(db.Boolean, default=False)
    # Photo stored straight in the database as base64 — nothing is written to disk.
    # image_data is deferred, so listing facilities never downloads the base64
    # payloads: they are fetched only when a photo is actually served.
    image_filename = db.Column(db.String(256), nullable=True)
    image_mimetype = db.Column(db.String(64), nullable=True)
    image_data = db.deferred(db.Column(db.Text, nullable=True))
    created_at = db.Column(db.DateTime, nullable=True, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def name(self):
        """Alias so existing code using facility.name keeps working."""
        return self.facility_name

    @property
    def status(self):
        """Map is_available to status string for compatibility."""
        return 'available' if self.is_available else 'maintenance'

    @property
    def has_image(self):
        """True when a photo is stored in the database for this facility.

        Reads only the mimetype column so listing facilities stays cheap — the
        base64 payload itself is deferred until it is served.
        """
        return bool(self.image_mimetype)

    @property
    def image_url(self):
        """URL that streams the photo out of the database (facilities.image).

        Use it anywhere a photo has to be shown, e.g.::

            <img src="{{ facility.image_url }}">
        """
        if not self.has_image:
            return None
        version = ''
        if getattr(self, 'updated_at', None):
            version = '?v=' + str(int(self.updated_at.timestamp()))
        try:
            from flask import url_for
            return url_for('facilities.image', id=self.id) + version
        except (RuntimeError, ImportError):
            # No request/app context (scripts, background jobs).
            return f'/facilities/{self.id}/image' + version

    @property
    def image_bytes(self):
        """Raw image bytes decoded from the stored base64 payload."""
        if not self.has_image:
            return None
        import base64
        try:
            return base64.b64decode(self.image_data)
        except Exception:
            return None


class Reservation(db.Model):
    __tablename__ = 'reservations'
    id = db.Column(db.Integer, primary_key=True)
    guest_id = db.Column(db.Integer, db.ForeignKey('guests.id', ondelete='CASCADE'), nullable=True)
    facility_id = db.Column(db.Text, nullable=True)  # stores UUID string from facilities table
    event_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    guest_count = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(32), default='pending')  # pending, confirmed, cancelled
    archived = db.Column(db.Boolean, default=False)  # soft delete
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Cancellation request fields
    cancellation_requested_at = db.Column(db.DateTime, nullable=True)
    cancellation_request_reason = db.Column(db.Text, nullable=True)
    cancellation_request_status = db.Column(db.Text, default='none')  # none, pending, approved, rejected
    cancellation_handled_by = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True)
    cancellation_handled_at = db.Column(db.DateTime, nullable=True)
    
    payment = db.relationship('Payment', backref='reservation', uselist=False)
    cancellation_handler = db.relationship('Account', foreign_keys=[cancellation_handled_by],
                                          primaryjoin="Reservation.cancellation_handled_by == Account.id")


class Booking(db.Model):
    """Guest-facing bookings from the public application."""
    __tablename__ = 'bookings'
    id = db.Column(GUID(), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    facility_type = db.Column(db.Text, nullable=False)
    check_in = db.Column(db.Date, nullable=False)
    check_out = db.Column(db.Date, nullable=False)
    guests = db.Column(db.Integer, nullable=False, default=1)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_method = db.Column(db.Text, nullable=False)
    status = db.Column(db.Text, nullable=False, default='pending')  # pending, confirmed, cancelled, cancel_requested
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), default=func.now())
    cancellation_reason = db.Column(db.Text, nullable=True)
    cancelled_at = db.Column(db.DateTime(timezone=True), nullable=True)
    
    # Check-in and Check-out timestamps (required in schema)
    check_in_at = db.Column(db.DateTime, nullable=False)
    check_out_at = db.Column(db.DateTime, nullable=False)
    archived = db.Column(db.Boolean, default=False)
    check_in_time = db.Column(db.Time, nullable=True)
    check_out_time = db.Column(db.Time, nullable=True)

    # Payment tracking fields
    payment_status = db.Column(db.Text, default='pending')
    payment_verified_at = db.Column(db.DateTime(timezone=True), nullable=True)
    payment_verified_by = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True)
    payment_notes = db.Column(db.Text, nullable=True)

    # Cancellation request fields
    cancellation_requested_at = db.Column(db.DateTime(timezone=True), nullable=True)
    inclusions = db.Column(db.JSON, nullable=True)  # JSONB in schema
    cancellation_request_reason = db.Column(db.Text, nullable=True)
    cancellation_request_status = db.Column(db.Text, default='none')  # none, pending, approved, rejected
    cancellation_handled_by = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True)
    cancellation_handled_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    account = db.relationship('Account', backref='bookings', foreign_keys=[account_id])
    payment_verifier = db.relationship('Account', foreign_keys=[payment_verified_by], 
                                     primaryjoin="Booking.payment_verified_by == Account.id")
    cancellation_handler = db.relationship('Account', foreign_keys=[cancellation_handled_by], 
                                          primaryjoin="Booking.cancellation_handled_by == Account.id")


class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    reservation_id = db.Column(db.Integer, db.ForeignKey('reservations.id', ondelete='CASCADE'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_mode = db.Column(db.String(32), nullable=False)  # cash, gcash, bank, card
    status = db.Column(db.String(32), default='pending')  # pending, paid, refunded, verified
    receipt_number = db.Column(db.String(64), unique=True, nullable=True)
    invoice_number = db.Column(db.String(64), unique=True, nullable=True)
    paid_at = db.Column(db.DateTime, nullable=True)
    
    # GCash verification fields
    gcash_reference_number = db.Column(db.String(64), nullable=True)
    gcash_sender_name = db.Column(db.String(120), nullable=True)
    gcash_sender_number = db.Column(db.String(32), nullable=True)
    gcash_screenshot_filename = db.Column(db.String(256), nullable=True)
    gcash_screenshot_mimetype = db.Column(db.String(64), nullable=True)
    gcash_screenshot_data = db.deferred(db.Column(db.Text, nullable=True))
    verification_status = db.Column(db.String(32), default='unverified')  # unverified, pending, verified, rejected
    verification_notes = db.Column(db.Text, nullable=True)
    verified_by_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True)
    verified_at = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    verified_by = db.relationship('Account', foreign_keys=[verified_by_id], backref='verified_payments')
    
    @property
    def has_gcash_screenshot(self):
        """Check if payment has an uploaded GCash screenshot"""
        return bool(self.gcash_screenshot_mimetype)
    
    @property
    def gcash_screenshot_url(self):
        """URL to view the GCash screenshot"""
        if not self.has_gcash_screenshot:
            return None
        try:
            from flask import url_for
            return url_for('payments.gcash_screenshot', id=self.id)
        except (RuntimeError, ImportError):
            return f'/payments/{self.id}/gcash-screenshot'
    
    @property
    def gcash_screenshot_bytes(self):
        """Raw screenshot bytes decoded from base64"""
        if not self.has_gcash_screenshot:
            return None
        import base64
        try:
            return base64.b64decode(self.gcash_screenshot_data)
        except Exception:
            return None


class GCashConfig(db.Model):
    """Store GCash QR codes and transaction history for payment verification"""
    __tablename__ = 'gcash_configs'
    id = db.Column(db.Integer, primary_key=True)
    qr_code_name = db.Column(db.String(120), nullable=False)
    qr_code_filename = db.Column(db.String(256), nullable=False)
    qr_code_mimetype = db.Column(db.String(64), nullable=False)
    qr_code_data = db.deferred(db.Column(db.Text, nullable=False))
    
    # Associated GCash account info
    gcash_account_name = db.Column(db.String(120), nullable=False)
    gcash_account_number = db.Column(db.String(32), nullable=False)
    
    is_active = db.Column(db.Boolean, default=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    created_by = db.relationship('Account', foreign_keys=[created_by_id], backref='gcash_configs')
    
    @property
    def qr_code_url(self):
        """URL to view the QR code"""
        try:
            from flask import url_for
            return url_for('payments.gcash_qr', id=self.id)
        except (RuntimeError, ImportError):
            return f'/payments/gcash-qr/{self.id}'
    
    @property
    def qr_code_bytes(self):
        """Raw QR code bytes decoded from base64"""
        import base64
        try:
            return base64.b64decode(self.qr_code_data)
        except Exception:
            return None


class GCashTransaction(db.Model):
    """Store GCash transaction history for verification"""
    __tablename__ = 'gcash_transactions'
    id = db.Column(db.Integer, primary_key=True)
    reference_number = db.Column(db.String(64), unique=True, nullable=False)
    transaction_date = db.Column(db.DateTime, nullable=False)
    sender_name = db.Column(db.String(120), nullable=False)
    sender_number = db.Column(db.String(32), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    
    # Link to payment if verified
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id'), nullable=True)
    
    # Screenshot of transaction
    screenshot_filename = db.Column(db.String(256), nullable=True)
    screenshot_mimetype = db.Column(db.String(64), nullable=True)
    screenshot_data = db.deferred(db.Column(db.Text, nullable=True))
    
    notes = db.Column(db.Text, nullable=True)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    payment = db.relationship('Payment', backref='gcash_transaction', uselist=False, foreign_keys=[payment_id])
    uploaded_by = db.relationship('Account', foreign_keys=[uploaded_by_id], backref='uploaded_gcash_transactions')
    
    @property
    def has_screenshot(self):
        return bool(self.screenshot_mimetype)
    
    @property
    def screenshot_url(self):
        if not self.has_screenshot:
            return None
        try:
            from flask import url_for
            return url_for('payments.gcash_transaction_screenshot', id=self.id)
        except (RuntimeError, ImportError):
            return f'/payments/gcash-transaction/{self.id}/screenshot'
    
    @property
    def screenshot_bytes(self):
        if not self.has_screenshot:
            return None
        import base64
        try:
            return base64.b64decode(self.screenshot_data)
        except Exception:
            return None


class Staff(db.Model):
    __tablename__ = 'staff'
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id', ondelete='SET NULL'), nullable=True)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(64), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(32), nullable=True)
    rfid_tag = db.Column(db.String(64), unique=True, nullable=True)
    shift = db.Column(db.String(32), nullable=True)  # morning, afternoon, evening
    status = db.Column(db.String(16), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    attendance_logs = db.relationship('AttendanceLog', backref='staff', lazy='dynamic')
    payroll_records = db.relationship('Payroll', backref='staff', lazy='dynamic')


class AttendanceLog(db.Model):
    __tablename__ = 'attendance_logs'
    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.Integer, db.ForeignKey('staff.id'), nullable=False)
    time_in = db.Column(db.DateTime, nullable=False)
    time_out = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(16), default='on_time')  # on_time, late, absent
    rfid_tap_in = db.Column(db.String(64), nullable=True)
    rfid_tap_out = db.Column(db.String(64), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class RFIDCard(db.Model):
    __tablename__ = 'rfid_cards'
    id = db.Column(db.Integer, primary_key=True)
    card_uid = db.Column(db.String(64), unique=True, nullable=False, index=True)
    staff_id = db.Column(db.Integer, db.ForeignKey('staff.id', ondelete='SET NULL'), nullable=True)
    status = db.Column(db.String(32), nullable=False, default='active')  # active, inactive, blocked
    notes = db.Column(db.String(256), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used_at = db.Column(db.DateTime, nullable=True)

    staff = db.relationship('Staff', backref=db.backref('rfid_cards', lazy='dynamic'))

    @property
    def owner_name(self):
        return self.staff.full_name if self.staff else 'Unassigned'

    @property
    def is_assigned(self):
        return self.staff_id is not None

    def __repr__(self):
        return f'<RFIDCard {self.card_uid} ({self.owner_name})>'


class Payroll(db.Model):
    __tablename__ = 'payrolls'
    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.Integer, db.ForeignKey('staff.id'), nullable=False)
    pay_period_start = db.Column(db.Date, nullable=False)
    pay_period_end = db.Column(db.Date, nullable=False)
    regular_hours = db.Column(db.Float, nullable=False, default=0)
    overtime_hours = db.Column(db.Float, nullable=False, default=0)
    hourly_rate = db.Column(db.Float, nullable=False)
    overtime_rate = db.Column(db.Float, nullable=False)
    gross_pay = db.Column(db.Float, nullable=False, default=0)
    deductions = db.Column(db.Float, nullable=False, default=0)
    net_pay = db.Column(db.Float, nullable=False, default=0)
    status = db.Column(db.String(16), default='pending')  # pending, generated, paid
    generated_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ShiftHandover(db.Model):
    __tablename__ = 'shift_handovers'
    id = db.Column(db.Integer, primary_key=True)
    outgoing_staff_id = db.Column(db.Integer, db.ForeignKey('staff.id'), nullable=False)
    incoming_staff_id = db.Column(db.Integer, db.ForeignKey('staff.id'), nullable=True)
    notes = db.Column(db.Text, nullable=False)
    pending_tasks = db.Column(db.Text, nullable=True)
    acknowledged = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    outgoing_staff = db.relationship('Staff', foreign_keys=[outgoing_staff_id])
    incoming_staff = db.relationship('Staff', foreign_keys=[incoming_staff_id])


class FacilityAvailability(db.Model):
    __tablename__ = 'facility_availability'
    id = db.Column(db.Integer, primary_key=True)
    facility_id = db.Column(GUID(), db.ForeignKey('facilities.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    slot_start = db.Column(db.Time, nullable=False)
    slot_end = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(16), default='available')  # available, booked, blocked
    reservation_id = db.Column(db.Integer, db.ForeignKey('reservations.id'), nullable=True)
    # passive_deletes: the ORM must not try to load/null slot rows when a
    # facility is removed — "facility_availability" is cleared explicitly in the
    # facilities blueprint (its facility_id column has no FK to facilities).
    facility = db.relationship('Facility', backref=db.backref('availability_slots', passive_deletes=True))


class AIChatLog(db.Model):
    __tablename__ = 'ai_chat_logs'
    id = db.Column(db.Integer, primary_key=True)
    guest_name = db.Column(db.String(120), nullable=False)
    guest_contact = db.Column(db.String(120), nullable=True)
    inquiry = db.Column(db.Text, nullable=False)
    ai_response = db.Column(db.Text, nullable=True)
    escalated = db.Column(db.Boolean, default=False)
    resolved = db.Column(db.Boolean, default=False)
    admin_reply = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True)
    action = db.Column(db.String(256), nullable=False)
    entity_type = db.Column(db.String(64), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    account = db.relationship('Account', backref='audit_logs')


class Announcement(db.Model):
    """Announcements stored in database instead of Firebase"""
    __tablename__ = 'announcements'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    target_audience = db.Column(db.String(20), nullable=False)  # 'staff', 'guest', or 'all'
    created_by_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    created_by_name = db.Column(db.String(128), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationship to creator
    created_by = db.relationship('Account', backref='announcements', foreign_keys=[created_by_id])
    
    def __repr__(self):
        return f'<Announcement {self.title}>'
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': str(self.id),
            'title': self.title,
            'content': self.content,
            'target_audience': self.target_audience,
            'created_by_id': self.created_by_id,
            'created_by_name': self.created_by_name,
            'is_active': self.is_active,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

class PaymentReceipt(db.Model):
    """New comprehensive payment receipt management system"""
    __tablename__ = 'payment_receipts'
    
    id = db.Column(GUID(), primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id = db.Column(GUID(), db.ForeignKey('bookings.id'), nullable=False)
    payment_method = db.Column(db.Text, nullable=False)
    
    # Receipt image storage
    receipt_image_url = db.Column(db.Text, nullable=True)
    receipt_image_data = db.Column(db.Text, nullable=True)  # base64 encoded
    receipt_filename = db.Column(db.Text, nullable=True)
    receipt_mimetype = db.Column(db.Text, nullable=True)
    
    # OCR extracted data
    reference_number = db.Column(db.Text, nullable=True)
    payer_name = db.Column(db.Text, nullable=True)
    amount_paid = db.Column(db.Numeric(10, 2), nullable=True)
    payment_date = db.Column(db.DateTime, nullable=True)
    
    # Manual override data
    manual_reference_number = db.Column(db.Text, nullable=True)
    manual_payer_name = db.Column(db.Text, nullable=True)
    manual_amount = db.Column(db.Numeric(10, 2), nullable=True)
    
    # OCR processing status
    ocr_status = db.Column(db.Text, default='pending')  # pending, processing, completed, failed, manual
    ocr_confidence = db.Column(db.Numeric(5, 2), nullable=True)
    ocr_raw_data = db.Column(db.JSON, nullable=True)
    ocr_error = db.Column(db.Text, nullable=True)
    
    # Verification workflow
    verification_status = db.Column(db.Text, default='pending')  # pending, verified, rejected
    verified_by = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True)
    verified_at = db.Column(db.DateTime, nullable=True)
    verification_notes = db.Column(db.Text, nullable=True)
    
    # Upload tracking
    uploaded_by = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    upload_source = db.Column(db.Text, default='customer')  # customer, staff, admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    booking = db.relationship('Booking', backref='payment_receipts')
    uploader = db.relationship('Account', foreign_keys=[uploaded_by])
    verifier = db.relationship('Account', foreign_keys=[verified_by], 
                              primaryjoin="PaymentReceipt.verified_by == Account.id")

    @property
    def receipt_image_bytes(self):
        """Convert base64 receipt data to bytes"""
        if self.receipt_image_data:
            import base64
            return base64.b64decode(self.receipt_image_data)
        return None

    @property
    def effective_reference_number(self):
        """Get the reference number (manual override takes precedence)"""
        return self.manual_reference_number or self.reference_number

    @property
    def effective_payer_name(self):
        """Get the payer name (manual override takes precedence)"""
        return self.manual_payer_name or self.payer_name

    @property
    def effective_amount(self):
        """Get the amount (manual override takes precedence)"""
        return self.manual_amount or self.amount_paid

    @property
    def has_manual_overrides(self):
        """Check if any manual overrides are set"""
        return bool(self.manual_reference_number or self.manual_payer_name or self.manual_amount)

    @property
    def needs_ocr_processing(self):
        """Check if OCR processing is needed"""
        return self.ocr_status in ['pending', 'failed'] and self.receipt_image_data

    @property
    def has_receipt_image(self):
        return bool(self.receipt_image_data or self.receipt_image_url)

    @property
    def receipt_url(self):
        if not self.has_receipt_image:
            return None
        try:
            from flask import url_for
            return url_for('payments.receipt_image', receipt_id=str(self.id))
        except Exception:
            return f'/payments/verification/receipt/{self.id}/image'

    @property
    def is_fully_processed(self):
        """Check if receipt has been fully processed (OCR + manual data)"""
        return bool(self.effective_reference_number and self.effective_amount)