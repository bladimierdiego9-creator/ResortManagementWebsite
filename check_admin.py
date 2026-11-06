from app import create_app
from app.models import Account

app = create_app()

with app.app_context():
    accounts = Account.query.filter(Account.role.in_(['admin', 'super_admin'])).all()
    
    print("\n=== ADMIN ACCOUNTS ===")
    if not accounts:
        print("❌ No admin accounts found!")
        print("\nRun: python seed.py")
    else:
        for acc in accounts:
            print(f"\n👤 Username: {acc.username}")
            print(f"   Email: {acc.email}")
            print(f"   Role: {acc.role}")
            print(f"   Status: {acc.status}")
            print(f"   Name: {acc.first_name} {acc.last_name}")
            print(f"   Default Password: admin123")
