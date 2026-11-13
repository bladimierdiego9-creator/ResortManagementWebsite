from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from app.cache import cache

db = SQLAlchemy()
login_manager = LoginManager()
