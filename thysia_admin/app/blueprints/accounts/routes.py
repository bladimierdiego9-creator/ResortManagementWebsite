from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.blueprints.accounts import accounts_bp
from app.decorators import admin_required, log_action
from app.models import Account, Staff, Guest
from app.extensions import db
from datetime import datetime


@accounts_bp.route('/')
@login_required
@admin_required
def index():
    tab = request.args.get('tab', 'admins')
    # Valid tabs: admins, staff, guests
    if tab not in ('admins', 'staff', 'guests'):
        tab = 'admins'

    page = request.args.get('page', 1, type=int)

    admin_accounts = Account.query.filter(
        Account.role.in_(['admin', 'super_admin'])
    ).order_by(Account.created_at.desc()).all()

    staff_list = Staff.query.order_by(Staff.full_name).paginate(
        page=page, per_page=20, error_out=False
    )

    guests = Guest.query.order_by(Guest.full_name).paginate(
        page=page, per_page=8, error_out=False
    )

    return render_template('accounts/index.html',
                           admin_accounts=admin_accounts,
                           staff_list=staff_list,
                           guests=guests,
                           tab=tab)


@accounts_bp.route('/new', methods=['POST'])
@login_required
@admin_required
def new_account():
    username  = request.form.get('username', '').strip()
    email     = request.form.get('email', '').strip()
    full_name = request.form.get('full_name', '').strip()
    role      = request.form.get('role', 'admin')
    password  = request.form.get('password', '')
    rfid_tag  = request.form.get('rfid_tag', '').strip() or None

    if not username or not email or not full_name or not password:
        flash('All required fields must be filled in.', 'error')
        return redirect(url_for('accounts.index', tab='admins'))

    if Account.query.filter_by(username=username).first():
        flash(f'Username "{username}" is already taken. Choose another.', 'error')
        return redirect(url_for('accounts.index', tab='admins'))

    if Account.query.filter_by(email=email).first():
        flash(f'Email "{email}" is already in use.', 'error')
        return redirect(url_for('accounts.index', tab='admins'))

    account = Account(
        username=username,
        email=email,
        full_name=full_name,
        role=role,
        rfid_tag=rfid_tag,
        status='active'
    )
    account.set_password(password)
    db.session.add(account)
    db.session.commit()
    log_action(f'Created account: {username}', 'Account', account.id)
    flash(f'Account for {full_name} created successfully.', 'success')
    return redirect(url_for('accounts.index', tab='admins'))


@accounts_bp.route('/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_account(id):
    account = Account.query.get_or_404(id)
    account.full_name = request.form.get('full_name', account.full_name).strip()
    account.email     = request.form.get('email', account.email).strip()
    account.role      = request.form.get('role', account.role)
    account.rfid_tag  = request.form.get('rfid_tag', '').strip() or None
    account.status    = request.form.get('status', account.status)
    new_password = request.form.get('new_password', '').strip()
    if new_password:
        account.set_password(new_password)
    db.session.commit()
    log_action(f'Updated account: {account.username}', 'Account', id)
    flash('Account updated successfully.', 'success')
    return redirect(url_for('accounts.index', tab='admins'))


@accounts_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_account(id):
    account = Account.query.get_or_404(id)
    username = account.username
    db.session.delete(account)
    db.session.commit()
    log_action(f'Deleted account: {username}', 'Account', id)
    flash(f'Account {username} deleted.', 'success')
    return redirect(url_for('accounts.index'))


@accounts_bp.route('/staff/new', methods=['POST'])
@login_required
@admin_required
def new_staff():
    full_name   = request.form.get('full_name', '').strip()
    role        = request.form.get('role', 'staff').strip()
    email       = request.form.get('email', '').strip()
    phone       = request.form.get('phone', '').strip()
    rfid_tag    = request.form.get('rfid_tag', '').strip() or None
    shift       = request.form.get('shift', 'morning')

    if not full_name or not role:
        flash('Full name and role are required.', 'error')
        return redirect(url_for('accounts.index', tab='staff'))

    staff = Staff(
        full_name=full_name,
        role=role,
        email=email or None,
        phone=phone or None,
        rfid_tag=rfid_tag,
        shift=shift,
        status='active'
    )
    db.session.add(staff)
    db.session.commit()
    log_action(f'Created staff: {staff.full_name}', 'Staff', staff.id)
    flash(f'Staff member {full_name} added successfully.', 'success')
    return redirect(url_for('accounts.index', tab='staff'))


@accounts_bp.route('/staff/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_staff(id):
    staff = Staff.query.get_or_404(id)
    staff.full_name = request.form.get('full_name', staff.full_name).strip()
    staff.role      = request.form.get('role', staff.role).strip()
    staff.email     = request.form.get('email', '').strip() or None
    staff.phone     = request.form.get('phone', '').strip() or None
    staff.rfid_tag  = request.form.get('rfid_tag', '').strip() or None
    staff.shift     = request.form.get('shift', staff.shift)
    staff.status    = request.form.get('status', staff.status)
    db.session.commit()
    log_action(f'Updated staff: {staff.full_name}', 'Staff', id)
    flash('Staff member updated.', 'success')
    return redirect(url_for('accounts.index', tab='staff'))


@accounts_bp.route('/staff/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_staff(id):
    staff = Staff.query.get_or_404(id)
    name = staff.full_name
    db.session.delete(staff)
    db.session.commit()
    log_action(f'Deleted staff: {name}', 'Staff', id)
    flash(f'Staff member {name} removed.', 'success')
    return redirect(url_for('accounts.index', tab='staff'))
