-- ============================================
-- GCash Payment Verification System Tables
-- ============================================

-- 1. Update payments table with GCash verification fields
-- (If not yet existing, add these columns)
ALTER TABLE payments ADD COLUMN IF NOT EXISTS gcash_reference_number VARCHAR(64);
ALTER TABLE payments ADD COLUMN IF NOT EXISTS gcash_sender_name VARCHAR(120);
ALTER TABLE payments ADD COLUMN IF NOT EXISTS gcash_sender_number VARCHAR(32);
ALTER TABLE payments ADD COLUMN IF NOT EXISTS gcash_screenshot_filename VARCHAR(256);
ALTER TABLE payments ADD COLUMN IF NOT EXISTS gcash_screenshot_mimetype VARCHAR(64);
ALTER TABLE payments ADD COLUMN IF NOT EXISTS gcash_screenshot_data TEXT;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS verification_status VARCHAR(32) DEFAULT 'unverified';
ALTER TABLE payments ADD COLUMN IF NOT EXISTS verification_notes TEXT;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS verified_by_id INTEGER;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP;

-- Add foreign key for verified_by_id
ALTER TABLE payments ADD CONSTRAINT fk_payments_verified_by 
    FOREIGN KEY (verified_by_id) REFERENCES accounts(id) ON DELETE SET NULL;

-- Add index for verification status
CREATE INDEX IF NOT EXISTS idx_payments_verification_status ON payments(verification_status);


-- 2. Create gcash_configs table (for QR Codes)
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
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign keys
    CONSTRAINT fk_gcash_configs_created_by 
        FOREIGN KEY (created_by_id) REFERENCES accounts(id) ON DELETE CASCADE
);

-- Indexes for gcash_configs
CREATE INDEX IF NOT EXISTS idx_gcash_configs_is_active ON gcash_configs(is_active);
CREATE INDEX IF NOT EXISTS idx_gcash_configs_account_number ON gcash_configs(gcash_account_number);


-- 3. Create gcash_transactions table (for Transaction History)
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign keys
    CONSTRAINT fk_gcash_transactions_payment 
        FOREIGN KEY (payment_id) REFERENCES payments(id) ON DELETE SET NULL,
    CONSTRAINT fk_gcash_transactions_uploaded_by 
        FOREIGN KEY (uploaded_by_id) REFERENCES accounts(id) ON DELETE CASCADE
);

-- Indexes for gcash_transactions
CREATE INDEX IF NOT EXISTS idx_gcash_transactions_reference ON gcash_transactions(reference_number);
CREATE INDEX IF NOT EXISTS idx_gcash_transactions_payment_id ON gcash_transactions(payment_id);
CREATE INDEX IF NOT EXISTS idx_gcash_transactions_amount ON gcash_transactions(amount);
CREATE INDEX IF NOT EXISTS idx_gcash_transactions_date ON gcash_transactions(transaction_date);
CREATE INDEX IF NOT EXISTS idx_gcash_transactions_sender_number ON gcash_transactions(sender_number);


-- ============================================
-- Verification: Check if tables were created
-- ============================================
SELECT 
    'payments' as table_name, 
    COUNT(*) as column_count 
FROM information_schema.columns 
WHERE table_name = 'payments'
UNION ALL
SELECT 
    'gcash_configs' as table_name, 
    COUNT(*) as column_count 
FROM information_schema.columns 
WHERE table_name = 'gcash_configs'
UNION ALL
SELECT 
    'gcash_transactions' as table_name, 
    COUNT(*) as column_count 
FROM information_schema.columns 
WHERE table_name = 'gcash_transactions';


-- ============================================
-- Optional: Sample data for testing
-- ============================================

-- Sample GCash Config (QR Code)
-- Replace 'your_base64_data_here' with actual base64 encoded QR code
-- INSERT INTO gcash_configs (qr_code_name, qr_code_filename, qr_code_mimetype, qr_code_data, gcash_account_name, gcash_account_number, created_by_id)
-- VALUES ('Main GCash Account', 'gcash_qr.png', 'image/png', 'your_base64_data_here', 'Juan Dela Cruz', '09171234567', 1);

-- Sample GCash Transaction
-- INSERT INTO gcash_transactions (reference_number, transaction_date, sender_name, sender_number, amount, uploaded_by_id)
-- VALUES ('GC-123456789', '2024-10-05 14:30:00', 'Maria Santos', '09181234567', 5000.00, 1);
