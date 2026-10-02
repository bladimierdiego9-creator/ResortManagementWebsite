from flask import Blueprint
facilities_bp = Blueprint('facilities', __name__, url_prefix='/facilities')
from app.blueprints.facilities import routes
