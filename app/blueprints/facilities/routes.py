"""Facilities management.

Every value on the Facilities page comes from the ``facilities`` table — the
page has no hardcoded content.  Photos are converted to base64 and stored in the
database (``image_data`` / ``image_filename`` / ``image_mimetype``); nothing is
written to the filesystem.  Pages display a photo by calling its URL::

    GET /facilities/<id>/image     ->  facilities.image

``Facility.image_url`` already builds that URL, so a template only needs::

    <img src="{{ facility.image_url }}">
"""

import base64
import io
import re
import time

from flask import (
    abort, current_app, flash, redirect, render_template, request, send_file, url_for,
)
from flask_login import login_required
from sqlalchemy import String, cast, delete as sa_delete, func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import undefer
from werkzeug.utils import secure_filename

from app.blueprints.facilities import facilities_bp
from app.decorators import admin_required, log_action
from app.extensions import db
from app.models import Facility, FacilityAvailability

# Fallback list used only when the database does not expose a facility_type
# CHECK constraint (e.g. the SQLite fallback).  On Postgres the constraint is the
# source of truth, so the form can never offer a type the database will reject.
DEFAULT_FACILITY_TYPES = ('full_resort', 'pavilion', 'pool', 'room')

# Cache of {database url: (allowed types or None, fetched_at)} — reading the
# constraint costs one query, and the short TTL lets a schema change take effect
# without restarting the server.
_ALLOWED_TYPES_CACHE = {}
_ALLOWED_TYPES_TTL = 300  # seconds

# Magic byte prefixes used to reject files that only claim to be images.
IMAGE_SIGNATURES = (
    (b'\xff\xd8\xff', 'image/jpeg'),
    (b'\x89PNG\r\n\x1a\n', 'image/png'),
    (b'GIF87a', 'image/gif'),
    (b'GIF89a', 'image/gif'),
    (b'RIFF', 'image/webp'),
)

# Photos are shrunk to this size before being stored (Pillow).  When Pillow is
# not installed the original file is stored as-is, up to MAX_STORED_IMAGE_BYTES.
IMAGE_MAX_SIDE = 1600
IMAGE_JPEG_QUALITY = 82
MAX_STORED_IMAGE_BYTES = 6 * 1024 * 1024

# Cache lifetime of the served photos (seconds).  The URL carries a ?v= stamp of
# the facility's updated_at, so a new photo is fetched immediately.
IMAGE_CACHE_SECONDS = 60 * 60 * 24 * 30


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def allowed_facility_types():
    """Types the database itself accepts, taken from its CHECK constraint.

    Returns ``None`` when no such constraint is visible (SQLite, or a database
    where the constraint is missing).
    """
    cache_key = str(db.engine.url)
    cached = _ALLOWED_TYPES_CACHE.get(cache_key)
    if cached and (time.monotonic() - cached[1]) < _ALLOWED_TYPES_TTL:
        return cached[0]

    values = None
    try:
        definitions = db.session.execute(text(
            "select pg_get_constraintdef(oid) from pg_constraint "
            "where conrelid = 'facilities'::regclass and contype = 'c'"
        )).scalars().all()
        for definition in definitions:
            if 'facility_type' not in (definition or ''):
                continue
            found = sorted(set(re.findall(r"'([^']+)'::text", definition)))
            if found:
                values = found
                break
    except Exception:
        values = None  # not Postgres — fall back to the built-in list

    _ALLOWED_TYPES_CACHE[cache_key] = (values, time.monotonic())
    return values


def facility_types():
    """Form options: what the database accepts, plus every stored type."""
    stored = {
        (row[0] or '').strip()
        for row in db.session.query(Facility.facility_type).distinct().all()
    }
    options = list(allowed_facility_types() or DEFAULT_FACILITY_TYPES)
    options += sorted(t for t in stored if t and t not in options)
    return options


def db_error_message(exc):
    """Short, non-technical reason for a database failure."""
    detail = str(getattr(exc, 'orig', exc)).split('\n')[0]
    lowered = detail.lower()
    if 'check constraint' in lowered or 'checkviolation' in lowered:
        return ('the database rejected one of the values (an allowed list is enforced '
                'on facility type) — pick a type from the list.')
    if 'duplicate key' in lowered or 'uniqueviolation' in lowered:
        return 'another facility already uses that name.'
    return detail[:200]


def sniff_mimetype(header):
    """Mimetype guessed from the file's magic bytes, or None."""
    for signature, mimetype in IMAGE_SIGNATURES:
        if header.startswith(signature):
            return mimetype
    return None


