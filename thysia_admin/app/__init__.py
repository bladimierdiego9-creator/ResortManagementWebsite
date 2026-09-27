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
        from flask import session
        session.permanent = True

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

    @app.route('/')
    def index():
        from flask import redirect, url_for
        return redirect(url_for('auth.login'))

    with app.app_context():
        db.create_all()

    return app
