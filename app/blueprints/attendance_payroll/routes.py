from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required
from app.blueprints.attendance_payroll import attendance_payroll_bp
from app.decorators import admin_required, log_action
from app.models import AttendanceLog, Payroll, Staff, ShiftHandover, RFIDCard, Account
from app.extensions import db
from datetime import datetime, date, timedelta, time
from sqlalchemy import func
import hmac


@attendance_payroll_bp.route('/')
@login_required
@admin_required
def index():
    tab = request.args.get('tab', 'attendance')
    if tab not in ('attendance', 'rfid', 'payroll'):
        tab = 'attendance'

    today = date.today()
    page = request.args.get('page', 1, type=int)

    # Attendance logs (for attendance tab)
    attendance_logs = AttendanceLog.query.order_by(
        AttendanceLog.time_in.desc()
    ).paginate(page=page, per_page=10, error_out=False)

    staff_list = Staff.query.filter_by(status='active').order_by(Staff.full_name).all()
    payrolls = Payroll.query.order_by(Payroll.created_at.desc()).limit(20).all()
    handovers = ShiftHandover.query.order_by(
        ShiftHandover.created_at.desc()
    ).limit(10).all()

    today_on_time = AttendanceLog.query.filter(
        func.date(AttendanceLog.time_in) == today,
        AttendanceLog.status == 'on_time'
    ).count()
    today_late = AttendanceLog.query.filter(
        func.date(AttendanceLog.time_in) == today,
        AttendanceLog.status == 'late'
    ).count()
    today_total = today_on_time + today_late

    # ── RFID Cards Tab Query, Filtering & Sorting ────────────────────────
    q = request.args.get('q', '').strip()
    status_filter = request.args.get('status', 'all').strip().lower()
    sort_by = request.args.get('sort', 'uid').strip().lower()
    sort_order = request.args.get('order', 'asc').strip().lower()
    rfid_page = request.args.get('page', 1, type=int) if tab == 'rfid' else 1

    rfid_query = RFIDCard.query.outerjoin(Staff, Staff.id == RFIDCard.staff_id)

    if q:
        like = f"%{q}%"
        rfid_query = rfid_query.filter(
            db.or_(
                RFIDCard.card_uid.ilike(like),
                RFIDCard.notes.ilike(like),
                Staff.full_name.ilike(like),
                Staff.role.ilike(like),
                Staff.shift.ilike(like)
            )
        )

    if status_filter in ('active', 'inactive', 'blocked'):
        rfid_query = rfid_query.filter(RFIDCard.status == status_filter)
    elif status_filter == 'unassigned':
        rfid_query = rfid_query.filter(RFIDCard.staff_id.is_(None))
    elif status_filter == 'assigned':
        rfid_query = rfid_query.filter(RFIDCard.staff_id.isnot(None))

    is_desc = (sort_order == 'desc')
    if sort_by == 'owner':
        order_col = Staff.full_name.desc() if is_desc else Staff.full_name.asc()
    elif sort_by == 'status':
        order_col = RFIDCard.status.desc() if is_desc else RFIDCard.status.asc()
    elif sort_by == 'role':
        order_col = Staff.role.desc() if is_desc else Staff.role.asc()
    elif sort_by == 'shift':
        order_col = Staff.shift.desc() if is_desc else Staff.shift.asc()
    elif sort_by == 'last_used':
        order_col = RFIDCard.last_used_at.desc() if is_desc else RFIDCard.last_used_at.asc()
    elif sort_by == 'date':
        order_col = RFIDCard.created_at.desc() if is_desc else RFIDCard.created_at.asc()
    else:  # uid
        order_col = RFIDCard.card_uid.desc() if is_desc else RFIDCard.card_uid.asc()

    rfid_query = rfid_query.order_by(order_col)
    rfid_cards = rfid_query.paginate(page=rfid_page, per_page=12, error_out=False)

    total_rfid = RFIDCard.query.count()
    active_rfid = RFIDCard.query.filter_by(status='active').count()
    assigned_rfid = RFIDCard.query.filter(RFIDCard.staff_id.isnot(None)).count()
    unassigned_rfid = RFIDCard.query.filter(RFIDCard.staff_id.is_(None)).count()

    return render_template('attendance_payroll/index.html',
                           attendance_logs=attendance_logs,
                           staff_list=staff_list,
                           payrolls=payrolls,
                           handovers=handovers,
                           tab=tab,
                           today=today,
                           today_on_time=today_on_time,
                           today_late=today_late,
                           today_total=today_total,
                           rfid_cards=rfid_cards,
                           total_rfid=total_rfid,
                           active_rfid=active_rfid,
                           assigned_rfid=assigned_rfid,
                           unassigned_rfid=unassigned_rfid,
                           q=q,
                           status_filter=status_filter,
                           sort_by=sort_by,
                           sort_order=sort_order)


