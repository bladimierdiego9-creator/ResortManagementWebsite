import uuid
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db, login_manager
from sqlalchemy import String, TypeDecorator


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
    reset_token = db.Column(db.String(100), unique=True, nullable=True)
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
        """Generate a password reset token that expires in 1 hour."""
        import secrets
        from datetime import timedelta
        
        self.reset_token = secrets.token_urlsafe(32)
        self.reset_token_expiry = datetime.utcnow() + timedelta(hours=1)
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
    payment = db.relationship('Payment', backref='reservation', uselist=False)


class Booking(db.Model):
    """Guest-facing bookings from the public application."""
    __tablename__ = 'bookings'
    id = db.Column(GUID(), primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    facility_type = db.Column(db.Text, nullable=False)
    inclusions = db.Column(db.JSON, nullable=True)
    check_in = db.Column(db.Date, nullable=False)
    check_out = db.Column(db.Date, nullable=False)
    guests = db.Column(db.Integer, nullable=False)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_method = db.Column(db.Text, nullable=False)
    status = db.Column(db.Text, nullable=False)  # pending, confirmed, cancelled
    archived = db.Column(db.Boolean, default=False)  # soft delete
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    cancellation_reason = db.Column(db.Text, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    
    # Relationship
    account = db.relationship('Account', backref='bookings', foreign_keys=[account_id])


class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    reservation_id = db.Column(db.Integer, db.ForeignKey('reservations.id', ondelete='CASCADE'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_mode = db.Column(db.String(32), nullable=False)  # cash, gcash, bank, card
    status = db.Column(db.String(32), default='pending')  # pending, paid, refunded
    receipt_number = db.Column(db.String(64), unique=True, nullable=True)
    invoice_number = db.Column(db.String(64), unique=True, nullable=True)
    paid_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


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
