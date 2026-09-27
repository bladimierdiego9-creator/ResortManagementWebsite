from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db, login_manager


class Account(UserMixin, db.Model):
    __tablename__ = 'accounts'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(32), nullable=False, default='admin')  # admin, super_admin, staff
    rfid_tag = db.Column(db.String(64), unique=True, nullable=True)
    status = db.Column(db.String(16), default='active')  # active, disabled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

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
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(32), nullable=True)
    address = db.Column(db.String(256), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reservations = db.relationship('Reservation', backref='guest', lazy='dynamic')


class Facility(db.Model):
    __tablename__ = 'facilities'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    facility_type = db.Column(db.String(64), nullable=False)  # pool, event_center, pavilion, cabana
    capacity = db.Column(db.Integer, nullable=False)
    price_per_hour = db.Column(db.Float, nullable=False)
    price_whole_day = db.Column(db.Float, nullable=True)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(16), default='available')  # available, maintenance, blocked
    image_url = db.Column(db.String(256), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reservations = db.relationship('Reservation', backref='facility', lazy='dynamic')


class Reservation(db.Model):
    __tablename__ = 'reservations'
    id = db.Column(db.Integer, primary_key=True)
    guest_id = db.Column(db.Integer, db.ForeignKey('guests.id'), nullable=False)
    facility_id = db.Column(db.Integer, db.ForeignKey('facilities.id'), nullable=False)
    event_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    guest_count = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(32), default='pending')  # pending, confirmed, cancelled
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    payment = db.relationship('Payment', backref='reservation', uselist=False)


class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    reservation_id = db.Column(db.Integer, db.ForeignKey('reservations.id'), nullable=False)
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
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True)
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
    facility_id = db.Column(db.Integer, db.ForeignKey('facilities.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    slot_start = db.Column(db.Time, nullable=False)
    slot_end = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(16), default='available')  # available, booked, blocked
    reservation_id = db.Column(db.Integer, db.ForeignKey('reservations.id'), nullable=True)
    facility = db.relationship('Facility', backref='availability_slots')


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
