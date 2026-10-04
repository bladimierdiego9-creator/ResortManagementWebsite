from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.decorators import admin_required
from app.extensions import db
from app.models import Announcement
from datetime import datetime
from . import announcements_bp


@announcements_bp.route('/')
@login_required
@admin_required
def index():
    """Display all announcements"""
    try:
        announcements = Announcement.query.order_by(Announcement.created_at.desc()).all()
        return render_template('announcements/index.html', announcements=announcements)
    except Exception as e:
        flash(f'Error loading announcements: {str(e)}', 'danger')
        return render_template('announcements/index.html', announcements=[])


@announcements_bp.route('/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create():
    """Create a new announcement"""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        target_audience = request.form.get('target_audience', 'all')
        
        # Validation
        if not title:
            flash('Title is required', 'danger')
            return render_template('announcements/create.html')
        
        if not content:
            flash('Content is required', 'danger')
            return render_template('announcements/create.html')
        
        if target_audience not in ['staff', 'guest', 'all']:
            flash('Invalid target audience', 'danger')
            return render_template('announcements/create.html')
        
        try:
            # Create announcement
            announcement = Announcement(
                title=title,
                content=content,
                target_audience=target_audience,
                created_by_id=current_user.id,
                created_by_name=current_user.full_name
            )
            
            db.session.add(announcement)
            db.session.commit()
            
            flash(f'Announcement "{title}" created successfully!', 'success')
            return redirect(url_for('announcements.index'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating announcement: {str(e)}', 'danger')
            return render_template('announcements/create.html')
    
    return render_template('announcements/create.html')


@announcements_bp.route('/<int:announcement_id>')
@login_required
@admin_required
def detail(announcement_id):
    """View announcement details"""
    try:
        announcement = Announcement.query.get_or_404(announcement_id)
        return render_template('announcements/detail.html', announcement=announcement)
    except Exception as e:
        flash(f'Error loading announcement: {str(e)}', 'danger')
        return redirect(url_for('announcements.index'))


@announcements_bp.route('/<int:announcement_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(announcement_id):
    """Edit an announcement"""
    try:
        announcement = Announcement.query.get_or_404(announcement_id)
        
        if request.method == 'POST':
            title = request.form.get('title', '').strip()
            content = request.form.get('content', '').strip()
            target_audience = request.form.get('target_audience', 'all')
            is_active = request.form.get('is_active') == 'on'
            
            # Validation
            if not title:
                flash('Title is required', 'danger')
                return render_template('announcements/edit.html', announcement=announcement)
            
            if not content:
                flash('Content is required', 'danger')
                return render_template('announcements/edit.html', announcement=announcement)
            
            if target_audience not in ['staff', 'guest', 'all']:
                flash('Invalid target audience', 'danger')
                return render_template('announcements/edit.html', announcement=announcement)
            
            # Update announcement
            announcement.title = title
            announcement.content = content
            announcement.target_audience = target_audience
            announcement.is_active = is_active
            announcement.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            flash('Announcement updated successfully!', 'success')
            return redirect(url_for('announcements.detail', announcement_id=announcement_id))
        
        # Get previous and next announcements for navigation
        all_announcements = Announcement.query.order_by(Announcement.created_at.desc()).all()
        current_index = next((i for i, a in enumerate(all_announcements) if a.id == announcement_id), None)
        
        prev_announcement = all_announcements[current_index + 1] if current_index is not None and current_index + 1 < len(all_announcements) else None
        next_announcement = all_announcements[current_index - 1] if current_index is not None and current_index > 0 else None
        
        return render_template('announcements/edit.html', 
                             announcement=announcement,
                             prev_announcement=prev_announcement,
                             next_announcement=next_announcement)
    
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('announcements.index'))


@announcements_bp.route('/<int:announcement_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(announcement_id):
    """Delete an announcement (soft delete)"""
    try:
        announcement = Announcement.query.get_or_404(announcement_id)
        announcement.is_active = False
        announcement.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Announcement deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
    
    return redirect(url_for('announcements.index'))


@announcements_bp.route('/<int:announcement_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_active(announcement_id):
    """Toggle announcement active status"""
    try:
        announcement = Announcement.query.get_or_404(announcement_id)
        announcement.is_active = not announcement.is_active
        announcement.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'is_active': announcement.is_active,
            'message': f'Announcement {"activated" if announcement.is_active else "deactivated"}'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


# API endpoints for staff/guest to view announcements
@announcements_bp.route('/api/staff')
@login_required
def api_staff_announcements():
    """Get announcements for staff"""
    try:
        announcements = Announcement.query.filter(
            Announcement.is_active == True,
            Announcement.target_audience.in_(['staff', 'all'])
        ).order_by(Announcement.created_at.desc()).all()
        
        return jsonify({
            'success': True,
            'announcements': [a.to_dict() for a in announcements]
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@announcements_bp.route('/api/guest')
def api_guest_announcements():
    """Get announcements for guests (public endpoint)"""
    try:
        announcements = Announcement.query.filter(
            Announcement.is_active == True,
            Announcement.target_audience.in_(['guest', 'all'])
        ).order_by(Announcement.created_at.desc()).all()
        
        return jsonify({
            'success': True,
            'announcements': [a.to_dict() for a in announcements]
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
