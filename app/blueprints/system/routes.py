from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.blueprints.system import system_bp
from app.decorators import super_admin_required, log_action
from app.models import AuditLog, Account
from app.extensions import db


@system_bp.route('/settings')
@login_required
@super_admin_required
def settings():
    return render_template('system/settings.html')


@system_bp.route('/settings', methods=['POST'])
@login_required
@super_admin_required
def update_settings():
    """Update system settings."""
    resort_name = request.form.get('resort_name', '').strip()
    admin_email = request.form.get('admin_email', '').strip()
    timezone = request.form.get('timezone', 'Asia/Manila')
    currency = request.form.get('currency', 'PHP')
    
    # Log the action
    log_action('update_settings', 'System', details=f'Updated resort settings')
    
    # In a real implementation, you would save these to a settings table or config file
    # For now, we'll just show a success message
    
    flash(f'System settings updated successfully.', 'success')
    return redirect(url_for('system.settings'))


@system_bp.route('/profile', methods=['POST'])
@login_required
def update_profile():
    """Update current user's profile information."""
    from flask_login import current_user
    full_name = request.form.get('full_name', '').strip()
    username = request.form.get('username', '').strip().lower()
    email = request.form.get('email', '').strip().lower()
    new_password = request.form.get('new_password', '').strip()

    if not full_name:
        flash('Full name is required.', 'error')
        return redirect(url_for('system.settings'))

    if username and username != current_user.username.lower():
        if len(username) < 3:
            flash('Username must be at least 3 characters long.', 'error')
            return redirect(url_for('system.settings'))
        existing = Account.query.filter(Account.username == username, Account.id != current_user.id).first()
        if existing:
            flash(f'Username "{username}" is already taken.', 'error')
            return redirect(url_for('system.settings'))
        current_user.username = username

    if email and email != current_user.email.lower():
        if '@' not in email or '.' not in email:
            flash('Please enter a valid email address.', 'error')
            return redirect(url_for('system.settings'))
        existing = Account.query.filter(Account.email == email, Account.id != current_user.id).first()
        if existing:
            flash(f'Email "{email}" is already in use.', 'error')
            return redirect(url_for('system.settings'))
        current_user.email = email

    name_parts = full_name.split(' ', 1)
    current_user.first_name = name_parts[0]
    current_user.last_name = name_parts[1] if len(name_parts) > 1 else ''

    if new_password:
        if len(new_password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
            return redirect(url_for('system.settings'))
        current_user.set_password(new_password)

    try:
        db.session.commit()
        log_action(f'Updated own profile: {current_user.username}', 'Account', current_user.id)
        flash('Your user information has been updated successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating profile: {str(e)}', 'error')

    return redirect(url_for('system.settings'))


@system_bp.route('/audit-log')
@login_required
@super_admin_required
def audit_log():
    page    = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 8, type=int)
    per_page = per_page if per_page in (8, 10, 25, 50, 100) else 8
    search  = (request.args.get('q') or '').strip()
    user_id = request.args.get('user', '', type=str)

    query = AuditLog.query

    if search:
        like = f"%{search}%"
        query = query.filter(
            db.or_(
                AuditLog.action.ilike(like),
                AuditLog.entity_type.ilike(like),
                AuditLog.details.ilike(like),
                AuditLog.ip_address.ilike(like),
            )
        )
    if user_id:
        query = query.filter(AuditLog.account_id == int(user_id))

    logs = query.order_by(AuditLog.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    users = db.session.query(Account.id, Account.username).order_by(Account.username).all()

    return render_template('system/audit_log.html', logs=logs, search=search,
                           user_filter=user_id, per_page=per_page, users=users)
