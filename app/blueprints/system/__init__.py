from flask import Blueprint
system_bp = Blueprint('system', __name__, url_prefix='/system')
from app.blueprints.system import routes
