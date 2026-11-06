"""
Create Payment Verification Tables
Run this script to create the necessary tables for GCash payment verification
"""

from app import create_app
from app.extensions import db
from sqlalchemy import text

def create_verification_tables():
    """Create tables for payment verification system"""
    app = create_app()
    
    with app.app_context():
        print("🚀 Creating payment verification tables...")
        
        try:
            # 1. Update payments table with GCash verification fields
            print("\n📝 Updating payments table...")
            verification_fields = [
                "ALTER TABLE payments ADD COLUMN IF NOT EXISTS gcash_reference_number VARCHAR(64);",
                "ALTER TABLE payments ADD COLUMN IF NOT EXISTS gcash_sender_name VARCHAR(120);",
                "ALTER TABLE payments ADD COLUMN IF NOT EXISTS gcash_sender_number VARCHAR(32);",
                "ALTER TABLE payments ADD COLUMN IF NOT EXISTS gcash_screenshot_filename VARCHAR(256);",
                "ALTER TABLE payments ADD COLUMN IF NOT EXISTS gcash_screenshot_mimetype VARCHAR(64);",
                "ALTER TABLE payments ADD COLUMN IF NOT EXISTS gcash_screenshot_data TEXT;",
                "ALTER TABLE payments ADD COLUMN IF NOT EXISTS verification_status VARCHAR(32) DEFAULT 'unverified';",
                "ALTER TABLE payments ADD COLUMN IF NOT EXISTS verification_notes TEXT;",
                "ALTER TABLE payments ADD COLUMN IF NOT EXISTS verified_by_id INTEGER;",
                "ALTER TABLE payments ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP;",
            ]
            
            for sql in verification_fields:
                db.session.execute(text(sql))
                print(f"  ✓ {sql[:50]}...")
            
            db.session.commit()
            print("✅ Payments table updated successfully!")
            
            # 2. Create all tables from models
            print("\n📝 Creating new tables from models...")
            db.create_all()
            print("✅ All tables created successfully!")
            
            # 3. Verify tables exist
            print("\n🔍 Verifying tables...")
            result = db.session.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('payments', 'gcash_configs', 'gcash_transactions')
                ORDER BY table_name;
            """))
            
            tables = result.fetchall()
            for table in tables:
                print(f"  ✓ Table '{table[0]}' exists")
            
            if len(tables) == 3:
                print("\n🎉 SUCCESS! All payment verification tables are ready!")
                print("\n📋 Tables created:")
                print("  1. payments (updated with verification fields)")
                print("  2. gcash_configs (for QR codes)")
                print("  3. gcash_transactions (for transaction history)")
                print("\n✨ You can now use the payment verification system!")
            else:
                print(f"\n⚠️  Warning: Expected 3 tables, found {len(tables)}")
                
        except Exception as e:
            print(f"\n❌ Error creating tables: {e}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    create_verification_tables()
