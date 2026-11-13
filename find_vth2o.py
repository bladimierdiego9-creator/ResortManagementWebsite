"""
Find the v&t's H2O account
"""
from app import create_app
from app.models import Account, Guest
from app.extensions import db

app = create_app()

with app.app_context():
    print("\n=== SEARCHING FOR v&t's H2O ===\n")
    
    # Search in Guest table (row #23 sa screenshot)
    guest = Guest.query.filter(Guest.full_name.ilike('%v&t%')).first()
    
    if guest:
        print(f"✅ Found in GUESTS table:")
        print(f"   ID: {guest.id}")
        print(f"   Full Name: {guest.full_name}")
        print(f"   Email: {guest.email}")
        print(f"   Phone: {guest.phone}")
        print(f"   Account ID: {guest.account_id}")
        
        if guest.account:
            print(f"\n✅ Linked ACCOUNT:")
            print(f"   Account ID: {guest.account.id}")
            print(f"   Username: {guest.account.username}")
            print(f"   Email: {guest.account.email}")
    else:
        print("❌ Not found in guests table")
    
    # Check all guests
    print("\n=== ALL GUESTS (First 30) ===\n")
    guests = Guest.query.order_by(Guest.id).limit(30).all()
    for g in guests:
        print(f"ID {g.id}: {g.full_name} | Email: {g.email} | Account ID: {g.account_id}")
