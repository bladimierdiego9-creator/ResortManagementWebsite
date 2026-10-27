"""
Reset admin password to 'admin123'
"""
from app import create_app
from app.models import Account
from app.extensions import db

app = create_app()

with app.app_context():
    # Find admin account
    admin = Account.query.filter_by(username='Salamatin').first()
    
    if admin:
        admin.set_password('admin123')
        db.session.commit()
        print(f"✅ Password reset for: {admin.username}")
        print(f"   New password: admin123")
    else:
        print("❌ Admin account 'Salamatin' not found!")
