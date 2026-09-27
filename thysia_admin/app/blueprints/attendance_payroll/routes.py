from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.blueprints.attendance_payroll import attendance_payroll_bp
from app.decorators import admin_required, log_action
from app.models import AttendanceLog, Payroll, Staff, ShiftHandover
from app.extensions import db
from datetime import datetime, date, timedelta
from sqlalchemy import func


@attendance_payroll_bp.route('/')
@login_required
@admin_required
def index():
    page = request.args.get('page', 1, type=int)
    tab = request.args.get('tab', 'attendance')
    today = date.today()

    attendance_logs = AttendanceLog.query.order_by(
        AttendanceLog.time_in.desc()
    ).paginate(page=page, per_page=20, error_out=False)

    staff_list = Staff.query.filter_by(status='active').all()
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

    return render_template('attendance_payroll/index.html',
                           attendance_logs=attendance_logs,
                           staff_list=staff_list,
                           payrolls=payrolls,
                           handovers=handovers,
                           tab=tab,
                           today=today,
                           today_on_time=today_on_time,
                           today_late=today_late,
                           today_total=today_total)


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

        hourly_rate = 75.0
        overtime_rate = hourly_rate * 1.25
        gross = (regular_hours * hourly_rate) + (overtime_hours * overtime_rate)
        deductions = gross * 0.1
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
    flash(f'Payroll generated for {generated} staff members.', 'success')
    return redirect(url_for('attendance_payroll.index', tab='payroll'))
