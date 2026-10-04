"""Test Firebase connection"""
import sys
import os

# Add the project to path
sys.path.insert(0, os.path.dirname(__file__))

print("=" * 50)
print("Testing Firebase Connection")
print("=" * 50)

# Test 1: Check if credentials file exists
print("\n1. Checking credentials file...")
cred_path = "firebase-credentials.json"
if os.path.exists(cred_path):
    print(f"   ✓ Credentials file found: {cred_path}")
else:
    print(f"   ✗ Credentials file NOT found: {cred_path}")
    sys.exit(1)

# Test 2: Try to import Firebase
print("\n2. Importing Firebase Admin SDK...")
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    print("   ✓ Firebase Admin SDK imported successfully")
except ImportError as e:
    print(f"   ✗ Import error: {e}")
    sys.exit(1)

# Test 3: Initialize Firebase
print("\n3. Initializing Firebase...")
try:
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)
    print("   ✓ Firebase initialized successfully")
except Exception as e:
    print(f"   ✗ Firebase initialization failed: {e}")
    sys.exit(1)

# Test 4: Get Firestore client
print("\n4. Getting Firestore client...")
try:
    db = firestore.client()
    print("   ✓ Firestore client created")
except Exception as e:
    print(f"   ✗ Firestore client failed: {e}")
    sys.exit(1)

# Test 5: Try to create a test document
print("\n5. Creating test announcement...")
try:
    from datetime import datetime
    
    test_data = {
        'title': 'Test Announcement',
        'content': 'This is a test',
        'target_audience': 'all',
        'created_by_id': 1,
        'created_by_name': 'Test Admin',
        'created_at': datetime.now(),
        'updated_at': datetime.now(),
        'is_active': True
    }
    
    doc_ref = db.collection('announcements').add(test_data)
    doc_id = doc_ref[1].id
    print(f"   ✓ Test announcement created with ID: {doc_id}")
    
    # Try to read it back
    print("\n6. Reading back the test announcement...")
    doc = db.collection('announcements').document(doc_id).get()
    if doc.exists:
        print(f"   ✓ Successfully read back announcement")
        print(f"   Title: {doc.to_dict()['title']}")
    else:
        print("   ✗ Could not read back announcement")
    
    # Clean up - delete test document
    print("\n7. Cleaning up test data...")
    db.collection('announcements').document(doc_id).delete()
    print("   ✓ Test announcement deleted")
    
except Exception as e:
    print(f"   ✗ Test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 50)
print("✓ All tests passed! Firebase is working correctly!")
print("=" * 50)
