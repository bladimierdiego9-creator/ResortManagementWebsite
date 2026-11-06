# 🎯 Supabase Setup Guide - Payment Verification Tables

## 📍 Saan Mag-store ang Data?

**IMPORTANTE:** Ang data ay mag-store sa **Supabase PostgreSQL Database**, hindi sa local VS Code!

---

## 🚀 Step-by-Step Guide

### Step 1: Open Supabase Dashboard

1. Go to: **https://supabase.com**
2. Login to your account
3. Select your project (A&D Thysia)

---

### Step 2: Open SQL Editor

1. Sa left sidebar, click **"SQL Editor"**
2. Or go directly to: `https://supabase.com/dashboard/project/[YOUR-PROJECT-ID]/sql`

---

### Step 3: Create New Query

1. Click **"New Query"** button (top right)
2. Or click **"+ New query"**

---

### Step 4: Copy SQL Script

1. Open ang file: **`create_payment_verification_tables.sql`**
2. **Select ALL** (Ctrl + A)
3. **Copy** (Ctrl + C)

---

### Step 5: Paste and Run

1. Paste sa Supabase SQL Editor (Ctrl + V)
2. Click **"Run"** button (o press Ctrl + Enter)
3. Wait for execution...

---

### Step 6: Verify Success

You should see messages like:
```
Success. No rows returned
```

Or check ang "Results" panel:
```
table_name         | column_count
-------------------|-------------
payments           | 25
gcash_configs      | 10
gcash_transactions | 11
```

---

## ✅ Verification - Check Tables Exist

### Method 1: Using Supabase Table Editor

1. Click **"Table Editor"** sa sidebar
2. Check if you see:
   - ✓ `payments` (updated)
   - ✓ `gcash_configs` (new)
   - ✓ `gcash_transactions` (new)

### Method 2: Using SQL Query

Run this query sa SQL Editor:
```sql
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('payments', 'gcash_configs', 'gcash_transactions')
ORDER BY table_name;
```

Expected result:
```
table_name
-------------------
gcash_configs
gcash_transactions
payments
```

---

## 🔍 Check Specific Columns

### Check payments table columns:
```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns 
WHERE table_name = 'payments'
AND (column_name LIKE '%gcash%' OR column_name LIKE '%verif%')
ORDER BY column_name;
```

Expected columns:
- `gcash_reference_number`
- `gcash_screenshot_data`
- `gcash_screenshot_filename`
- `gcash_screenshot_mimetype`
- `gcash_sender_name`
- `gcash_sender_number`
- `verification_notes`
- `verification_status`
- `verified_at`
- `verified_by_id`

---

## 🗂️ Table Structure sa Supabase

### 1. gcash_configs
**Purpose:** Store GCash QR codes for payment collection

| Column | Type | Description |
|--------|------|-------------|
| id | int4 | Primary key |
| qr_code_name | varchar(120) | Name ng QR code |
| qr_code_data | text | Base64 encoded image |
| gcash_account_name | varchar(120) | Account holder name |
| gcash_account_number | varchar(32) | GCash number |
| is_active | bool | Active status |
| created_by_id | int4 | FK → accounts.id |
| created_at | timestamp | Creation date |

### 2. gcash_transactions
**Purpose:** Store GCash transaction history for verification

| Column | Type | Description |
|--------|------|-------------|
| id | int4 | Primary key |
| reference_number | varchar(64) | GC-XXXXXXXXX (unique) |
| transaction_date | timestamp | Date ng transaction |
| sender_name | varchar(120) | Nagpadala |
| sender_number | varchar(32) | Sender's GCash # |
| amount | float8 | Amount received |
| payment_id | int4 | FK → payments.id (nullable) |
| screenshot_data | text | Base64 screenshot |
| uploaded_by_id | int4 | FK → accounts.id |
| created_at | timestamp | Upload date |

### 3. payments (Updated)
**Purpose:** Main payment records with verification fields