def shrink_image(raw_bytes, mimetype):
    """Downscale/re-compress a photo when Pillow is available.

    Returns ``(raw_bytes, mimetype)`` — unchanged when Pillow is missing or the
    image cannot be processed.
    """
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return raw_bytes, mimetype

    try:
        with Image.open(io.BytesIO(raw_bytes)) as image:
            image = ImageOps.exif_transpose(image)
            if image.mode in ('RGBA', 'LA', 'P') and mimetype != 'image/gif':
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.convert('RGBA').split()[-1])
                image = background
            elif image.mode not in ('RGB', 'L'):
                image = image.convert('RGB')

            if max(image.size) > IMAGE_MAX_SIDE:
                image.thumbnail((IMAGE_MAX_SIDE, IMAGE_MAX_SIDE), Image.LANCZOS)

            buffer = io.BytesIO()
            image.save(buffer, format='JPEG', quality=IMAGE_JPEG_QUALITY, optimize=True)
            return buffer.getvalue(), 'image/jpeg'
    except Exception as exc:  # unsupported/corrupt file — fall back to the original
        current_app.logger.info('Image not re-encoded (%s); storing it as uploaded.', exc)
        return raw_bytes, mimetype


def prepare_image(file_storage):
    """Validate an upload and turn it into database fields.

    Returns ``(fields, error)`` where ``fields`` is a dict with ``image_data``
    (base64), ``image_filename`` and ``image_mimetype``.
    """
    if not file_storage or not (file_storage.filename or '').strip():
        return None, None

    original = secure_filename(file_storage.filename) or 'photo'
    extension = original.rsplit('.', 1)[-1].lower() if '.' in original else ''
    allowed = current_app.config.get('ALLOWED_EXTENSIONS') or {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    if extension not in allowed:
        return None, (
            f'"{file_storage.filename}" is not a supported image. '
            f'Allowed types: {", ".join(sorted(allowed))}.'
        )

    raw_bytes = file_storage.stream.read()
    file_storage.stream.seek(0)
    if not raw_bytes:
        return None, f'"{file_storage.filename}" is empty.'

    mimetype = sniff_mimetype(raw_bytes[:16])
    if not mimetype:
        return None, f'"{file_storage.filename}" does not look like a valid image file.'

    raw_bytes, mimetype = shrink_image(raw_bytes, mimetype)

    if len(raw_bytes) > MAX_STORED_IMAGE_BYTES:
        limit_mb = MAX_STORED_IMAGE_BYTES // (1024 * 1024)
        return None, (
            f'"{file_storage.filename}" is too large to store ({len(raw_bytes) // 1024} KB). '
            f'Maximum is {limit_mb} MB — try a smaller photo.'
        )

    extension = {'image/jpeg': 'jpg', 'image/png': 'png',
                 'image/gif': 'gif', 'image/webp': 'webp'}.get(mimetype, extension)
    stored_name = f'{original.rsplit(".", 1)[0] or "photo"}.{extension}'

    return {
        'image_data': base64.b64encode(raw_bytes).decode('ascii'),
        'image_filename': stored_name[:256],
        'image_mimetype': mimetype,
    }, None


def form_values():
    """Snapshot of the submitted form so a validation error can be redisplayed."""
    return {
        'facility_name': (request.form.get('facility_name') or '').strip(),
        'facility_type': (request.form.get('facility_type') or '').strip(),
        'capacity': (request.form.get('capacity') or '').strip(),
        'base_price': (request.form.get('base_price') or '').strip(),
        'description': (request.form.get('description') or '').strip(),
        'is_available': request.form.get('is_available', 'true') == 'true',
    }


def validate_form(facility=None):
    """Validate a create/update submission.  Returns ``(values, error)``."""
    values = form_values()

    name = values['facility_name']
    if not name:
        return None, 'Facility name is required.'
    if len(name) > 120:
        return None, 'Facility name must be 120 characters or fewer.'

    facility_type = values['facility_type']
    if not facility_type:
        return None, 'Please choose a facility type.'

    allowed_options = facility_types()
    if facility_type not in allowed_options:
        return None, (
            f'"{facility_type}" is not a facility type this database accepts. '
            f'Choose one of: {", ".join(allowed_options)}.'
        )

    try:
        capacity = int(values['capacity'])
    except (TypeError, ValueError):
        return None, 'Capacity must be a whole number.'
    if capacity < 1:
        return None, 'Capacity must be at least 1.'

    try:
        base_price = float(values['base_price'])
    except (TypeError, ValueError):
        return None, 'Base price must be a number.'
    if base_price < 0:
        return None, 'Base price cannot be negative.'

    duplicate = Facility.query.filter(
        func.lower(Facility.facility_name) == name.lower()
    )
    if facility is not None:
        duplicate = duplicate.filter(Facility.id != facility.id)
    if duplicate.first() is not None:
        return None, f'A facility named "{name}" already exists.'

    return {
        'facility_name': name,
        'facility_type': facility_type,
        'capacity': capacity,
        'base_price': base_price,
        'description': values['description'],
        'is_available': values['is_available'],
    }, None


def clear_availability_slots(facility_id):
    """Drop booked/blocked slots that belong to a facility.

    ``cast(..., String)`` keeps this working on both Postgres (where the column
    is an integer) and SQLite (where it is text).
    """
    db.session.execute(
        sa_delete(FacilityAvailability).where(
            cast(FacilityAvailability.facility_id, String) == str(facility_id)
        )
    )


def render_index(**overrides):
    """Render the facilities page straight from the database."""
    context = {
        'facilities': Facility.query.order_by(Facility.facility_name).all(),
        'facility_types': facility_types(),
        'open_modal': None,
        'edit_id': None,
        'form_values': None,
        'total_count': Facility.query.count(),
        'available_count': Facility.query.filter_by(is_available=True).count(),
    }
    context.update(overrides)
    return render_template('facilities/index.html', **context)


# --------------------------------------------------------------------------- #
# routes
# --------------------------------------------------------------------------- #
@facilities_bp.route('/')
@login_required
@admin_required
def index():
    # Check if viewing archived
    view_archived = request.args.get('archived') == 'true'
    
    if view_archived:
        facilities = Facility.query.filter_by(archived=True).order_by(Facility.facility_name).all()
    else:
        facilities = Facility.query.filter_by(archived=False).order_by(Facility.facility_name).all()
    
    total_count = Facility.query.filter_by(archived=False).count()
    available_count = Facility.query.filter_by(archived=False, is_available=True).count()
    archived_count = Facility.query.filter_by(archived=True).count()
    
    return render_index(
        facilities=facilities,
        view_archived=view_archived,
        total_count=total_count,
        available_count=available_count,
        archived_count=archived_count
    )


@facilities_bp.route('/<id>/image')
def image(id):
    """Stream a facility photo straight out of the database.

    Public on purpose: the guest-facing website can simply use
    ``<img src="/facilities/<id>/image">``.
    """
    facility = Facility.query.options(undefer(Facility.image_data)).get_or_404(id)
    raw_bytes = facility.image_bytes
    if not raw_bytes:
        abort(404)

    response = send_file(
        io.BytesIO(raw_bytes),
        mimetype=facility.image_mimetype or 'image/jpeg',
        download_name=facility.image_filename or f'{facility.id}',
        max_age=IMAGE_CACHE_SECONDS,
    )
    response.headers['Cache-Control'] = f'public, max-age={IMAGE_CACHE_SECONDS}'
    return response


@facilities_bp.route('/new', methods=['GET', 'POST'])
@login_required
@admin_required
def new():
    if request.method == 'GET':
        return render_index(open_modal='addFacilityModal')

    values, error = validate_form()
    if error:
        flash(error, 'danger')
        return render_index(open_modal='addFacilityModal', form_values=form_values())

    image_fields, error = prepare_image(request.files.get('image'))
    if error:
        flash(error, 'danger')
        return render_index(open_modal='addFacilityModal', form_values=form_values())

    facility = Facility(**values, **(image_fields or {}))
    try:
        db.session.add(facility)
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        current_app.logger.warning('Facility insert rejected by the database: %s', exc)
        flash(f'Could not save the facility: {db_error_message(exc)}', 'danger')
        return render_index(open_modal='addFacilityModal', form_values=form_values())
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception('Could not create facility')
        flash(f'Could not save the facility: {db_error_message(exc)}', 'danger')
        return render_index(open_modal='addFacilityModal', form_values=form_values())

    log_action('Created facility', 'Facility', facility.id,
               f'Added facility "{facility.facility_name}"')
    flash(f'Facility "{facility.facility_name}" added successfully.', 'success')
    return redirect(url_for('facilities.index'))


@facilities_bp.route('/<id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(id):
    facility = Facility.query.get_or_404(id)

    if request.method == 'GET':
        return render_index(open_modal='editFacilityModal', edit_id=str(facility.id))

    values, error = validate_form(facility)
    if error:
        flash(error, 'danger')
        return render_index(open_modal='editFacilityModal', edit_id=str(facility.id),
                            form_values=form_values())

    image_fields, error = prepare_image(request.files.get('image'))
    if error:
        flash(error, 'danger')
        return render_index(open_modal='editFacilityModal', edit_id=str(facility.id),
                            form_values=form_values())

    remove_image = request.form.get('remove_image') in ('true', 'on', 'yes')

    for field, value in values.items():
        setattr(facility, field, value)
    if image_fields:
        for field, value in image_fields.items():
            setattr(facility, field, value)
    elif remove_image:
        facility.image_data = None
        facility.image_filename = None
        facility.image_mimetype = None

    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        current_app.logger.warning('Facility update rejected by the database: %s', exc)
        flash(f'Could not update the facility: {db_error_message(exc)}', 'danger')
        return render_index(open_modal='editFacilityModal', edit_id=str(facility.id),
                            form_values=form_values())
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception('Could not update facility %s', id)
        flash(f'Could not update the facility: {db_error_message(exc)}', 'danger')
        return render_index(open_modal='editFacilityModal', edit_id=str(facility.id),
                            form_values=form_values())

    log_action('Updated facility', 'Facility', facility.id,
               f'Updated facility "{facility.facility_name}"')
    flash(f'Facility "{facility.facility_name}" updated.', 'success')
    return redirect(url_for('facilities.index'))


@facilities_bp.route('/<id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(id):
    facility = Facility.query.get_or_404(id)
    name = facility.facility_name
    
    # Check if already archived
    if not facility.archived:
        flash(f'Cannot delete "{name}". Please archive it first.', 'danger')
        return redirect(url_for('facilities.index'))

    try:
        clear_availability_slots(facility.id)
        db.session.delete(facility)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception('Could not delete facility %s', id)
        flash(f'Could not delete "{name}": {db_error_message(exc)}', 'danger')
        return redirect(url_for('facilities.index', archived='true'))

    log_action('Permanently deleted facility', 'Facility', None, f'Permanently deleted facility "{name}"')
    flash(f'Facility "{name}" permanently deleted.', 'success')
    return redirect(url_for('facilities.index', archived='true'))


@facilities_bp.route('/<id>/archive', methods=['POST'])
@login_required
@admin_required
def archive(id):
    facility = Facility.query.get_or_404(id)
    facility.archived = True
    facility.is_available = False

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception('Could not archive facility %s', id)
        flash(f'Could not archive "{facility.facility_name}": {db_error_message(exc)}', 'danger')
        return redirect(url_for('facilities.index'))

    log_action('Archived facility', 'Facility', facility.id,
               f'Archived facility "{facility.facility_name}"')
    flash(f'"{facility.facility_name}" has been archived.', 'success')
    return redirect(url_for('facilities.index'))


@facilities_bp.route('/<id>/unarchive', methods=['POST'])
@login_required
@admin_required
def unarchive(id):
    facility = Facility.query.get_or_404(id)
    facility.archived = False

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception('Could not unarchive facility %s', id)
        flash(f'Could not unarchive "{facility.facility_name}": {db_error_message(exc)}', 'danger')
        return redirect(url_for('facilities.index', archived='true'))

    log_action('Unarchived facility', 'Facility', facility.id,
               f'Unarchived facility "{facility.facility_name}"')
    flash(f'"{facility.facility_name}" has been restored.', 'success')
    return redirect(url_for('facilities.index'))


@facilities_bp.route('/<id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle(id):
    facility = Facility.query.get_or_404(id)
    facility.is_available = not bool(facility.is_available)

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception('Could not change availability for %s', id)
        flash(f'Could not update "{facility.facility_name}": {db_error_message(exc)}', 'danger')
        return redirect(url_for('facilities.index'))

    state = 'available' if facility.is_available else 'unavailable'
    log_action('Updated facility availability', 'Facility', facility.id,
               f'Marked "{facility.facility_name}" as {state}')
    flash(f'"{facility.facility_name}" is now marked {state}.', 'success')
    return redirect(url_for('facilities.index'))


@facilities_bp.errorhandler(413)
def upload_too_large(_error):
    limit_mb = current_app.config.get('MAX_CONTENT_LENGTH', 0) // (1024 * 1024)
    flash(f'That image is too large. Maximum upload size is {limit_mb} MB.', 'danger')
    return redirect(url_for('facilities.index'))
