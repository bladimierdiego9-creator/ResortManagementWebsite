"""
Firebase service for Thysia announcements
"""
import os
from datetime import datetime

# Fix SSL certificate issues on Windows
os.environ['GRPC_DEFAULT_SSL_ROOTS_FILE_PATH'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
os.environ['SSL_CERT_FILE'] = ''

import firebase_admin
from firebase_admin import credentials, firestore

# Initialize Firebase
_firebase_initialized = False

def init_firebase(app):
    """Initialize Firebase with the Flask app"""
    global _firebase_initialized
    
    if _firebase_initialized:
        return
    
    try:
        cred_path = app.config.get('FIREBASE_CREDENTIALS')
        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            print("[Firebase] Initialized successfully")
        else:
            print(f"[Firebase] Credentials file not found at {cred_path}")
    except Exception as e:
        print(f"[Firebase] Initialization failed: {e}")

def get_firestore_db():
    """Get Firestore database instance"""
    if not _firebase_initialized:
        raise Exception("Firebase not initialized. Call init_firebase() first.")
    return firestore.client()

class AnnouncementService:
    """Service for managing announcements in Firestore"""
    
    @staticmethod
    def create_announcement(title, content, target_audience, created_by_id, created_by_name):
        """
        Create a new announcement in Firestore
        
        Args:
            title: Announcement title
            content: Announcement content
            target_audience: 'staff', 'guest', or 'all'
            created_by_id: ID of admin who created it
            created_by_name: Name of admin who created it
        
        Returns:
            dict: Created announcement with ID
        """
        try:
            db = get_firestore_db()
            
            announcement_data = {
                'title': title,
                'content': content,
                'target_audience': target_audience,
                'created_by_id': created_by_id,
                'created_by_name': created_by_name,
                'created_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP,
                'is_active': True
            }
            
            # Add to Firestore
            doc_ref = db.collection('announcements').add(announcement_data)
            announcement_id = doc_ref[1].id
            
            return {
                'id': announcement_id,
                **announcement_data,
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
        except Exception as e:
            print(f"[Firebase] Error creating announcement: {e}")
            raise
    
    @staticmethod
    def get_all_announcements():
        """Get all announcements ordered by creation date"""
        try:
            db = get_firestore_db()
            announcements = []
            
            docs = db.collection('announcements').order_by('created_at', direction=firestore.Query.DESCENDING).stream()
            
            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id
                announcements.append(data)
            
            return announcements
        except Exception as e:
            print(f"[Firebase] Error getting announcements: {e}")
            return []
    
    @staticmethod
    def get_announcements_by_audience(target_audience):
        """Get announcements for specific audience"""
        try:
            db = get_firestore_db()
            announcements = []
            
            # Get announcements for specific audience or 'all'
            docs = db.collection('announcements')\
                .where('target_audience', 'in', [target_audience, 'all'])\
                .where('is_active', '==', True)\
                .order_by('created_at', direction=firestore.Query.DESCENDING)\
                .stream()
            
            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id
                announcements.append(data)
            
            return announcements
        except Exception as e:
            print(f"[Firebase] Error getting announcements by audience: {e}")
            return []
    
    @staticmethod
    def get_announcement_by_id(announcement_id):
        """Get a single announcement by ID"""
        try:
            db = get_firestore_db()
            doc = db.collection('announcements').document(announcement_id).get()
            
            if doc.exists:
                data = doc.to_dict()
                data['id'] = doc.id
                return data
            return None
        except Exception as e:
            print(f"[Firebase] Error getting announcement: {e}")
            return None
    
    @staticmethod
    def update_announcement(announcement_id, title=None, content=None, target_audience=None, is_active=None):
        """Update an announcement"""
        try:
            db = get_firestore_db()
            doc_ref = db.collection('announcements').document(announcement_id)
            
            update_data = {'updated_at': firestore.SERVER_TIMESTAMP}
            
            if title is not None:
                update_data['title'] = title
            if content is not None:
                update_data['content'] = content
            if target_audience is not None:
                update_data['target_audience'] = target_audience
            if is_active is not None:
                update_data['is_active'] = is_active
            
            doc_ref.update(update_data)
            return True
        except Exception as e:
            print(f"[Firebase] Error updating announcement: {e}")
            return False
    
    @staticmethod
    def delete_announcement(announcement_id):
        """Delete an announcement (soft delete by setting is_active to False)"""
        try:
            db = get_firestore_db()
            doc_ref = db.collection('announcements').document(announcement_id)
            doc_ref.update({
                'is_active': False,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            return True
        except Exception as e:
            print(f"[Firebase] Error deleting announcement: {e}")
            return False
    
    @staticmethod
    def hard_delete_announcement(announcement_id):
        """Permanently delete an announcement from Firestore"""
        try:
            db = get_firestore_db()
            db.collection('announcements').document(announcement_id).delete()
            return True
        except Exception as e:
            print(f"[Firebase] Error hard deleting announcement: {e}")
            return False
