"""Add archived field to facilities table"""
from app import create_app
from app.extensions import db

app = create_app()
with app.app_context():
    # Add archived column
    sql = """
    ALTER TABLE facilities 
    ADD COLUMN IF NOT EXISTS archived BOOLEAN DEFAULT FALSE;
    """
    
    try:
        db.session.execute(db.text(sql))
        db.session.commit()
        print("✓ Successfully added 'archived' column to facilities table!")
        print("\nFacilities can now be:")
        print("  - Active (archived=false)")
        print("  - Archived (archived=true)")
        print("\nArchived facilities can be permanently deleted.")
    except Exception as e:
        db.session.rollback()
        print(f"✗ Error: {e}")
