from flask import Blueprint
ai_concierge_bp = Blueprint('ai_concierge', __name__, url_prefix='/ai-concierge')
from app.blueprints.ai_concierge import routes
