from flask import Blueprint
attendance_payroll_bp = Blueprint('attendance_payroll', __name__, url_prefix='/attendance-payroll')
from app.blueprints.attendance_payroll import routes
