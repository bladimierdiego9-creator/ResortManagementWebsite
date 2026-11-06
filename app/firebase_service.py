"""
Firebase service for Firestore operations
Handles SSL certificate issues on Windows by using REST API
"""
import os
import json
import requests
from datetime import datetime
from flask import current_app
from google.oauth2 import service_account
from google.auth.transport.requests import Request
import urllib3

# Disable SSL warnings (for development only)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class FirebaseService:
    def __init__(self):
        self.project_id = None
        self.credentials = None
        self.base_url = None
        self._initialize()
    
    def _initialize(self):
        """Initialize Firebase credentials"""
        try:
            cred_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'firebase-credentials.json')
            
            if not os.path.exists(cred_path):
                print(f"Warning: Firebase credentials not found at {cred_path}")
                return
            
            with open(cred_path, 'r') as f:
                cred_data = json.load(f)
            
            self.project_id = cred_data.get('project_id')
            self.credentials = service_account.Credentials.from_service_account_file(
                cred_path,
                scopes=['https://www.googleapis.com/auth/datastore']
            )
            self.base_url = f'https://firestore.googleapis.com/v1/projects/{self.project_id}/databases/(default)/documents'
            
            print(f"Firebase initialized successfully for project: {self.project_id}")
        
        except Exception as e:
            print(f"Error initializing Firebase: {str(e)}")
    
    def _get_auth_token(self):
        """Get fresh authentication token"""
        if not self.credentials:
            return None
        
        # Create custom request adapter that bypasses SSL verification
        import google.auth.transport.requests
        
        class CustomRequest(google.auth.transport.requests.Request):
            def __call__(self, *args, **kwargs):
                kwargs['verify'] = False  # Bypass SSL verification
                return super().__call__(*args, **kwargs)
        
        if not self.credentials.valid:
            try:
                auth_request = CustomRequest()
                self.credentials.refresh(auth_request)
            except Exception as e:
                print(f"Error refreshing credentials: {str(e)}")
                return None
        
        return self.credentials.token
    
    def _firestore_to_dict(self, doc_data):
        """Convert Firestore document format to Python dict"""
        result = {}
        
        if 'fields' not in doc_data:
            return result
        
        for key, value in doc_data['fields'].items():
            if 'stringValue' in value:
                result[key] = value['stringValue']
            elif 'integerValue' in value:
                result[key] = int(value['integerValue'])
            elif 'booleanValue' in value:
                result[key] = value['booleanValue']
            elif 'timestampValue' in value:
                result[key] = value['timestampValue']
            elif 'nullValue' in value:
                result[key] = None
        
        # Extract ID from document name
        if 'name' in doc_data:
            doc_id = doc_data['name'].split('/')[-1]
            result['id'] = doc_id
        
        return result
    
    def _dict_to_firestore(self, data):
        """Convert Python dict to Firestore document format"""
        fields = {}
        
        for key, value in data.items():
            if value is None:
                fields[key] = {'nullValue': None}
            elif isinstance(value, bool):
                fields[key] = {'booleanValue': value}
            elif isinstance(value, int):
                fields[key] = {'integerValue': str(value)}
            elif isinstance(value, str):
                fields[key] = {'stringValue': value}
            elif isinstance(value, datetime):
                fields[key] = {'timestampValue': value.isoformat() + 'Z'}
        
        return {'fields': fields}
    
    def create_announcement(self, data):
        """Create a new announcement in Firestore"""
        try:
            token = self._get_auth_token()
            if not token:
                return {'success': False, 'message': 'Not authenticated'}
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            # Add timestamps
            now = datetime.utcnow()
            data['created_at'] = now
            data['updated_at'] = now
            
            # Convert to Firestore format
            doc_data = self._dict_to_firestore(data)
            
            # Create document
            response = requests.post(
                self.base_url + '/announcements',
                headers=headers,
                json=doc_data,
                verify=False  # Bypass SSL verification
            )
            
            if response.status_code in [200, 201]:
                doc = response.json()
                return {
                    'success': True,
                    'id': doc['name'].split('/')[-1],
                    'data': self._firestore_to_dict(doc)
                }
            else:
                return {
                    'success': False,
                    'message': f'Error creating announcement: {response.text}'
                }
        
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    def get_announcement(self, announcement_id):
        """Get a single announcement by ID"""
        try:
            token = self._get_auth_token()
            if not token:
                return None
            
            headers = {'Authorization': f'Bearer {token}'}
            
            response = requests.get(
                f'{self.base_url}/announcements/{announcement_id}',
                headers=headers,
                verify=False  # Bypass SSL verification
            )
            
            if response.status_code == 200:
                return self._firestore_to_dict(response.json())
            
            return None
        
        except Exception as e:
            print(f"Error getting announcement: {str(e)}")
            return None
    
    def get_all_announcements(self):
        """Get all announcements"""
        try:
            token = self._get_auth_token()
            if not token:
                return []
            
            headers = {'Authorization': f'Bearer {token}'}
            
            response = requests.get(
                self.base_url + '/announcements',
                headers=headers,
                verify=False  # Bypass SSL verification
            )
            
            if response.status_code == 200:
                data = response.json()
                documents = data.get('documents', [])
                return [self._firestore_to_dict(doc) for doc in documents]
            
            return []
        
        except Exception as e:
            print(f"Error getting announcements: {str(e)}")
            return []
    
    def update_announcement(self, announcement_id, data):
        """Update an announcement"""
        try:
            token = self._get_auth_token()
            if not token:
                return {'success': False, 'message': 'Not authenticated'}
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            # Add updated timestamp
            data['updated_at'] = datetime.utcnow()
            
            # Convert to Firestore format
            doc_data = self._dict_to_firestore(data)
            
            # Update document
            response = requests.patch(
                f'{self.base_url}/announcements/{announcement_id}',
                headers=headers,
                json=doc_data,
                verify=False  # Bypass SSL verification
            )
            
            if response.status_code == 200:
                return {'success': True, 'data': self._firestore_to_dict(response.json())}
            else:
                return {'success': False, 'message': response.text}
        
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    def delete_announcement(self, announcement_id):
        """Delete an announcement (soft delete by setting is_active to False)"""
        return self.update_announcement(announcement_id, {'is_active': False})
    
    def get_announcements_by_audience(self, audience):
        """Get announcements filtered by target audience"""
        try:
            all_announcements = self.get_all_announcements()
            
            # Filter by audience and active status
            filtered = [
                ann for ann in all_announcements
                if ann.get('is_active', True) and 
                (ann.get('target_audience') == audience or ann.get('target_audience') == 'all')
            ]
            
            # Sort by created_at descending
            filtered.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            
            return filtered
        
        except Exception as e:
            print(f"Error getting announcements by audience: {str(e)}")
            return []


# Global instance
firebase_service = FirebaseService()