@attendance_payroll_bp.route('/api/rfid/scan', methods=['POST'])
def device_rfid_scan():
    """Authenticated ESP32 endpoint; writes into the existing attendance system."""
    expected_token = current_app.config.get('RFID_DEVICE_TOKEN', '')
    supplied_token = request.headers.get('X-Device-Token', '')
    if not expected_token or not hmac.compare_digest(supplied_token, expected_token):
        return jsonify(ok=False, message='Unauthorized device'), 401

    payload = request.get_json(silent=True) or {}
    card_uid = str(payload.get('uid', '')).strip().upper()
    if not card_uid or len(card_uid) > 64:
        return jsonify(ok=False, message='Invalid UID'), 400

    card = RFIDCard.query.filter_by(card_uid=card_uid).first()
    if not card:
        staff = Staff.query.filter_by(rfid_tag=card_uid).first()
        if staff:
            card = RFIDCard(card_uid=card_uid, staff_id=staff.id, status='active')
            db.session.add(card)
            db.session.flush()
        else:
            return jsonify(ok=False, message='Card is not registered'), 404
    if card.status != 'active':
        return jsonify(ok=False, message=f'Card is {card.status}'), 403
    if not card.staff or card.staff.status != 'active':
        return jsonify(ok=False, message='Card is not assigned to active staff'), 403

    staff = card.staff
    now = datetime.now()
    today = now.date()
    try:
        open_log = AttendanceLog.query.filter(
            AttendanceLog.staff_id == staff.id,
            func.date(AttendanceLog.time_in) == today,
            AttendanceLog.time_out.is_(None)
        ).order_by(AttendanceLog.time_in.desc()).first()
        if open_log:
            open_log.time_out = now
            open_log.rfid_tap_out = card_uid
            action = 'CLOCK_OUT'
        else:
            expected_hour = 8 if staff.shift == 'morning' else (14 if staff.shift == 'afternoon' else 20)
            expected_time = datetime.combine(today, time(expected_hour, 0))
            status = 'late' if now > expected_time + timedelta(minutes=15) else 'on_time'
            db.session.add(AttendanceLog(
                staff_id=staff.id, time_in=now, status=status,
                rfid_tap_in=card_uid, notes=f'ESP32 RFID tap in via Card {card_uid}'
            ))
            action = 'CLOCK_IN'
        card.last_used_at = now
        db.session.commit()
        return jsonify(ok=True, action=action, name=staff.full_name, time=now.isoformat(timespec='seconds'))
    except Exception:
        db.session.rollback()
        current_app.logger.exception('ESP32 RFID attendance write failed')
        return jsonify(ok=False, message='Could not save attendance'), 500


@attendance_payroll_bp.route('/rfid')
@login_required
@admin_required
def rfid_management():
    """Direct route for RFID card management page."""
    return redirect(url_for('attendance_payroll.index', tab='rfid'))


# ── RFID CARD REGISTRATION & MANAGEMENT ─────────────────────────────────────

