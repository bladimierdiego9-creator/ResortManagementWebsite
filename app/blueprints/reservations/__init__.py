from flask import Blueprint
reservations_bp = Blueprint('reservations', __name__, url_prefix='/reservations')
from app.blueprints.reservations import routes
