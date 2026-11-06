"""
Test if the /admin/api/bookings endpoint is accessible
"""
from app import create_app

app = create_app()

with app.test_client() as client:
    # First login
    print("🔐 Attempting login...")
    
    # Try to access the API endpoint without login
    response = client.get('/admin/api/bookings?start=2026-09-01&end=2026-11-30')
    print(f"\n📡 GET /admin/api/bookings")
    print(f"   Status Code: {response.status_code}")
    
    if response.status_code == 302:
        print(f"   Redirect to: {response.location}")
        print("   ❌ Not logged in - redirected to login page")
    elif response.status_code == 200:
        import json
        data = json.loads(response.data)
        print(f"   ✅ Success! Retrieved {len(data)} events")
        if data:
            print(f"\n📋 Sample event:")
            print(json.dumps(data[0], indent=2))
    else:
        print(f"   ❌ Error: {response.status_code}")
        print(f"   Response: {response.data[:200]}")