@attendance_payroll_bp.route('/rfid/register', methods=['POST'])
@login_required
@admin_required
def register_rfid():
    card_uid = request.form.get('card_uid', '').strip().upper()
    staff_id = request.form.get('staff_id', '').strip()
    status = request.form.get('status', 'active').strip().lower()
    notes = request.form.get('notes', '').strip() or None

    if not card_uid:
        flash('Card Tag UID is required.', 'error')
        return redirect(url_for('attendance_payroll.index', tab='rfid'))

    if status not in ('active', 'inactive', 'blocked'):
        status = 'active'

    existing = RFIDCard.query.filter_by(card_uid=card_uid).first()
    if existing:
        flash(f'RFID card with Tag UID "{card_uid}" is already registered.', 'error')
        return redirect(url_for('attendance_payroll.index', tab='rfid'))

    target_staff = None
    if staff_id and staff_id != '0':
        try:
            target_staff = Staff.query.get(int(staff_id))
        except (ValueError, TypeError):
            pass

    try:
        if target_staff:
            # If target staff already has another card, unassign that card first
            old_card = RFIDCard.query.filter_by(staff_id=target_staff.id).first()
            if old_card:
                old_card.staff_id = None
            target_staff.rfid_tag = card_uid
            if target_staff.account:
                target_staff.account.rfid_tag = card_uid

        new_card = RFIDCard(
            card_uid=card_uid,
            staff_id=target_staff.id if target_staff else None,
            status=status,
            notes=notes
        )
        db.session.add(new_card)
        db.session.commit()
        log_action(f"Registered RFID card: {card_uid}", "RFIDCard", new_card.id)
        owner_msg = f" and assigned to {target_staff.full_name}" if target_staff else " (Unassigned)"
        flash(f'RFID Card "{card_uid}" registered successfully{owner_msg}.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error registering RFID card: {str(e)}', 'error')

    return redirect(url_for('attendance_payroll.index', tab='rfid'))


@attendance_payroll_bp.route('/rfid/lookup')
@login_required
@admin_required
def lookup_rfid():
    """Check whether a scanned UID is already registered."""
    card_uid = request.args.get('card_uid', '').strip().upper()
    if not card_uid:
        return jsonify({'error': 'Card UID is required.'}), 400

    card = RFIDCard.query.filter_by(card_uid=card_uid).first()
    if not card:
        return jsonify({'found': False})

    return jsonify({
        'found': True,
        'id': card.id,
        'card_uid': card.card_uid,
        'status': card.status,
        'owner': card.owner_name,
        'reactivate_url': url_for('attendance_payroll.reactivate_rfid', id=card.id),
    })


@attendance_payroll_bp.route('/rfid/<int:id>/reactivate', methods=['POST'])
@login_required
@admin_required
def reactivate_rfid(id):
    """Reactivate an inactive RFID card from the registration flow."""
    card = RFIDCard.query.get_or_404(id)
    if card.status != 'inactive':
        return jsonify({'error': 'Only inactive cards can be reactivated.'}), 409

    try:
        card.status = 'active'
        if card.staff:
            card.staff.rfid_tag = card.card_uid
            if card.staff.account:
                card.staff.account.rfid_tag = card.card_uid
        db.session.commit()
        log_action(f'Reactivated RFID card: {card.card_uid}', 'RFIDCard', card.id)
        return jsonify({'success': True, 'card_uid': card.card_uid})
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Unable to reactivate RFID card %s', id)
        return jsonify({'error': 'Could not reactivate this card. Please try again.'}), 500


