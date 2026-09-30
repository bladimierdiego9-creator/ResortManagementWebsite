from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
from sqlalchemy import select, func
from app.blueprints.accounts import accounts_bp
from app.decorators import admin_required, log_action
from app.models import Account, Staff, Guest
from app.extensions import db
from datetime import datetime


# ── simple pagination wrapper (Flask-SQLAlchemy 3.x compatible) ─────────────

class _Pagination:
    """Wraps a list of rows with pagination metadata used by the template."""
    def __init__(self, items, total, page, per_page):
        self.items    = items
        self.total    = total
        self.page     = page
        self.per_page = per_page
        self.pages    = max(1, -(-total // per_page))  # ceiling division

    @property
    def has_prev(self):
        return self.page > 1

    @property
    def has_next(self):
        return self.page < self.pages

    @property
    def prev_num(self):
        return self.page - 1

    @property
    def next_num(self):
        return self.page + 1

    def iter_pages(self, left_edge=1, right_edge=1, left_current=2, right_current=2):
        last = 0
        for num in range(1, self.pages + 1):
            if (num <= left_edge
                    or (self.page - left_current <= num <= self.page + right_current)
                    or num > self.pages - right_edge):
                if last + 1 != num:
                    yield None
                yield num
                last = num


# ── helpers ────────────────────────────────────────────────────────────────

def _split_name(full_name):
    """Split 'First Last' into (first, last). Last defaults to '' if absent."""
    parts = full_name.strip().split(' ', 1)
    return parts[0], parts[1] if len(parts) > 1 else ''


def _tab_for_role(role):
    if role == 'staff':
        return 'staff'
    if role == 'guest':
        return 'guests'
    return 'admins'


# ── index ───────────────────────────────────────────────────────────────────

@accounts_bp.route('/')
@login_required
@admin_required
def index():
    tab = request.args.get('tab', 'admins')
    if tab not in ('admins', 'staff', 'guests'):
        tab = 'admins'

    page = request.args.get('page', 1, type=int)

    # Admins tab — accounts only, no join needed
    admin_accounts = Account.query.filter(
        Account.role.in_(['admin', 'super_admin'])
    ).order_by(Account.created_at.desc()).all()

    # Staff tab — accounts with role='staff', left-joined to staff table
    # Use select() + manual pagination (compatible with Flask-SQLAlchemy 3.x)
    PER_PAGE_STAFF = 20
    staff_base = (
        select(Account, Staff)
        .outerjoin(Staff, Staff.account_id == Account.id)
        .where(Account.role == 'staff')
        .order_by(Account.first_name, Account.last_name)
    )
    staff_total = db.session.execute(
        select(func.count()).select_from(
            Account
        ).where(Account.role == 'staff')
    ).scalar() or 0
    staff_rows = db.session.execute(
        staff_base.offset((page - 1) * PER_PAGE_STAFF).limit(PER_PAGE_STAFF)
    ).all()
    staff_accounts = _Pagination(staff_rows, staff_total, page, PER_PAGE_STAFF)

    # Guests tab — accounts with role='guest', left-joined to guests table
    PER_PAGE_GUESTS = 10
    guest_base = (
        select(Account, Guest)
        .outerjoin(Guest, Guest.account_id == Account.id)
        .where(Account.role == 'guest')
        .order_by(Account.first_name, Account.last_name)
    )
    guest_total = db.session.execute(
        select(func.count()).select_from(
            Account
        ).where(Account.role == 'guest')
    ).scalar() or 0
    guest_rows = db.session.execute(
        guest_base.offset((page - 1) * PER_PAGE_GUESTS).limit(PER_PAGE_GUESTS)
    ).all()
    guest_accounts = _Pagination(guest_rows, guest_total, page, PER_PAGE_GUESTS)

    return render_template(
        'accounts/index.html',
        admin_accounts=admin_accounts,
        staff_accounts=staff_accounts,
        guest_accounts=guest_accounts,
        tab=tab,
    )


# ── create admin account ────────────────────────────────────────────────────

@accounts_bp.route('/new', methods=['POST'])
@login_required
@admin_required
def new_account():
    first_name = request.form.get('first_name', '').strip()
    last_name  = request.form.get('last_name', '').strip()
    username   = request.form.get('username', '').strip()
    email      = request.form.get('email', '').strip()
    role       = request.form.get('role', 'admin')
    password   = request.form.get('password', '')
    rfid_tag   = request.form.get('rfid_tag', '').strip() or None

    if role not in ('admin', 'super_admin'):
        role = 'admin'

    if not first_name or not last_name or not username or not email or not password:
        flash('All required fields must be filled in.', 'error')
        return redirect(url_for('accounts.index', tab='admins'))

    if Account.query.filter_by(username=username).first():
        flash(f'Username "{username}" is already taken.', 'error')
        return redirect(url_for('accounts.index', tab='admins'))

    if Account.query.filter_by(email=email).first():
        flash(f'Email "{email}" is already in use.', 'error')
        return redirect(url_for('accounts.index', tab='admins'))

    account = Account(
        first_name=first_name,
        last_name=last_name,
        username=username,
        email=email,
        role=role,
        rfid_tag=rfid_tag,
        status='active',
    )
    account.set_password(password)
    db.session.add(account)
    db.session.commit()
    log_action(f'Created admin account: {username}', 'Account', account.id)
    flash(f'Account for {account.full_name} created successfully.', 'success')
    return redirect(url_for('accounts.index', tab='admins'))


# ── edit admin account ──────────────────────────────────────────────────────

@accounts_bp.route('/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_account(id):
    account = Account.query.get_or_404(id)
    account.first_name = request.form.get('first_name', account.first_name).strip()
    account.last_name  = request.form.get('last_name', account.last_name).strip()
    account.email      = request.form.get('email', account.email).strip()
    account.role       = request.form.get('role', account.role)
    account.rfid_tag   = request.form.get('rfid_tag', '').strip() or None
    account.status     = request.form.get('status', account.status)
    new_password = request.form.get('new_password', '').strip()
    if new_password:
        account.set_password(new_password)
    db.session.commit()
    log_action(f'Updated account: {account.username}', 'Account', id)
    flash('Account updated successfully.', 'success')
    return redirect(url_for('accounts.index', tab=_tab_for_role(account.role)))


# ── delete account ──────────────────────────────────────────────────────────

@accounts_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_account(id):
    account = Account.query.get_or_404(id)
    username = account.username
    tab = _tab_for_role(account.role)
    db.session.delete(account)
    db.session.commit()
    log_action(f'Deleted account: {username}', 'Account', id)
    flash(f'Account {username} deleted.', 'success')
    return redirect(url_for('accounts.index', tab=tab))


# ── create staff account (accounts + staff row) ─────────────────────────────

@accounts_bp.route('/staff/new', methods=['POST'])
@login_required
@admin_required
def new_staff():
    first_name = request.form.get('first_name', '').strip()
    last_name  = request.form.get('last_name', '').strip()
    username   = request.form.get('username', '').strip()
    email      = request.form.get('email', '').strip()
    password   = request.form.get('password', '')
    rfid_tag   = request.form.get('rfid_tag', '').strip() or None
    job_role   = request.form.get('job_role', 'staff').strip()
    shift      = request.form.get('shift', 'morning')
    phone      = request.form.get('phone', '').strip() or None

    if not first_name or not last_name or not username or not password:
        flash('First name, last name, username, and password are required.', 'error')
        return redirect(url_for('accounts.index', tab='staff'))

    if Account.query.filter_by(username=username).first():
        flash(f'Username "{username}" is already taken.', 'error')
        return redirect(url_for('accounts.index', tab='staff'))

    if email and Account.query.filter_by(email=email).first():
        flash(f'Email "{email}" is already in use.', 'error')
        return redirect(url_for('accounts.index', tab='staff'))

    try:
        # Create the accounts row first
        account = Account(
            first_name=first_name,
            last_name=last_name,
            username=username,
            email=email or f'{username}@thysia.local',
            role='staff',
            rfid_tag=rfid_tag,
            status='active',
        )
        account.set_password(password)
        db.session.add(account)
        db.session.flush()  # get account.id without committing

        # Create the linked staff operational row
        staff = Staff(
            account_id=account.id,
            full_name=account.full_name,
            role=job_role,
            email=email or None,
            phone=phone,
            rfid_tag=rfid_tag,
            shift=shift,
            status='active',
        )
        db.session.add(staff)
        db.session.commit()
        log_action(f'Created staff account: {username}', 'Account', account.id)
        flash(f'Staff member {account.full_name} added successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating staff member: {str(e)}', 'error')

    return redirect(url_for('accounts.index', tab='staff'))


# ── edit staff account ──────────────────────────────────────────────────────

@accounts_bp.route('/staff/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_staff(id):
    account = Account.query.get_or_404(id)
    if account.role != 'staff':
        flash('Account is not a staff member.', 'error')
        return redirect(url_for('accounts.index', tab='staff'))

    account.first_name = request.form.get('first_name', account.first_name).strip()
    account.last_name  = request.form.get('last_name', account.last_name).strip()
    account.email      = request.form.get('email', account.email).strip()
    account.rfid_tag   = request.form.get('rfid_tag', '').strip() or None
    account.status     = request.form.get('status', account.status)
    new_password = request.form.get('new_password', '').strip()
    if new_password:
        account.set_password(new_password)

    # Sync the staff operational row if it exists
    if account.staff_profile:
        sp = account.staff_profile
        sp.full_name = account.full_name
        sp.role      = request.form.get('job_role', sp.role).strip()
        sp.shift     = request.form.get('shift', sp.shift)
        sp.phone     = request.form.get('phone', '').strip() or None
        sp.rfid_tag  = account.rfid_tag
        sp.email     = account.email
        sp.status    = account.status

    db.session.commit()
    log_action(f'Updated staff account: {account.username}', 'Account', id)
    flash('Staff member updated successfully.', 'success')
    return redirect(url_for('accounts.index', tab='staff'))


# ── delete staff account ────────────────────────────────────────────────────

@accounts_bp.route('/staff/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_staff(id):
    account = Account.query.get_or_404(id)
    username = account.username
    # staff_profile.account_id will be SET NULL via FK cascade — preserving attendance/payroll
    db.session.delete(account)
    db.session.commit()
    log_action(f'Deleted staff account: {username}', 'Account', id)
    flash(f'Staff account {username} removed.', 'success')
    return redirect(url_for('accounts.index', tab='staff'))


# ── create guest account (accounts + guests row) ────────────────────────────

@accounts_bp.route('/guests/new', methods=['POST'])
@login_required
@admin_required
def new_guest():
    first_name = request.form.get('first_name', '').strip()
    last_name  = request.form.get('last_name', '').strip()
    username   = request.form.get('username', '').strip()
    email      = request.form.get('email', '').strip()
    password   = request.form.get('password', '')
    phone      = request.form.get('phone', '').strip() or None
    address    = request.form.get('address', '').strip() or None

    if not first_name or not last_name or not username or not password:
        flash('First name, last name, username, and password are required.', 'error')
        return redirect(url_for('accounts.index', tab='guests'))

    if Account.query.filter_by(username=username).first():
        flash(f'Username "{username}" is already taken.', 'error')
        return redirect(url_for('accounts.index', tab='guests'))

    if email and Account.query.filter_by(email=email).first():
        flash(f'Email "{email}" is already in use.', 'error')
        return redirect(url_for('accounts.index', tab='guests'))

    try:
        account = Account(
            first_name=first_name,
            last_name=last_name,
            username=username,
            email=email or f'{username}@thysia.local',
            role='guest',
            status='active',
        )
        account.set_password(password)
        db.session.add(account)
        db.session.flush()  # get account.id

        guest = Guest(
            account_id=account.id,
            full_name=account.full_name,
            email=email or None,
            phone=phone,
            address=address,
        )
        db.session.add(guest)
        db.session.commit()
        log_action(f'Created guest account: {username}', 'Account', account.id)
        flash(f'Guest account for {account.full_name} created successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating guest account: {str(e)}', 'error')

    return redirect(url_for('accounts.index', tab='guests'))


# ── edit guest account ──────────────────────────────────────────────────────

@accounts_bp.route('/guests/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_guest(id):
    account = Account.query.get_or_404(id)
    if account.role != 'guest':
        flash('Account is not a guest.', 'error')
        return redirect(url_for('accounts.index', tab='guests'))

    account.first_name = request.form.get('first_name', account.first_name).strip()
    account.last_name  = request.form.get('last_name', account.last_name).strip()
    account.email      = request.form.get('email', account.email).strip()
    account.status     = request.form.get('status', account.status)
    new_password = request.form.get('new_password', '').strip()
    if new_password:
        account.set_password(new_password)

    # Sync the guest profile row if it exists
    if account.guest_profile:
        gp = account.guest_profile
        gp.full_name = account.full_name
        gp.email     = account.email
        gp.phone     = request.form.get('phone', '').strip() or None
        gp.address   = request.form.get('address', '').strip() or None

    db.session.commit()
    log_action(f'Updated guest account: {account.username}', 'Account', id)
    flash('Guest account updated successfully.', 'success')
    return redirect(url_for('accounts.index', tab='guests'))


# ── delete guest account ────────────────────────────────────────────────────

@accounts_bp.route('/guests/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_guest(id):
    account = Account.query.get_or_404(id)
    username = account.username
    # guest_profile.account_id will be SET NULL via FK — reservations are preserved
    db.session.delete(account)
    db.session.commit()
    log_action(f'Deleted guest account: {username}', 'Account', id)
    flash(f'Guest account {username} removed.', 'success')
    return redirect(url_for('accounts.index', tab='guests'))
