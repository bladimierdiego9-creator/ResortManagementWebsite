from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.blueprints.ai_concierge import ai_concierge_bp
from app.decorators import admin_required, log_action
from app.models import AIChatLog
from app.extensions import db
from datetime import datetime


@ai_concierge_bp.route('/')
@login_required
@admin_required
def index():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'escalated')

    query = AIChatLog.query.order_by(AIChatLog.created_at.desc())
    if status_filter == 'escalated':
        query = query.filter_by(escalated=True, resolved=False)
    elif status_filter == 'resolved':
        query = query.filter_by(resolved=True)

    pagination = query.paginate(page=page, per_page=15, error_out=False)
    logs = pagination.items

    unread_count = AIChatLog.query.filter_by(escalated=True, resolved=False).count()

    return render_template('ai_concierge/index.html',
                           logs=logs,
                           pagination=pagination,
                           status_filter=status_filter,
                           unread_count=unread_count)


@ai_concierge_bp.route('/<int:id>/reply', methods=['POST'])
@login_required
@admin_required
def reply(id):
    log = AIChatLog.query.get_or_404(id)
    admin_reply = request.form.get('admin_reply', '').strip()
    if admin_reply:
        log.admin_reply = admin_reply
        log.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Reply sent.', 'success')
    return redirect(url_for('ai_concierge.index'))


@ai_concierge_bp.route('/<int:id>/resolve', methods=['POST'])
@login_required
@admin_required
def resolve(id):
    log = AIChatLog.query.get_or_404(id)
    log.resolved = True
    log.updated_at = datetime.utcnow()
    db.session.commit()
    log_action('Resolved AI chat inquiry', 'AIChatLog', id)
    flash('Inquiry marked as resolved.', 'success')
    return redirect(url_for('ai_concierge.index'))
