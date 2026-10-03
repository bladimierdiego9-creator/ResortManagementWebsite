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