**New columns added:**
- `gcash_reference_number` - Para sa matching
- `gcash_sender_name` - Para sa matching
- `gcash_sender_number` - Para sa matching
- `gcash_screenshot_data` - Proof of payment
- `verification_status` - unverified/pending/verified/rejected
- `verification_notes` - Admin notes
- `verified_by_id` - FK → accounts.id
- `verified_at` - Timestamp

---

## 🎯 Data Flow

```
1. Guest submits payment → creates `payments` record (unverified)
                           ↓
2. Admin uploads GCash transaction → creates `gcash_transactions` record
                           ↓
3. System auto-matches → suggests matches based on amount/sender
                           ↓
4. Admin verifies → links payment_id, updates verification_status
                           ↓
5. Data stored in Supabase PostgreSQL ✓
```

---

## 🔐 RLS (Row Level Security) - Optional

Kung gusto mo i-enable ang security:

```sql
-- Enable RLS on gcash_configs
ALTER TABLE gcash_configs ENABLE ROW LEVEL SECURITY;

-- Admin only can view/insert
CREATE POLICY "Admins can view QR codes" ON gcash_configs
    FOR SELECT
    USING (auth.role() = 'authenticated');

-- Enable RLS on gcash_transactions
ALTER TABLE gcash_transactions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Admins can manage transactions" ON gcash_transactions
    FOR ALL
    USING (auth.role() = 'authenticated');
```

---

## 📊 Supabase Dashboard Views

### After setup, you can use:

1. **Table Editor** - View/edit data visually
2. **SQL Editor** - Run custom queries
3. **Database** → **Roles** - Manage permissions
4. **API Docs** - Auto-generated REST API

---

## ⚠️ Common Issues

### Error: "relation already exists"
✅ **Solution:** Table already created! You're good to go.

### Error: "column already exists"
✅ **Solution:** Column already added! Skip that part.

### Error: "permission denied"
❌ **Solution:** Check your Supabase role has CREATE privileges.

### Error: "database connection failed"
❌ **Solution:** Check your `.env` DATABASE_URL

---

## 🧪 Test the Setup

### Insert test data:
```sql
-- Test gcash_configs (replace with real data)
INSERT INTO gcash_configs (
    qr_code_name, 
    qr_code_filename, 
    qr_code_mimetype, 
    qr_code_data,
    gcash_account_name, 
    gcash_account_number, 
    created_by_id
) VALUES (
    'Test QR Code',
    'test_qr.png',
    'image/png',
    'base64_data_here',
    'Test Account',
    '09171234567',
    1
);

-- Test gcash_transactions
INSERT INTO gcash_transactions (
    reference_number,
    transaction_date,
    sender_name,
    sender_number,
    amount,
    uploaded_by_id
) VALUES (
    'GC-TEST123456',
    NOW(),
    'Juan Dela Cruz',
    '09181234567',
    5000.00,
    1
);
```

### Query test data:
```sql
SELECT * FROM gcash_configs LIMIT 1;
SELECT * FROM gcash_transactions LIMIT 1;
```

---

## 🎉 Success Checklist

- ✅ SQL script ran without errors
- ✅ Tables visible in Supabase Table Editor
- ✅ All columns exist in payments table
- ✅ gcash_configs table created
- ✅ gcash_transactions table created
- ✅ Foreign keys properly linked
- ✅ Indexes created
- ✅ Ready to use payment verification system!

---

## 🚀 Next Steps

1. ✅ Tables created in Supabase
2. 🔄 Test the web interface at `/payments/verification`
3. 📤 Upload your first QR code
4. 📝 Add transaction history
5. ✨ Start verifying payments!

---

## 💡 Pro Tips

- **Backup first:** Use Supabase's automatic backups
- **Test with sample data:** Before using real payments
- **Monitor queries:** Use Supabase's query performance tools
- **Enable RLS:** For production security
- **Use indexes:** Already created for performance!

---

## 📞 Need Help?

1. Check Supabase Logs: Dashboard → Logs
2. Check Database Health: Dashboard → Database → Health
3. View API logs: Dashboard → API → Logs
4. Check connection string in `.env`

---

**Remember:** All data is stored in **Supabase Cloud PostgreSQL**, not locally! 🌐
