from app import create_app
from app.models import Facility

app = create_app()
with app.app_context():
    facilities = Facility.query.all()
    print(f"Current facilities count: {len(facilities)}")
    print("\nFacilities in database:")
    for f in facilities:
        print(f"  - ID: {f.id}")
        print(f"    Name: {f.facility_name}")
        print(f"    Type: {f.facility_type}")
        print(f"    Available: {f.is_available}")
        print()
    
    # Check facility types from the routes helper
    from app.blueprints.facilities.routes import facility_types, allowed_facility_types
    print("Allowed facility types from DB constraint:", allowed_facility_types())
    print("All facility types (including stored):", facility_types())
