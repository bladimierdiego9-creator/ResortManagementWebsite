"""
Delete all accounts EXCEPT row #23 (ID 24 - v&t's H2O)
"""
from app import create_app
from app.models import Account
from app.extensions import db

app = create_app()

with app.app_context():
    print("\n" + "="*60)
    print("DELETE ALL ACCOUNTS EXCEPT ROW #23 (ID 24)")
    print("="*60 + "\n")
    
    # Find the account to KEEP (ID 24)
    keep_account = Account.query.get(24)
    
    if not keep_account:
        print("❌ Account ID 24 not found! Cannot proceed.")
        print("\nSearching for account with email 'v&t2023@gmail.com'...")
        keep_account = Account.query.filter_by(email='v&t2023@gmail.com').first()
        if keep_account:
            print(f"✅ Found account: ID {keep_account.id}, Username: {keep_account.username}")
        else:
            print("❌ No account found with that email either!")
            exit(1)
    
    print(f"🔒 KEEPING Account:")
    print(f"   ID: {keep_account.id}")
    print(f"   Username: {keep_account.username}")
    print(f"   Email: {keep_account.email}")
    print(f"   Status: {keep_account.status}")
    print()
    
    # Get all OTHER accounts
    accounts_to_delete = Account.query.filter(Account.id != keep_account.id).all()
    
    print(f"🗑️  DELETING {len(accounts_to_delete)} accounts:\n")
    
    for acc in accounts_to_delete:
        print(f"   ❌ ID {acc.id}: {acc.username} ({acc.email})")
    
    # Confirmation
    print(f"\n{'='*60}")
    print("⚠️  WARNING: This will permanently delete these accounts!")
    print(f"{'='*60}\n")
    
    confirm = input("Type 'DELETE' to confirm: ")
    
    if confirm == "DELETE":
        deleted_count = 0
        for acc in accounts_to_delete:
            try:
                db.session.delete(acc)
                deleted_count += 1
            except Exception as e:
                print(f"   ⚠️  Failed to delete {acc.username}: {e}")
        
        db.session.commit()
        
        print(f"\n✅ Successfully deleted {deleted_count} accounts!")
        print(f"✅ Kept 1 account: {keep_account.username} (ID {keep_account.id})")
        
        # Verify
        remaining = Account.query.count()
        print(f"\n📊 Remaining accounts in database: {remaining}")
        
        if remaining == 1:
            print("✅ Perfect! Only 1 account remains (row #23)")
        else:
            print(f"⚠️  Expected 1, but found {remaining} accounts")
    else:
        print("\n❌ Deletion cancelled.")
