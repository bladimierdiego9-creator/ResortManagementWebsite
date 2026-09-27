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
    facilities = Facility.query.order_by(Facility.name).all()
    return render_template('facilities/index.html', facilities=facilities)


@facilities_bp.route('/new', methods=['GET', 'POST'])
@login_required
@admin_required
def new():
    if request.method == 'POST':
        facility = Facility(
            name=request.form.get('name'),
            facility_type=request.form.get('facility_type'),
            capacity=int(request.form.get('capacity', 0)),
            price_per_hour=float(request.form.get('price_per_hour', 0)),
            price_whole_day=float(request.form.get('price_whole_day', 0)) if request.form.get('price_whole_day') else None,
            description=request.form.get('description', ''),
            status=request.form.get('status', 'available')
        )
        db.session.add(facility)
        db.session.commit()
        log_action('Created facility', 'Facility', facility.id)
        flash('Facility added successfully.', 'success')
        return redirect(url_for('facilities.index'))
    return render_template('facilities/index.html', facilities=Facility.query.all(), mode='new')


@facilities_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(id):
    facility = Facility.query.get_or_404(id)
    if request.method == 'POST':
        facility.name = request.form.get('name', facility.name)
        facility.facility_type = request.form.get('facility_type', facility.facility_type)
        facility.capacity = int(request.form.get('capacity', facility.capacity))
        facility.price_per_hour = float(request.form.get('price_per_hour', facility.price_per_hour))
        facility.price_whole_day = float(request.form.get('price_whole_day', 0)) if request.form.get('price_whole_day') else None
        facility.description = request.form.get('description', facility.description)
        facility.status = request.form.get('status', facility.status)
        db.session.commit()
        log_action('Updated facility', 'Facility', id)
        flash('Facility updated.', 'success')
        return redirect(url_for('facilities.index'))
    return render_template('facilities/index.html', facilities=Facility.query.all(), edit_facility=facility)


@facilities_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(id):
    facility = Facility.query.get_or_404(id)
    db.session.delete(facility)
    db.session.commit()
    log_action('Deleted facility', 'Facility', id)
    flash('Facility deleted.', 'success')
    return redirect(url_for('facilities.index'))
