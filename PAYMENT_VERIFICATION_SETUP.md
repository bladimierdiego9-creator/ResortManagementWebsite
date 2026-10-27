# 🏦 GCash Payment Verification Setup Guide

## 📋 Mga Required Tables

Para gumana ang payment verification system, kailangan mo ng **3 tables**:

1. **`payments`** - Updated with verification fields
2. **`gcash_configs`** - Para sa QR codes
3. **`gcash_transactions`** - Para sa transaction history

---

## 🚀 Option 1: Using Supabase SQL Editor (RECOMMENDED)

### Step 1: Login to Supabase
1. Go to https://supabase.com
2. Open your project
3. Click "SQL Editor" sa sidebar

### Step 2: Run the SQL Script
1. Open ang file `create_payment_verification_tables.sql`
2. Copy ALL the content
3. Paste sa Supabase SQL Editor
4. Click "Run" button
5. Wait for success message! ✨

---

## 🔧 Option 2: Using Python Script (Automatic)

Kung gusto mo automatic via Python (connected to Supabase):

### Step 1: Activate virtual environment
```bash
.venv\Scripts\activate
```

### Step 2: Make sure .env has Supabase connection
```
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@[YOUR-PROJECT].supabase.co:5432/postgres
```

### Step 3: Run the Python migration script
```bash
python create_verification_tables.py
```

Ito ay automatic na gagawa ng lahat ng tables sa Supabase! ✨

---

## ✅ Verification

### Check kung existing na ang tables:
```sql
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('payments', 'gcash_configs', 'gcash_transactions');
```

### Check ang columns ng payments table:
```sql
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'payments'
AND column_name LIKE '%gcash%' OR column_name LIKE '%verif%';
```

---

## 📊 Table Structure

### 1. payments (Updated)
```sql
- gcash_reference_number (VARCHAR 64)
- gcash_sender_name (VARCHAR 120)
- gcash_sender_number (VARCHAR 32)
- gcash_screenshot_filename (VARCHAR 256)
- gcash_screenshot_mimetype (VARCHAR 64)
- gcash_screenshot_data (TEXT)
- verification_status (VARCHAR 32) - 'unverified', 'pending', 'verified', 'rejected'
- verification_notes (TEXT)
- verified_by_id (INTEGER) - FK to accounts.id
- verified_at (TIMESTAMP)
```

### 2. gcash_configs
```sql
- id (PRIMARY KEY)
- qr_code_name (VARCHAR 120)
- qr_code_filename (VARCHAR 256)
- qr_code_mimetype (VARCHAR 64)
- qr_code_data (TEXT) - base64 encoded QR image
- gcash_account_name (VARCHAR 120)
- gcash_account_number (VARCHAR 32)
- is_active (BOOLEAN)
- created_by_id (INTEGER) - FK to accounts.id
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)
```

### 3. gcash_transactions
```sql
- id (PRIMARY KEY)
- reference_number (VARCHAR 64 UNIQUE)
- transaction_date (TIMESTAMP)
- sender_name (VARCHAR 120)
- sender_number (VARCHAR 32)
- amount (FLOAT)
- payment_id (INTEGER) - FK to payments.id (nullable, linked when verified)
- screenshot_filename (VARCHAR 256)
- screenshot_mimetype (VARCHAR 64)
- screenshot_data (TEXT) - base64 encoded screenshot
- notes (TEXT)
- uploaded_by_id (INTEGER) - FK to accounts.id
- created_at (TIMESTAMP)
```

---

## 🎯 Paano Gamitin

### 1. Upload QR Code
- Go to: `/payments/verification`
- Click "Upload QR Code"
- Upload your GCash QR code

### 2. Add Transaction History
- Click "Add Transaction"
- Enter transaction details from GCash app
- Upload screenshot (optional but recommended)

### 3. Automatic Matching
- System will automatically suggest matches
- Based on: amount, sender name, reference number

### 4. Verify Payments
- Review suggested matches
- Click "Verify This Match"
- Payment status becomes "verified"

---

## 🔍 Troubleshooting

### Error: "Table already exists"
✅ This is okay! The script uses `IF NOT EXISTS` to prevent errors.

### Error: "Column already exists"
✅ This is okay! The script uses `ADD COLUMN IF NOT EXISTS`.

### Error: "Foreign key constraint fails"
❌ Make sure `accounts` table exists first!

### Error: "Permission denied"
❌ Make sure you have CREATE/ALTER permissions on the database.

---

## 📞 Support

Need help? Check:
1. Check if virtual environment is activated
2. Check database connection in `.env`
3. Check if `accounts` table exists
4. Check PostgreSQL is running

---

## 🎉 Success!

Kapag successful, makikita mo sa terminal:
```
✅ Payments table updated successfully!
✅ All tables created successfully!
🎉 SUCCESS! All payment verification tables are ready!
```

You're ready to use the payment verification system! 🚀
