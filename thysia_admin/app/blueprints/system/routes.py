from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.blueprints.system import system_bp
from app.decorators import super_admin_required, log_action
from app.models import AuditLog
from app.extensions import db


@system_bp.route('/settings')
@login_required
@super_admin_required
def settings():
    return render_template('system/settings.html')


@system_bp.route('/audit-log')
@login_required
@super_admin_required
def audit_log():
    page = request.args.get('page', 1, type=int)
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).paginate(
        page=page, per_page=30, error_out=False
    )
    return render_template('system/audit_log.html', logs=logs)
