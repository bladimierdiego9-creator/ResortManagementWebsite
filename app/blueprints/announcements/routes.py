from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.decorators import admin_required
from app.firebase_service import firebase_service
from datetime import datetime
from . import announcements_bp


@announcements_bp.route('/')
@login_required
@admin_required
def index():
    """Display all announcements"""
    try:
        announcements = firebase_service.get_all_announcements()
        # Sort by created_at descending
        announcements.sort(key=lambda x: x.get('created_at', ''), reverse=True)
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
            # Create announcement in Firebase
            result = firebase_service.create_announcement({
                'title': title,
                'content': content,
                'target_audience': target_audience,
                'created_by_id': current_user.id,
                'created_by_name': current_user.full_name,
                'is_active': True
            })
            
            if result.get('success'):
                flash(f'Announcement "{title}" created successfully!', 'success')
                return redirect(url_for('announcements.index'))
            else:
                flash(f'Error creating announcement: {result.get("message")}', 'danger')
                return render_template('announcements/create.html')
        
        except Exception as e:
            flash(f'Error creating announcement: {str(e)}', 'danger')
            return render_template('announcements/create.html')
    
    return render_template('announcements/create.html')


@announcements_bp.route('/<announcement_id>')
@login_required
@admin_required
def detail(announcement_id):
    """View announcement details"""
    try:
        announcement = firebase_service.get_announcement(announcement_id)
        if not announcement:
            flash('Announcement not found', 'danger')
            return redirect(url_for('announcements.index'))
        
        return render_template('announcements/detail.html', announcement=announcement)
    except Exception as e:
        flash(f'Error loading announcement: {str(e)}', 'danger')
        return redirect(url_for('announcements.index'))


@announcements_bp.route('/<announcement_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(announcement_id):
    """Edit an announcement"""
    try:
        announcement = firebase_service.get_announcement(announcement_id)
        if not announcement:
            flash('Announcement not found', 'danger')
            return redirect(url_for('announcements.index'))
        
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
            
            # Update announcement in Firebase
            result = firebase_service.update_announcement(announcement_id, {
                'title': title,
                'content': content,
                'target_audience': target_audience,
                'is_active': is_active
            })
            
            if result.get('success'):
                flash('Announcement updated successfully!', 'success')
                return redirect(url_for('announcements.detail', announcement_id=announcement_id))
            else:
                flash(f'Error updating announcement: {result.get("message")}', 'danger')
        
        # Get previous and next announcements for navigation
        all_announcements = firebase_service.get_all_announcements()
        all_announcements.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        current_index = next((i for i, a in enumerate(all_announcements) if a.get('id') == announcement_id), None)
        
        prev_announcement = all_announcements[current_index + 1] if current_index is not None and current_index + 1 < len(all_announcements) else None
        next_announcement = all_announcements[current_index - 1] if current_index is not None and current_index > 0 else None
        
        return render_template('announcements/edit.html', 
                             announcement=announcement,
                             prev_announcement=prev_announcement,
                             next_announcement=next_announcement)
    
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('announcements.index'))


@announcements_bp.route('/<announcement_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(announcement_id):
    """Delete an announcement (soft delete)"""
    try:
        result = firebase_service.delete_announcement(announcement_id)
        if result.get('success'):
            flash('Announcement deleted successfully', 'success')
        else:
            flash(f'Error deleting announcement: {result.get("message")}', 'danger')
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
    
    return redirect(url_for('announcements.index'))


@announcements_bp.route('/<announcement_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_active(announcement_id):
    """Toggle announcement active status"""
    try:
        announcement = firebase_service.get_announcement(announcement_id)
        if not announcement:
            return jsonify({'success': False, 'message': 'Announcement not found'}), 404
        
        new_status = not announcement.get('is_active', True)
        result = firebase_service.update_announcement(announcement_id, {'is_active': new_status})
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'is_active': new_status,
                'message': f'Announcement {"activated" if new_status else "deactivated"}'
            })
        else:
            return jsonify({'success': False, 'message': result.get('message')}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# API endpoints for staff/guest to view announcements
@announcements_bp.route('/api/staff')
@login_required
def api_staff_announcements():
    """Get announcements for staff"""
    try:
        announcements = firebase_service.get_announcements_by_audience('staff')
        
        return jsonify({
            'success': True,
            'announcements': announcements
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@announcements_bp.route('/api/guest')
def api_guest_announcements():
    """Get announcements for guests (public endpoint)"""
    try:
        announcements = firebase_service.get_announcements_by_audience('guest')
        
        return jsonify({
            'success': True,
            'announcements': announcements
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

