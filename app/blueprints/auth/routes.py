from flask import render_template, redirect, url_for, flash, request, session, make_response
from flask_login import login_user, logout_user, login_required, current_user
from app.blueprints.auth import auth_bp
from app.models import Account
from app.extensions import db
from app.email import send_password_reset_email
from datetime import datetime, timedelta
import secrets


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin.overview'))

    error = None
    if request.method == 'POST':
        email    = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'

        user = Account.query.filter_by(email=email).first()
        if user and user.check_password(password) and user.status == 'active':
            # Session lifetime: 12 h when "Remember" is off, 7 days when on
            from flask import current_app
            if remember:
                current_app.permanent_session_lifetime = timedelta(days=7)
            else:
                current_app.permanent_session_lifetime = timedelta(hours=12)

            session.permanent = True
            login_user(user, remember=remember)
            user.last_login = datetime.utcnow()
            db.session.commit()

            # ── Login-session token ──────────────────────────────────────────
            # Generate a unique token, store it in the server-side session AND
            # in an HttpOnly cookie.  The before_request hook validates that
            # both values match on every subsequent request.
            token = secrets.token_hex(32)
            session['login_token'] = token
            session['login_user_id'] = user.id

            next_page = request.args.get('next')
            resp = make_response(redirect(next_page or url_for('admin.overview')))

            max_age = 7 * 24 * 3600 if remember else 12 * 3600
            resp.set_cookie(
                'login_token',
                token,
                max_age=max_age,
                httponly=True,
                samesite='Lax',
                secure=False,   # set True when served over HTTPS
                path='/'
            )
            return resp
        else:
            error = 'Invalid email or password.'

    return render_template('auth/login.html', error=error)


@auth_bp.route('/force-logout')
def force_logout():
    """Force logout - clears everything without validation"""
    # Clear Flask-Login user
    logout_user()
    
    # Clear all session data
    session.clear()
    
    # Create clean response
    resp = make_response(redirect(url_for('auth.login')))
    
    # Remove all possible cookies
    resp.delete_cookie('login_token', path='/')
    resp.delete_cookie('login_token')
    resp.delete_cookie('nav_intent', path='/')  
    resp.delete_cookie('nav_intent')
    resp.delete_cookie('session', path='/')
    resp.delete_cookie('session')
    
    # Clear cache
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    
    return resp


@auth_bp.route('/logout')
def logout():
    # Force logout even if not authenticated (in case of token mismatch)
    if current_user.is_authenticated:
        logout_user()
    
    # Clear all session data (including login_token, current_page, etc.)
    session.clear()
    
    # Create response with redirect
    resp = make_response(redirect(url_for('auth.login')))
    
    # Expire both the login_token and nav_intent cookies with all possible paths
    resp.delete_cookie('login_token', path='/')
    resp.delete_cookie('login_token')  # Delete without path as backup
    resp.delete_cookie('nav_intent', path='/')
    resp.delete_cookie('nav_intent')  # Delete without path as backup
    
    # Add cache control headers to prevent caching
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    
    # Flash message after clearing session
    from flask import flash
    flash('You have been logged out.', 'info')
    
    return resp


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

        # A new request starts a fresh recovery flow. Do not let an earlier
        # email or verified OTP authorize a later attempt.
        session.pop('reset_email', None)
        session.pop('verified_otp', None)
        
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
                    user.clear_reset_token()
                    db.session.commit()
                    flash('Failed to send OTP. Please try again later.', 'error')
                    return redirect(url_for('auth.forgot_password'))
            except Exception as e:
                import traceback
                print(f"[FORGOT-PASSWORD] Email send error: {e}")
                traceback.print_exc()
                user.clear_reset_token()
                db.session.commit()
                flash('An error occurred. Please try again later.', 'error')
                return redirect(url_for('auth.forgot_password'))
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
