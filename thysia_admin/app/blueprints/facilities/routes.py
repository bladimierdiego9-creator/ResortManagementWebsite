from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.blueprints.facilities import facilities_bp
from app.decorators import admin_required, log_action
from app.models import Facility
from app.extensions import db
from werkzeug.utils import secure_filename
import os
import uuid

# Configure upload settings
UPLOAD_FOLDER = 'app/static/uploads/facilities'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_facility_image(file):
    """Save uploaded facility image and return the URL path."""
    if file and allowed_file(file.filename):
        # Generate unique filename
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4()}.{ext}"
        
        # Ensure upload directory exists
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        
        # Save file
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        # Return web-accessible path
        return f"/static/uploads/facilities/{filename}"
    return None


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
        try:
            # Handle image upload
            image_url = None
            if 'image' in request.files:
                file = request.files['image']
                if file.filename:
                    image_url = save_facility_image(file)
            
            # Check if facility name already exists
            facility_name = request.form.get('facility_name', '').strip()
            existing = Facility.query.filter_by(facility_name=facility_name).first()
            if existing:
                flash(f'Facility name "{facility_name}" already exists. Please use a different name.', 'danger')
                return redirect(url_for('facilities.index'))
            
            facility = Facility(
                facility_name=facility_name,
                facility_type=request.form.get('facility_type', '').strip(),
                capacity=int(request.form.get('capacity', 0)),
                base_price=float(request.form.get('base_price', 0)),
                description=request.form.get('description', '').strip(),
                is_available=request.form.get('is_available', 'true') == 'true',
                image_url=image_url
            )
            db.session.add(facility)
            db.session.commit()
            log_action('Created facility', 'Facility', facility.id)
            flash('Facility added successfully.', 'success')
            return redirect(url_for('facilities.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding facility: {str(e)}', 'danger')
            return redirect(url_for('facilities.index'))
    return render_template('facilities/index.html', facilities=Facility.query.order_by(Facility.facility_name).all(), mode='new')


@facilities_bp.route('/<id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(id):
    facility = Facility.query.get_or_404(id)
    if request.method == 'POST':
        # Handle image upload
        if 'image' in request.files:
            file = request.files['image']
            if file.filename:
                new_image_url = save_facility_image(file)
                if new_image_url:
                    # Delete old image if exists
                    if facility.image_url:
                        old_path = os.path.join('app', facility.image_url.lstrip('/'))
                        if os.path.exists(old_path):
                            try:
                                os.remove(old_path)
                            except:
                                pass
                    facility.image_url = new_image_url
        
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
    # If GET request, just redirect to index (modal will handle the edit)
    return redirect(url_for('facilities.index'))


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
