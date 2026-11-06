-- The Flask app already uses these tables in Supabase:
-- staff, rfid_cards, attendance_logs. No new table is needed.
-- Run this in Supabase SQL Editor to confirm the tables/indexes used by the scanner.
CREATE INDEX IF NOT EXISTS ix_rfid_cards_card_uid ON public.rfid_cards (card_uid);
CREATE INDEX IF NOT EXISTS ix_attendance_logs_staff_time_in
    ON public.attendance_logs (staff_id, time_in DESC);

-- Register one card to an existing staff member.
-- Replace the values below, then run this statement. UID format must be like
-- AA:BB:CC:DD (uppercase, colon-separated, matching the ESP32 display).
-- INSERT INTO public.rfid_cards (card_uid, staff_id, status, created_at)
-- SELECT 'AA:BB:CC:DD', s.id, 'active', NOW()
-- FROM public.staff AS s
-- WHERE s.id = 1
-- ON CONFLICT (card_uid) DO UPDATE
-- SET staff_id = EXCLUDED.staff_id, status = 'active';

-- View latest scans recorded by the website/API:
-- SELECT a.id, s.full_name, a.rfid_tap_in, a.time_in, a.time_out, a.status
-- FROM public.attendance_logs AS a
-- JOIN public.staff AS s ON s.id = a.staff_id
-- ORDER BY a.time_in DESC
-- LIMIT 50;