@attendance_payroll_bp.route('/rfid/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_rfid(id):
    card = RFIDCard.query.get_or_404(id)
    card_uid = request.form.get('card_uid', '').strip().upper()
    staff_id = request.form.get('staff_id', '').strip()
    status = request.form.get('status', card.status).strip().lower()
    notes = request.form.get('notes', '').strip() or None

    if not card_uid:
        flash('Card Tag UID is required.', 'error')
        return redirect(url_for('attendance_payroll.index', tab='rfid'))

    if status not in ('active', 'inactive', 'blocked'):
        status = card.status

    if card_uid != card.card_uid:
        existing = RFIDCard.query.filter(RFIDCard.card_uid == card_uid, RFIDCard.id != id).first()
        if existing:
            flash(f'RFID card with Tag UID "{card_uid}" is already registered.', 'error')
            return redirect(url_for('attendance_payroll.index', tab='rfid'))

    target_staff = None
    if staff_id and staff_id != '0':
        try:
            target_staff = Staff.query.get(int(staff_id))
        except (ValueError, TypeError):
            pass

    try:
        old_staff = card.staff
        old_uid = card.card_uid

        # Handle owner change
        if old_staff and old_staff != target_staff:
            if old_staff.rfid_tag == old_uid:
                old_staff.rfid_tag = None
            if old_staff.account and old_staff.account.rfid_tag == old_uid:
                old_staff.account.rfid_tag = None

        if target_staff:
            # Unassign other card previously assigned to target staff if any
            other_card = RFIDCard.query.filter(RFIDCard.staff_id == target_staff.id, RFIDCard.id != card.id).first()
            if other_card:
                other_card.staff_id = None
            target_staff.rfid_tag = card_uid
            if target_staff.account:
                target_staff.account.rfid_tag = card_uid
            card.staff_id = target_staff.id
        else:
            card.staff_id = None

        card.card_uid = card_uid
        card.status = status
        card.notes = notes
        db.session.commit()
        log_action(f"Updated RFID card: {card_uid}", "RFIDCard", id)
        flash(f'RFID Card "{card_uid}" updated successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating RFID card: {str(e)}', 'error')

    return redirect(url_for('attendance_payroll.index', tab='rfid'))


@attendance_payroll_bp.route('/rfid/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_rfid(id):
    card = RFIDCard.query.get_or_404(id)
    uid = card.card_uid
    try:
        if card.staff:
            if card.staff.rfid_tag == card.card_uid:
                card.staff.rfid_tag = None
            if card.staff.account and card.staff.account.rfid_tag == card.card_uid:
                card.staff.account.rfid_tag = None

        db.session.delete(card)
        db.session.commit()
        log_action(f"Deleted RFID card: {uid}", "RFIDCard", id)
        flash(f'RFID Card "{uid}" removed successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting RFID card: {str(e)}', 'error')

    return redirect(url_for('attendance_payroll.index', tab='rfid'))


@attendance_payroll_bp.route('/rfid/tap', methods=['POST'])
@login_required
@admin_required
def tap_rfid():
    """Simulate or process an RFID tap for staff attendance (Clock In / Clock Out)."""
    card_uid = request.form.get('card_uid', '').strip().upper()
    if not card_uid:
        flash('Please provide or scan an RFID Tag UID.', 'error')
        return redirect(url_for('attendance_payroll.index', tab='rfid'))

    card = RFIDCard.query.filter_by(card_uid=card_uid).first()
    if not card:
        staff = Staff.query.filter_by(rfid_tag=card_uid).first()
        if staff:
            card = RFIDCard(card_uid=card_uid, staff_id=staff.id, status='active')
            db.session.add(card)
            db.session.flush()
        else:
            flash(f'Unrecognized RFID card "{card_uid}". Card is not registered.', 'error')
            return redirect(url_for('attendance_payroll.index', tab='rfid'))

    if card.status == 'blocked':
        flash(f'Access Denied: RFID Card "{card_uid}" is BLOCKED / SUSPENDED.', 'error')
        return redirect(url_for('attendance_payroll.index', tab='rfid'))

    if card.status == 'inactive':
        flash(f'Access Denied: RFID Card "{card_uid}" is marked INACTIVE.', 'error')
        return redirect(url_for('attendance_payroll.index', tab='rfid'))

    if not card.staff:
        flash(f'RFID Card "{card_uid}" is UNASSIGNED. Please assign it to a staff member first.', 'error')
        return redirect(url_for('attendance_payroll.index', tab='rfid'))

    staff = card.staff
    today = date.today()
    now = datetime.now()

    try:
        # Check if staff has an open attendance record today (clocked in without clock out)
        open_log = AttendanceLog.query.filter(
            AttendanceLog.staff_id == staff.id,
            func.date(AttendanceLog.time_in) == today,
            AttendanceLog.time_out.is_(None)
        ).order_by(AttendanceLog.time_in.desc()).first()

        if open_log:
            # CLOCK OUT
            open_log.time_out = now
            open_log.rfid_tap_out = card_uid
            card.last_used_at = now

            duration_secs = (now - open_log.time_in).total_seconds()
            hrs = int(duration_secs // 3600)
            mins = int((duration_secs % 3600) // 60)
            log_action(f"RFID Attendance Clock-Out: {staff.full_name} ({card_uid})", "AttendanceLog", open_log.id)
            db.session.commit()
            flash(f'CLOCKED OUT: {staff.full_name} ({staff.role.replace("_", " ").title()}) at {now.strftime("%I:%M %p")}. Total shift duration: {hrs}h {mins}m.', 'success')
        else:
            # CLOCK IN
            # Shift schedule check:
            # Morning: 08:00, Afternoon: 14:00, Evening: 20:00
            expected_hour = 8 if staff.shift == 'morning' else (14 if staff.shift == 'afternoon' else 20)
            expected_time = datetime.combine(today, time(expected_hour, 0))
            is_late = now > expected_time + timedelta(minutes=15)
            status = 'late' if is_late else 'on_time'

            new_log = AttendanceLog(
                staff_id=staff.id,
                time_in=now,
                status=status,
                rfid_tap_in=card_uid,
                notes=f"RFID tap in via Card {card_uid}"
            )
            db.session.add(new_log)
            card.last_used_at = now
            db.session.flush()
            log_action(f"RFID Attendance Clock-In: {staff.full_name} ({card_uid})", "AttendanceLog", new_log.id)
            db.session.commit()
            status_label = "On Time" if status == 'on_time' else "Late"
            category = 'success' if status == 'on_time' else 'warning'
            flash(f'CLOCKED IN: {staff.full_name} ({staff.role.replace("_", " ").title()}) at {now.strftime("%I:%M %p")} — {status_label}.', category)
    except Exception as e:
        db.session.rollback()
        flash(f'Error processing RFID attendance tap: {str(e)}', 'error')

    return redirect(url_for('attendance_payroll.index', tab='rfid'))


@attendance_payroll_bp.route('/generate-payroll', methods=['POST'])
@login_required
@admin_required
def generate_payroll():
    period_start = request.form.get('period_start')
    period_end = request.form.get('period_end')

    try:
        start = datetime.strptime(period_start, '%Y-%m-%d').date()
        end = datetime.strptime(period_end, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        flash('Invalid date range.', 'error')
        return redirect(url_for('attendance_payroll.index', tab='payroll'))

    staff_list = Staff.query.filter_by(status='active').all()
    generated = 0

    for staff in staff_list:
        logs = AttendanceLog.query.filter(
            AttendanceLog.staff_id == staff.id,
            func.date(AttendanceLog.time_in) >= start,
            func.date(AttendanceLog.time_in) <= end,
            AttendanceLog.time_out != None
        ).all()

        regular_hours = 0
        overtime_hours = 0
        for log in logs:
            if log.time_out:
                duration = (log.time_out - log.time_in).total_seconds() / 3600
                if duration > 8:
                    regular_hours += 8
                    overtime_hours += duration - 8
                else:
                    regular_hours += duration

        # TODO: Replace with per-staff hourly_rate from Staff model or a
        # PayrollConfig table. Payroll generation is disabled until real
        # rates are configured — no record is saved for this staff member.
        hourly_rate = getattr(staff, 'hourly_rate', None)
        if not hourly_rate:
            continue

        overtime_rate = hourly_rate * 1.5  # standard OT multiplier
        gross = (regular_hours * hourly_rate) + (overtime_hours * overtime_rate)

        # TODO: Replace with real statutory deductions (SSS, PhilHealth,
        # Pag-IBIG, withholding tax) from a DeductionConfig table.
        deductions = 0.0
        net = gross - deductions

        payroll = Payroll(
            staff_id=staff.id,
            pay_period_start=start,
            pay_period_end=end,
            regular_hours=round(regular_hours, 2),
            overtime_hours=round(overtime_hours, 2),
            hourly_rate=hourly_rate,
            overtime_rate=overtime_rate,
            gross_pay=round(gross, 2),
            deductions=round(deductions, 2),
            net_pay=round(net, 2),
            status='generated',
            generated_at=datetime.utcnow()
        )
        db.session.add(payroll)
        generated += 1

    db.session.commit()
    log_action(f'Generated payroll for {generated} staff members', 'Payroll')
    skipped = len(staff_list) - generated
    msg = f'Payroll generated for {generated} staff member(s).'
    if skipped:
        msg += f' {skipped} skipped (no hourly rate configured).'
    flash(msg, 'success' if generated else 'warning')
    return redirect(url_for('attendance_payroll.index', tab='payroll'))
