# Firebase Setup Instructions for A&D Thysia Announcements

## Step 1: Create Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Click "Add project" or select existing project
3. Follow the setup wizard

## Step 2: Enable Firestore Database

1. In Firebase Console, go to **Build** > **Firestore Database**
2. Click "Create database"
3. Choose **Start in production mode** or **Test mode**
4. Select a region closest to you (e.g., asia-southeast1)
5. Click "Enable"

## Step 3: Create Service Account

1. In Firebase Console, click the gear icon (⚙️) next to "Project Overview"
2. Select **Project settings**
3. Go to **Service accounts** tab
4. Click **Generate new private key**
5. Click **Generate key** - this will download a JSON file
6. Save this file as `firebase-credentials.json` in your project root directory

## Step 4: Configure Firestore Security Rules

In Firestore Database, go to the **Rules** tab and set:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Announcements collection
    match /announcements/{announcement} {
      // Allow admins to read/write (implement your admin check)
      allow read, write: if true;  // TODO: Add proper authentication
      
      // For production, use proper authentication:
      // allow read: if request.auth != null;
      // allow write: if request.auth != null && request.auth.token.admin == true;
    }
  }
}
```

## Step 5: Install Required Python Packages

```bash
pip install firebase-admin
```

## Step 6: Update .gitignore

Make sure `firebase-credentials.json` is in your `.gitignore`:

```
firebase-credentials.json
```

## Step 7: Verify Setup

Run your Flask app and check the console for:
```
[Firebase] Initialized successfully
```

## Firestore Data Structure

### Collection: `announcements`

Each document contains:
```json
{
  "title": "Announcement Title",
  "content": "Announcement content here...",
  "target_audience": "staff|guest|all",
  "created_by_id": 1,
  "created_by_name": "Admin Name",
  "created_at": "2024-10-04T12:00:00Z",
  "updated_at": "2024-10-04T12:00:00Z",
  "is_active": true
}
```

## API Endpoints

### Admin Endpoints (requires login + admin role)
- `GET /announcements/` - List all announcements
- `GET /announcements/create` - Create form
- `POST /announcements/create` - Create announcement
- `GET /announcements/<id>` - View details
- `GET /announcements/<id>/edit` - Edit form
- `POST /announcements/<id>/edit` - Update announcement
- `POST /announcements/<id>/delete` - Delete announcement
- `POST /announcements/<id>/toggle` - Toggle active status

### Public API Endpoints
- `GET /announcements/api/staff` - Get staff announcements (requires login)
- `GET /announcements/api/guest` - Get guest announcements (public)

## Testing

1. Login as admin
2. Go to `/announcements/`
3. Create a new announcement
4. Select target audience (Staff, Guest, or All)
5. Check Firestore Console to see the data

## Troubleshooting

### Error: "Firebase not initialized"
- Make sure `firebase-credentials.json` exists in project root
- Check file permissions
- Verify JSON format

### Error: "Permission denied"
- Check Firestore security rules
- Verify service account has proper permissions

### Error: "Module not found: firebase_admin"
- Run: `pip install firebase-admin`

## Production Considerations

1. **Security Rules**: Update Firestore rules for production
2. **Environment Variables**: Store credentials path in environment variables
3. **Rate Limiting**: Implement rate limiting for API endpoints
4. **Caching**: Consider caching frequently accessed announcements
5. **Monitoring**: Set up Firebase monitoring and alerts
