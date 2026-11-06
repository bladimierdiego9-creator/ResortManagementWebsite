"""Set facility types to 3 only: full_exclusivity, pavilion_and_event, pool_and_cottages"""
from app import create_app
from app.extensions import db

app = create_app()
with app.app_context():
    # Drop constraint first
    print("Removing old constraint...")
    db.session.execute(db.text("ALTER TABLE facilities DROP CONSTRAINT IF EXISTS facilities_facility_type_check;"))
    db.session.commit()
    
    # Then update existing facilities to new 3 types
    print("Updating existing facilities...")
    
    updates = """
    UPDATE facilities SET facility_type = 'pool_and_cottages' WHERE facility_type IN ('pool', 'cottages', 'cottage', 'room');
    UPDATE facilities SET facility_type = 'full_exclusivity' WHERE facility_name ILIKE '%exclusivity%' OR facility_name ILIKE '%resort%' OR facility_name ILIKE '%full%';
    UPDATE facilities SET facility_type = 'pavilion_and_event' WHERE facility_type IN ('pavilion', 'event');
    """
    
    db.session.execute(db.text(updates))
    db.session.commit()
    print("✓ Updated existing facilities")
    
    # Add new constraint with only 3 types
    constraint_sql = """
    ALTER TABLE facilities 
    ADD CONSTRAINT facilities_facility_type_check 
    CHECK (facility_type IN (
        'full_exclusivity', 
        'pavilion_and_event', 
        'pool_and_cottages'
    ));
    """
    
    try:
        db.session.execute(db.text(constraint_sql))
        db.session.commit()
        print("✓ Successfully set facility types!")
        print("\n✅ Allowed types (3 types only):")
        print("  1. full_exclusivity - Full Resort Exclusivity")
        print("  2. pavilion_and_event - Pavilion and Event")
        print("  3. pool_and_cottages - Pool and Cottages")
        print("\nYou can create multiple facilities of each type!")
    except Exception as e:
        db.session.rollback()
        print(f"✗ Error: {e}")
