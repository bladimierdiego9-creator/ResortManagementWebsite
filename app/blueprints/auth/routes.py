from flask import render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from app.blueprints.auth import auth_bp
from app.models import Account
from app.extensions import db
from app.email import send_password_reset_email
from datetime import datetime


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin.overview'))

    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'

        user = Account.query.filter_by(username=username).first()
        if user and user.check_password(password) and user.status == 'active':
            login_user(user, remember=True)  # always remember — session lasts 7 days
            user.last_login = datetime.utcnow()
            db.session.commit()
            next_page = request.args.get('next')
            return redirect(next_page or url_for('admin.overview'))
        else:
            error = 'Invalid username or password.'

    return render_template('auth/login.html', error=error)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('')
def index():
    return redirect(url_for('auth.login'))


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Handle forgot password - send reset email."""
    if current_user.is_authenticated:
        return redirect(url_for('admin.overview'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        
        if not email:
            flash('Please enter your email address.', 'error')
            return render_template('auth/forgot_password.html')
        
        # Find user by email
        user = Account.query.filter_by(email=email).first()
        
        # Always show success message for security (don't reveal if email exists)
        if user and user.status == 'active':
            # Generate reset token
            token = user.generate_reset_token()
            db.session.commit()
            
            # Send reset email
            try:
                if send_password_reset_email(user.email, token):
                    flash('Password reset instructions have been sent to your email.', 'success')
                else:
                    flash('Failed to send reset email. Please try again later.', 'error')
            except Exception as e:
                flash('An error occurred. Please try again later.', 'error')
        else:
            # Still show success to prevent email enumeration
            flash('If that email exists in our system, you will receive password reset instructions.', 'info')
        
        return redirect(url_for('auth.login'))
    
    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Handle password reset with token."""
    if current_user.is_authenticated:
        return redirect(url_for('admin.overview'))
    
    # Find user with this token
    user = Account.query.filter_by(reset_token=token).first()
    
    if not user or not user.verify_reset_token(token):
        flash('Invalid or expired reset link. Please request a new one.', 'error')
        return redirect(url_for('auth.forgot_password'))
    
    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validation
        if not password or not confirm_password:
            flash('Please fill in all fields.', 'error')
            return render_template('auth/reset_password.html', token=token)
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('auth/reset_password.html', token=token)
        
        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
            return render_template('auth/reset_password.html', token=token)
        
        # Update password
        user.set_password(password)
        user.clear_reset_token()
        db.session.commit()
        
        flash('Your password has been reset successfully. You can now log in.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password.html', token=token)
