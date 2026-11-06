-- ============================================================================
-- 🚀 SUPABASE PAYMENT VERIFICATION - RUN THIS SCRIPT
-- ============================================================================
-- INSTRUCTIONS:
-- 1. Copy this ENTIRE file (Ctrl + A, Ctrl + C)
-- 2. Go to Supabase → SQL Editor
-- 3. Paste (Ctrl + V)
-- 4. Click "Run" or press Ctrl + Enter
-- 5. Wait for "Success" message
-- ============================================================================

-- Start transaction
BEGIN;

-- ============================================================================
-- STEP 1: Update payments table with GCash verification fields
-- ============================================================================

DO $$ 
BEGIN
    -- Add gcash_reference_number if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='payments' AND column_name='gcash_reference_number') THEN
        ALTER TABLE payments ADD COLUMN gcash_reference_number VARCHAR(64);
    END IF;

    -- Add gcash_sender_name if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='payments' AND column_name='gcash_sender_name') THEN
        ALTER TABLE payments ADD COLUMN gcash_sender_name VARCHAR(120);
    END IF;

    -- Add gcash_sender_number if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='payments' AND column_name='gcash_sender_number') THEN
        ALTER TABLE payments ADD COLUMN gcash_sender_number VARCHAR(32);
    END IF;

    -- Add gcash_screenshot_filename if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='payments' AND column_name='gcash_screenshot_filename') THEN
        ALTER TABLE payments ADD COLUMN gcash_screenshot_filename VARCHAR(256);
    END IF;

    -- Add gcash_screenshot_mimetype if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='payments' AND column_name='gcash_screenshot_mimetype') THEN
        ALTER TABLE payments ADD COLUMN gcash_screenshot_mimetype VARCHAR(64);
    END IF;

    -- Add gcash_screenshot_data if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='payments' AND column_name='gcash_screenshot_data') THEN
        ALTER TABLE payments ADD COLUMN gcash_screenshot_data TEXT;
    END IF;

    -- Add verification_status if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='payments' AND column_name='verification_status') THEN
        ALTER TABLE payments ADD COLUMN verification_status VARCHAR(32) DEFAULT 'unverified';
    END IF;

    -- Add verification_notes if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='payments' AND column_name='verification_notes') THEN
        ALTER TABLE payments ADD COLUMN verification_notes TEXT;
    END IF;

    -- Add verified_by_id if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='payments' AND column_name='verified_by_id') THEN
        ALTER TABLE payments ADD COLUMN verified_by_id INTEGER;
    END IF;

    -- Add verified_at if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='payments' AND column_name='verified_at') THEN
        ALTER TABLE payments ADD COLUMN verified_at TIMESTAMP;
    END IF;
END $$;

-- Add index for verification_status
CREATE INDEX IF NOT EXISTS idx_payments_verification_status ON payments(verification_status);

-- ============================================================================
-- STEP 2: Create gcash_configs table (for QR Codes)
-- ============================================================================

