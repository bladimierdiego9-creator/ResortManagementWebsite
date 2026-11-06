from flask import Flask
from app.extensions import db, login_manager
from config import Config


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    login_manager.login_user_loader_error_handler = None

    # Make all sessions permanent so they last PERMANENT_SESSION_LIFETIME
    @app.before_request
    def make_session_permanent():
        from flask import session, request, redirect, url_for
        from flask_login import current_user, logout_user
        session.permanent = True

        # ── Login-token validation ─────────────────────────────────────────────
        # Verifies that the HttpOnly login_token cookie matches the one stored
        # in the server-side session.  If they differ (tampered cookie or stolen
        # session), the user is forcibly logged out and redirected to login.
        if current_user.is_authenticated:
            # Skip token check on auth endpoints to avoid loops
            if request.endpoint not in ('auth.logout', 'auth.login', 'auth.forgot_password', 'auth.verify_otp', 'auth.reset_password', 'static'):
                session_token = session.get('login_token')
                cookie_token  = request.cookies.get('login_token')
                
                # Only validate if both tokens exist
                if session_token and cookie_token:
                    if session_token != cookie_token:
                        # Mismatch — invalidate session
                        logout_user()
                        session.clear()
                        from flask import flash, make_response
                        flash('Your session has expired or was invalidated. Please log in again.', 'warning')
                        resp = make_response(redirect(url_for('auth.login')))
                        resp.delete_cookie('login_token', path='/')
                        resp.delete_cookie('login_token')
                        return resp
                elif session_token or cookie_token:
                    # One exists but not the other - likely logout in progress or session issue
                    logout_user()
                    session.clear()
                    from flask import make_response
                    resp = make_response(redirect(url_for('auth.login')))
                    resp.delete_cookie('login_token', path='/')
                    resp.delete_cookie('login_token')
                    return resp

    # ── Navigation Lock ──────────────────────────────────────────────────────
    # Prevents users from navigating to a different page by manually editing
    # the URL bar. Pages can only be changed via the sidebar navigation links.
    #
    # How it works:
    #   1. JS in base.html sets a short-lived cookie "nav_intent=<url>" when
    #      a sidebar [data-nav-link] is clicked.
    #   2. This hook checks every GET request:
    #      - If the current URL matches nav_intent cookie → legitimate nav,
    #        update session['current_page'] and clear the cookie via response.
    #      - If session has a stored page and the URL is a different protected
    #        page with NO nav_intent → redirect back to stored page.
    @app.before_request
    def navigation_lock():
        from flask import request, session, redirect, make_response
        from flask_login import current_user
        from urllib.parse import urlparse, unquote

        # Only apply to authenticated GET requests
        if request.method != 'GET':
            return
        if not current_user.is_authenticated:
            return

        # Only real browser navigations are subject to the lock.
        # AJAX/fetch calls (e.g. the calendar's bookings feed) send an
        # HTML-capable Accept header too, so without this check they get bounced
        # with a 302, the caller silently follows it and parses the redirected
        # page as JSON — leaving the page that made the call empty.
        # Browsers label the request type in Sec-Fetch-Dest ('document' for
        # address-bar/sidebar navigations, 'empty' for fetch/XHR).
        fetch_dest = request.headers.get('Sec-Fetch-Dest')
        if fetch_dest and fetch_dest != 'document':
            return

        # Skip static assets, auth routes, and non-navigable API/media endpoints
        skip_prefixes = ('/static/', '/auth/')
        skip_endpoints = {'static', 'auth.login', 'auth.logout', 'index',
                          'facilities.image', 'payments.gcash_qr',
                          'payments.gcash_screenshot', 'payments.screenshot_proxy',
                          'admin.calendar', 'admin.api_bookings',
                          'attendance_payroll.rfid_management'}
        if request.endpoint in skip_endpoints:
            return
        if any(request.path.startswith(p) for p in skip_prefixes):
            return
        # Skip non-HTML endpoints (JSON, file downloads, etc.)
        if request.accept_mimetypes.best not in ('text/html', '*/*', None):
            return

        current_path = request.path
        nav_intent_raw = request.cookies.get('nav_intent', '')
        nav_intent = unquote(nav_intent_raw) if nav_intent_raw else ''

        # Determine if this is a legitimate sidebar navigation.
        # nav_intent holds the href the user clicked, which may include query
        # params.  We compare only the path portion.
        nav_intent_path = urlparse(nav_intent).path if nav_intent else ''
        is_sidebar_nav = bool(nav_intent_path and current_path == nav_intent_path)

        stored_page = session.get('current_page')

        if is_sidebar_nav:
            # Legitimate navigation: update stored page and proceed.
            session['current_page'] = current_path
            # The nav_intent cookie is automatically expired by the 5-second
            # max-age set in JS; nothing extra needed here.
            return

        # Not a sidebar click.
        if stored_page and stored_page != current_path:
            # User tried to jump to a different page via address bar → bounce back.
            resp = redirect(stored_page)
            resp.headers['Cache-Control'] = 'no-store'
            return resp

        # First visit or same page refresh: record the current page.
        session['current_page'] = current_path


    from app.blueprints.auth import auth_bp
    from app.blueprints.admin import admin_bp
    from app.blueprints.reservations import reservations_bp
    from app.blueprints.facilities import facilities_bp
    from app.blueprints.payments import payments_bp
    from app.blueprints.analytics import analytics_bp
    from app.blueprints.ai_concierge import ai_concierge_bp
    from app.blueprints.attendance_payroll import attendance_payroll_bp
    from app.blueprints.accounts import accounts_bp
    from app.blueprints.system import system_bp
    from app.blueprints.announcements import announcements_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(reservations_bp)
    app.register_blueprint(facilities_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(ai_concierge_bp)
    app.register_blueprint(attendance_payroll_bp)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(announcements_bp, url_prefix='/announcements')

    @app.context_processor
    def inject_frontend_globals():
        from datetime import datetime

        def format_currency(value):
            try:
                return f"₱{float(value):,.2f}"
            except (TypeError, ValueError):
                return "₱0.00"

        def format_date(value):
            if not value:
                return "—"
            if hasattr(value, "strftime"):
                return value.strftime("%b %d, %Y")
            return str(value)

        def format_datetime(value):
            if not value:
                return "—"
            if hasattr(value, "strftime"):
                return value.strftime("%b %d, %Y %I:%M %p")
            return str(value)

        return {
            "resort_name": "A&D Thysia",
            "app_version": "1.0",
            "now": datetime.now,
            "format_currency": format_currency,
            "format_date": format_date,
            "format_datetime": format_datetime,
        }

    @app.route('/')
    def index():
        from flask import redirect, url_for
        return redirect(url_for('auth.login'))

    with app.app_context():
        db.create_all()

        # Drop the unique constraint on accounts.reset_token if it exists.
        # The column was originally created with unique=True, which causes
        # failures when two users coincidentally receive the same 6-digit OTP.
        try:
            uri = str(db.engine.url)
            if 'sqlite' in uri:
                # SQLite doesn't support ALTER TABLE DROP CONSTRAINT, but
                # unique constraints on nullable columns don't block inserts
                # of duplicate NULLs in SQLite, so this is a no-op.
                pass
            else:
                # PostgreSQL: find and drop the constraint by inspecting
                # information_schema
                with db.engine.connect() as conn:
                    result = conn.execute(db.text("""
                        SELECT constraint_name
                        FROM information_schema.table_constraints
                        WHERE table_name = 'accounts'
                          AND constraint_type = 'UNIQUE'
                          AND constraint_name LIKE '%reset_token%'
                    """))
                    for row in result:
                        conn.execute(db.text(
                            f'ALTER TABLE accounts DROP CONSTRAINT IF EXISTS "{row[0]}"'
                        ))
                    conn.commit()
        except Exception as e:
            print(f"[STARTUP] Could not drop reset_token unique constraint: {e}")

        # Auto-sync unlinked staff and guests to ensure they have accounts
        try:
            from app.models import Staff, Guest, Account
            import re

            unlinked_staff = Staff.query.filter(Staff.account_id.is_(None)).all()
            for s in unlinked_staff:
                name_parts = (s.full_name or 'Staff').strip().split(' ', 1)
                first_name = name_parts[0]
                last_name = name_parts[1] if len(name_parts) > 1 else ''
                base_username = re.sub(r'[^a-z0-9]', '', (s.full_name or '').lower()) or f"staff{s.id}"
                username = base_username
                suffix = 1
                while Account.query.filter_by(username=username).first():
                    username = f"{base_username}{suffix}"
                    suffix += 1

                email = (s.email or '').strip().lower() or f"{username}@adthysia.com"
                suffix = 1
                base_email = email
                while Account.query.filter_by(email=email).first():
                    email_parts = base_email.split('@')
                    email = f"{email_parts[0]}{suffix}@{email_parts[1]}"
                    suffix += 1

                acc = Account(
                    username=username,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    role='staff',
                    rfid_tag=s.rfid_tag,
                    status=s.status or 'active'
                )
                acc.set_password('Staff@123')
                db.session.add(acc)
                db.session.flush()

                s.account_id = acc.id
                s.email = email

            unlinked_guests = Guest.query.filter(Guest.account_id.is_(None)).all()
            for g in unlinked_guests:
                name_parts = (g.full_name or 'Guest').strip().split(' ', 1)
                first_name = name_parts[0]
                last_name = name_parts[1] if len(name_parts) > 1 else ''
                base_username = re.sub(r'[^a-z0-9]', '', (g.full_name or '').lower()) or f"guest{g.id}"
                username = base_username
                suffix = 1
                while Account.query.filter_by(username=username).first():
                    username = f"{base_username}{suffix}"
                    suffix += 1

                email = (g.email or '').strip().lower() or f"{username}@guest.adthysia.com"
                suffix = 1
                base_email = email
                while Account.query.filter_by(email=email).first():
                    email_parts = base_email.split('@')
                    email = f"{email_parts[0]}{suffix}@{email_parts[1]}"
                    suffix += 1

                acc = Account(
                    username=username,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    role='guest',
                    status='active'
                )
                acc.set_password('Guest@123')
                db.session.add(acc)
                db.session.flush()

                g.account_id = acc.id
                g.email = email

            if unlinked_staff or unlinked_guests:
                db.session.commit()
        except Exception as e:
            print(f"[STARTUP] Could not sync unlinked accounts: {e}")

        # Auto-sync RFID cards from Staff who have rfid_tag
        try:
            from app.models import Staff, RFIDCard, AttendanceLog
            staff_with_rfid = Staff.query.filter(Staff.rfid_tag.isnot(None)).all()
            synced_rfid = 0
            for s in staff_with_rfid:
                existing_card = RFIDCard.query.filter_by(card_uid=s.rfid_tag).first()
                if not existing_card:
                    # Look up last attendance log for last_used_at
                    last_log = AttendanceLog.query.filter(
                        (AttendanceLog.rfid_tap_in == s.rfid_tag) | (AttendanceLog.rfid_tap_out == s.rfid_tag)
                    ).order_by(AttendanceLog.time_in.desc()).first()
                    last_used = last_log.time_in if last_log else None

                    card = RFIDCard(
                        card_uid=s.rfid_tag,
                        staff_id=s.id,
                        status='active' if s.status == 'active' else 'inactive',
                        notes=f"{s.full_name} ({s.role.replace('_', ' ').title()}) staff badge",
                        last_used_at=last_used
                    )
                    db.session.add(card)
                    synced_rfid += 1
                elif existing_card.staff_id != s.id:
                    existing_card.staff_id = s.id
                    synced_rfid += 1

            if synced_rfid:
                db.session.commit()
                print(f"[STARTUP] Synced {synced_rfid} RFID cards.")
        except Exception as e:
            print(f"[STARTUP] Could not sync RFID cards: {e}")

    return app
