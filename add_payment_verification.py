"""
Migration script to add payment verification features:
- Add GCash verification fields to payments table
- Create gcash_configs table for QR codes
- Create gcash_transactions table for transaction history
"""

import sys
from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    try:
        print("🔄 Adding payment verification columns to payments table...")
        
        # Add GCash verification fields to payments table
        columns_to_add = [
            ("gcash_reference_number", "VARCHAR(64)"),
            ("gcash_sender_name", "VARCHAR(120)"),
            ("gcash_sender_number", "VARCHAR(32)"),
            ("gcash_screenshot_filename", "VARCHAR(256)"),
            ("gcash_screenshot_mimetype", "VARCHAR(64)"),
            ("gcash_screenshot_data", "TEXT"),
            ("verification_status", "VARCHAR(32) DEFAULT 'unverified'"),
            ("verification_notes", "TEXT"),
            ("verified_by_id", "INTEGER REFERENCES accounts(id)"),
            ("verified_at", "TIMESTAMP"),
        ]
        
        for col_name, col_type in columns_to_add:
            try:
                db.session.execute(db.text(f"ALTER TABLE payments ADD COLUMN {col_name} {col_type};"))
                db.session.commit()
                print(f"  ✓ Added column: {col_name}")
            except Exception as e:
                if "already exists" in str(e):
                    print(f"  ⊙ Column already exists: {col_name}")
                else:
                    print(f"  ⚠ Error adding {col_name}: {e}")
                db.session.rollback()
        
        # Update status column to include 'verified'
        try:
            db.session.execute(db.text("""
                ALTER TABLE payments 
                DROP CONSTRAINT IF EXISTS payments_status_check;
            """))
            db.session.execute(db.text("""
                ALTER TABLE payments
                ADD CONSTRAINT payments_status_check 
                CHECK (status IN ('pending', 'paid', 'refunded', 'verified'));
            """))
            db.session.commit()
            print("  ✓ Updated payment status constraint")
        except Exception as e:
            print(f"  ⚠ Status constraint: {e}")
            db.session.rollback()
        
        print("\n🔄 Creating gcash_configs table...")
        
        # Create gcash_configs table
        try:
            db.session.execute(db.text("""
                CREATE TABLE IF NOT EXISTS gcash_configs (
                    id SERIAL PRIMARY KEY,
                    qr_code_name VARCHAR(120) NOT NULL,
                    qr_code_filename VARCHAR(256) NOT NULL,
                    qr_code_mimetype VARCHAR(64) NOT NULL,
                    qr_code_data TEXT NOT NULL,
                    gcash_account_name VARCHAR(120) NOT NULL,
                    gcash_account_number VARCHAR(32) NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_by_id INTEGER NOT NULL REFERENCES accounts(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
            db.session.commit()
            print("  ✓ Created gcash_configs table")
        except Exception as e:
            print(f"  ⚠ gcash_configs: {e}")
            db.session.rollback()
        
        print("\n🔄 Creating gcash_transactions table...")
        
        # Create gcash_transactions table
        try:
            db.session.execute(db.text("""
                CREATE TABLE IF NOT EXISTS gcash_transactions (
                    id SERIAL PRIMARY KEY,
                    reference_number VARCHAR(64) UNIQUE NOT NULL,
                    transaction_date TIMESTAMP NOT NULL,
                    sender_name VARCHAR(120) NOT NULL,
                    sender_number VARCHAR(32) NOT NULL,
                    amount NUMERIC(10, 2) NOT NULL,
                    payment_id INTEGER REFERENCES payments(id),
                    screenshot_filename VARCHAR(256),
                    screenshot_mimetype VARCHAR(64),
                    screenshot_data TEXT,
                    notes TEXT,
                    uploaded_by_id INTEGER NOT NULL REFERENCES accounts(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
            db.session.commit()
            print("  ✓ Created gcash_transactions table")
        except Exception as e:
            print(f"  ⚠ gcash_transactions: {e}")
            db.session.rollback()
        
        # Create indexes
        print("\n🔄 Creating indexes...")
        
        indexes = [
            ("idx_payments_verification_status", "payments", "verification_status"),
            ("idx_payments_gcash_ref", "payments", "gcash_reference_number"),
            ("idx_gcash_transactions_ref", "gcash_transactions", "reference_number"),
            ("idx_gcash_transactions_payment", "gcash_transactions", "payment_id"),
        ]
        
        for idx_name, table, column in indexes:
            try:
                db.session.execute(db.text(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({column});"))
                db.session.commit()
                print(f"  ✓ Created index: {idx_name}")
            except Exception as e:
                print(f"  ⚠ Index {idx_name}: {e}")
                db.session.rollback()
        
        print("\n✅ Payment verification system migration completed successfully!")
        
    except Exception as e:
        db.session.rollback()
        print(f"\n❌ Migration failed: {e}")
        raise