CREATE TABLE IF NOT EXISTS gcash_configs (
    id SERIAL PRIMARY KEY,
    qr_code_name VARCHAR(120) NOT NULL,
    qr_code_filename VARCHAR(256) NOT NULL,
    qr_code_mimetype VARCHAR(64) NOT NULL,
    qr_code_data TEXT NOT NULL,
    
    -- GCash account information
    gcash_account_name VARCHAR(120) NOT NULL,
    gcash_account_number VARCHAR(32) NOT NULL,
    
    -- Status and metadata
    is_active BOOLEAN DEFAULT TRUE,
    created_by_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add indexes for gcash_configs
CREATE INDEX IF NOT EXISTS idx_gcash_configs_is_active ON gcash_configs(is_active);
CREATE INDEX IF NOT EXISTS idx_gcash_configs_account_number ON gcash_configs(gcash_account_number);

-- ============================================================================
-- STEP 3: Create gcash_transactions table (for Transaction History)
-- ============================================================================

CREATE TABLE IF NOT EXISTS gcash_transactions (
    id SERIAL PRIMARY KEY,
    reference_number VARCHAR(64) UNIQUE NOT NULL,
    transaction_date TIMESTAMP NOT NULL,
    sender_name VARCHAR(120) NOT NULL,
    sender_number VARCHAR(32) NOT NULL,
    amount FLOAT NOT NULL,
    
    -- Link to payment when matched/verified
    payment_id INTEGER,
    
    -- Screenshot of transaction
    screenshot_filename VARCHAR(256),
    screenshot_mimetype VARCHAR(64),
    screenshot_data TEXT,
    
    -- Additional info
    notes TEXT,
    uploaded_by_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add indexes for gcash_transactions
CREATE INDEX IF NOT EXISTS idx_gcash_transactions_reference ON gcash_transactions(reference_number);
CREATE INDEX IF NOT EXISTS idx_gcash_transactions_payment_id ON gcash_transactions(payment_id);
CREATE INDEX IF NOT EXISTS idx_gcash_transactions_amount ON gcash_transactions(amount);
CREATE INDEX IF NOT EXISTS idx_gcash_transactions_date ON gcash_transactions(transaction_date);
CREATE INDEX IF NOT EXISTS idx_gcash_transactions_sender_number ON gcash_transactions(sender_number);

-- ============================================================================
-- STEP 4: Add Foreign Key Constraints (if accounts table exists)
-- ============================================================================

DO $$ 
BEGIN
    -- Check if accounts table exists before adding foreign keys
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='accounts') THEN
        
        -- Add FK for payments.verified_by_id
        IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints 
                       WHERE constraint_name='fk_payments_verified_by') THEN
            ALTER TABLE payments 
            ADD CONSTRAINT fk_payments_verified_by 
            FOREIGN KEY (verified_by_id) REFERENCES accounts(id) ON DELETE SET NULL;
        END IF;

        -- Add FK for gcash_configs.created_by_id
        IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints 
                       WHERE constraint_name='fk_gcash_configs_created_by') THEN
            ALTER TABLE gcash_configs 
            ADD CONSTRAINT fk_gcash_configs_created_by 
            FOREIGN KEY (created_by_id) REFERENCES accounts(id) ON DELETE CASCADE;
        END IF;

        -- Add FK for gcash_transactions.payment_id
        IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints 
                       WHERE constraint_name='fk_gcash_transactions_payment') THEN
            ALTER TABLE gcash_transactions 
            ADD CONSTRAINT fk_gcash_transactions_payment 
            FOREIGN KEY (payment_id) REFERENCES payments(id) ON DELETE SET NULL;
        END IF;

        -- Add FK for gcash_transactions.uploaded_by_id
        IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints 
                       WHERE constraint_name='fk_gcash_transactions_uploaded_by') THEN
            ALTER TABLE gcash_transactions 
            ADD CONSTRAINT fk_gcash_transactions_uploaded_by 
            FOREIGN KEY (uploaded_by_id) REFERENCES accounts(id) ON DELETE CASCADE;
        END IF;

    END IF;
END $$;

-- ============================================================================
-- STEP 5: Verification - Check what was created
-- ============================================================================

-- Check tables exist
SELECT 
    'TABLE CHECK' as check_type,
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns WHERE columns.table_name = tables.table_name) as column_count
FROM information_schema.tables
WHERE table_schema = 'public' 
AND table_name IN ('payments', 'gcash_configs', 'gcash_transactions')
ORDER BY table_name;

-- Check payments verification columns
SELECT 
    'PAYMENTS COLUMNS' as check_type,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns 
WHERE table_name = 'payments'
AND (column_name LIKE '%gcash%' OR column_name LIKE '%verif%')
ORDER BY column_name;

-- Commit transaction
COMMIT;

-- ============================================================================
-- ✅ SUCCESS MESSAGE
-- ============================================================================
SELECT '✅ SUCCESS! Payment verification tables created in Supabase!' as status;
SELECT '📊 Tables: payments (updated), gcash_configs (new), gcash_transactions (new)' as info;
SELECT '🚀 Ready to use at: /payments/verification' as next_step;
