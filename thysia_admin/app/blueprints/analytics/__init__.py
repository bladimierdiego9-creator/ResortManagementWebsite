from flask import Blueprint
analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics')
from app.blueprints.analytics import routes
