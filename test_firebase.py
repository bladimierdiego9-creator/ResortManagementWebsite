"""Test Firebase Firestore connection"""
from app.firebase_service import firebase_service

print("Testing Firebase Firestore connection...")
print(f"Project ID: {firebase_service.project_id}")
print(f"Base URL: {firebase_service.base_url}")
print()

# Test creating an announcement
print("Attempting to create a test announcement...")
result = firebase_service.create_announcement({
    'title': 'Test Announcement',
    'content': 'This is a test announcement to verify Firebase connection.',
    'target_audience': 'all',
    'created_by_id': 1,
    'created_by_name': 'Admin Test',
    'is_active': True
})

if result.get('success'):
    print("✓ SUCCESS! Announcement created successfully!")
    print(f"  Document ID: {result.get('id')}")
    print(f"  Data: {result.get('data')}")
    print()
    
    # Try to retrieve it
    print("Attempting to retrieve all announcements...")
    announcements = firebase_service.get_all_announcements()
    print(f"✓ Retrieved {len(announcements)} announcement(s)")
    for ann in announcements:
        print(f"  - {ann.get('title')} (ID: {ann.get('id')})")
else:
    print("✗ ERROR creating announcement")
    print(f"  Message: {result.get('message')}")
    print()
    print("COMMON ISSUES:")
    print("1. Firestore database not yet created in Firebase Console")
    print("2. Go to: https://console.firebase.google.com/")
    print("3. Select project: aanddthysia")
    print("4. Click 'Firestore Database' and create database")
