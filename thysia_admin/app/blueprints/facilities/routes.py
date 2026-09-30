from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.blueprints.facilities import facilities_bp
from app.decorators import admin_required, log_action
from app.models import Facility
from app.extensions import db


@facilities_bp.route('/')
@login_required
@admin_required
def index():
    facilities = Facility.query.order_by(Facility.facility_name).all()
    return render_template('facilities/index.html', facilities=facilities)


@facilities_bp.route('/new', methods=['GET', 'POST'])
@login_required
@admin_required
def new():
    if request.method == 'POST':
        facility = Facility(
            facility_name=request.form.get('facility_name', '').strip(),
            facility_type=request.form.get('facility_type', '').strip(),
            capacity=int(request.form.get('capacity', 0)),
            base_price=float(request.form.get('base_price', 0)),
            description=request.form.get('description', '').strip(),
            is_available=request.form.get('is_available', 'true') == 'true',
        )
        db.session.add(facility)
        db.session.commit()
        log_action('Created facility', 'Facility', facility.id)
        flash('Facility added successfully.', 'success')
        return redirect(url_for('facilities.index'))
    return render_template('facilities/index.html', facilities=Facility.query.order_by(Facility.facility_name).all(), mode='new')


@facilities_bp.route('/<id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(id):
    facility = Facility.query.get_or_404(id)
    if request.method == 'POST':
        facility.facility_name = request.form.get('facility_name', facility.facility_name).strip()
        facility.facility_type = request.form.get('facility_type', facility.facility_type).strip()
        facility.capacity      = int(request.form.get('capacity', facility.capacity or 0))
        facility.base_price    = float(request.form.get('base_price', facility.base_price))
        facility.description   = request.form.get('description', facility.description or '').strip()
        facility.is_available  = request.form.get('is_available', 'true') == 'true'
        db.session.commit()
        log_action('Updated facility', 'Facility', id)
        flash('Facility updated.', 'success')
        return redirect(url_for('facilities.index'))
    return render_template('facilities/index.html',
                           facilities=Facility.query.order_by(Facility.facility_name).all(),
                           edit_facility=facility)


@facilities_bp.route('/<id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(id):
    facility = Facility.query.get_or_404(id)
    db.session.delete(facility)
    db.session.commit()
    log_action('Deleted facility', 'Facility', id)
    flash('Facility deleted.', 'success')
    return redirect(url_for('facilities.index'))
