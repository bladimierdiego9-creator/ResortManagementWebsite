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
        email = request.form.get('username', '').strip().lower()  # form field is still named 'username' but accepts email
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'

        user = Account.query.filter_by(email=email).first()
        if user and user.check_password(password) and user.status == 'active':
            login_user(user, remember=True)  # always remember — session lasts 7 days
            user.last_login = datetime.utcnow()
            db.session.commit()
            next_page = request.args.get('next')
            return redirect(next_page or url_for('admin.overview'))
        else:
            error = 'Invalid email or password.'

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
    """Handle forgot password - send OTP email."""
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
            # Generate OTP
            otp = user.generate_reset_token()
            db.session.commit()
            
            # Send OTP email
            try:
                if send_password_reset_email(user.email, otp):
                    # Store email in session to verify OTP later
                    session['reset_email'] = email
                    flash('A 6-digit OTP has been sent to your email.', 'success')
                    return redirect(url_for('auth.verify_otp'))
                else:
                    flash('Failed to send OTP. Please try again later.', 'error')
            except Exception as e:
                flash('An error occurred. Please try again later.', 'error')
        else:
            # Still show success to prevent email enumeration but redirect to verify page
            session['reset_email'] = email
            flash('If that email exists in our system, you will receive an OTP.', 'info')
            return redirect(url_for('auth.verify_otp'))
        
        return redirect(url_for('auth.verify_otp'))
    
    return render_template('auth/forgot_password.html')


@auth_bp.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    """Handle OTP verification."""
    if current_user.is_authenticated:
        return redirect(url_for('admin.overview'))
    
    # Check if email is in session
    email = session.get('reset_email')
    if not email:
        flash('Please request a password reset first.', 'error')
        return redirect(url_for('auth.forgot_password'))
    
    if request.method == 'POST':
        otp = request.form.get('otp', '').strip()
        
        if not otp:
            flash('Please enter the OTP.', 'error')
            return render_template('auth/verify_otp.html')
        
        # Find user and verify OTP
        user = Account.query.filter_by(email=email).first()
        
        if user and user.verify_reset_token(otp):
            # OTP is valid, store in session and redirect to reset password
            session['verified_otp'] = otp
            return redirect(url_for('auth.reset_password'))
        else:
            flash('Invalid or expired OTP. Please try again.', 'error')
    
    return render_template('auth/verify_otp.html', email=email)


@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    """Handle password reset after OTP verification."""
    if current_user.is_authenticated:
        return redirect(url_for('admin.overview'))
    
    # Check if OTP was verified
    email = session.get('reset_email')
    otp = session.get('verified_otp')
    
    if not email or not otp:
        flash('Please complete OTP verification first.', 'error')
        return redirect(url_for('auth.forgot_password'))
    
    # Find user and verify OTP is still valid
    user = Account.query.filter_by(email=email).first()
    
    if not user or not user.verify_reset_token(otp):
        flash('Session expired. Please request a new OTP.', 'error')
        session.pop('reset_email', None)
        session.pop('verified_otp', None)
        return redirect(url_for('auth.forgot_password'))
    
    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validation
        if not password or not confirm_password:
            flash('Please fill in all fields.', 'error')
            return render_template('auth/reset_password.html')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('auth/reset_password.html')
        
        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
            return render_template('auth/reset_password.html')
        
        # Update password
        user.set_password(password)
        user.clear_reset_token()
        db.session.commit()
        
        # Clear session
        session.pop('reset_email', None)
        session.pop('verified_otp', None)
        
        flash('Your password has been reset successfully. You can now log in.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password.html')
