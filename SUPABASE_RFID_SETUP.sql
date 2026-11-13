-- Run this in Supabase SQL Editor to enable admin-armed RFID registration scans.
-- RFID taps are staged in rfid_scan_events. rfid_cards stays the official registry.
CREATE INDEX IF NOT EXISTS ix_rfid_cards_card_uid ON public.rfid_cards (card_uid);
CREATE INDEX IF NOT EXISTS ix_attendance_logs_staff_time_in
    ON public.attendance_logs (staff_id, time_in DESC);
ALTER TABLE public.rfid_cards
    ALTER COLUMN created_at SET DEFAULT (NOW() AT TIME ZONE 'UTC');

CREATE TABLE IF NOT EXISTS public.rfid_scan_control (
    id SMALLINT PRIMARY KEY CHECK (id = 1),
    is_armed BOOLEAN NOT NULL DEFAULT FALSE,
    session_id VARCHAR(36),
    scanned_uid VARCHAR(64),
    scanned_at TIMESTAMP WITHOUT TIME ZONE,
    started_at TIMESTAMP WITHOUT TIME ZONE,
    expires_at TIMESTAMP WITHOUT TIME ZONE
);

-- Upgrade a control table created by an earlier version of this setup.
ALTER TABLE public.rfid_scan_control
    ADD COLUMN IF NOT EXISTS is_armed BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE public.rfid_scan_control
    ADD COLUMN IF NOT EXISTS session_id VARCHAR(36);
ALTER TABLE public.rfid_scan_control
    ADD COLUMN IF NOT EXISTS scanned_uid VARCHAR(64);
ALTER TABLE public.rfid_scan_control
    ADD COLUMN IF NOT EXISTS scanned_at TIMESTAMP WITHOUT TIME ZONE;
ALTER TABLE public.rfid_scan_control
    ADD COLUMN IF NOT EXISTS started_at TIMESTAMP WITHOUT TIME ZONE;
ALTER TABLE public.rfid_scan_control
    ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITHOUT TIME ZONE;

ALTER TABLE public.rfid_scan_control ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.rfid_scan_control FROM PUBLIC, anon;
REVOKE SELECT (id, is_armed, session_id, scanned_uid, scanned_at, started_at, expires_at)
    ON TABLE public.rfid_scan_control FROM PUBLIC, anon;
REVOKE UPDATE (id, is_armed, session_id, scanned_uid, scanned_at, started_at, expires_at)
    ON TABLE public.rfid_scan_control FROM PUBLIC, anon;
GRANT SELECT (id, is_armed, session_id, expires_at)
    ON TABLE public.rfid_scan_control TO anon;

DROP POLICY IF EXISTS "ESP32 can read RFID scan session"
    ON public.rfid_scan_control;
CREATE POLICY "ESP32 can read RFID scan session"
    ON public.rfid_scan_control FOR SELECT TO anon
    USING (id = 1);

DROP POLICY IF EXISTS "ESP32 can publish an armed RFID scan"
    ON public.rfid_scan_control;

CREATE TABLE IF NOT EXISTS public.rfid_scan_events (
    id SERIAL PRIMARY KEY,
    card_uid VARCHAR(64) NOT NULL,
    rfid_card_id INTEGER NULL
        REFERENCES public.rfid_cards(id) ON DELETE SET NULL,
    scan_session_id VARCHAR(36) NOT NULL UNIQUE,
    scanned_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
        DEFAULT (NOW() AT TIME ZONE 'UTC'),
    processed_at TIMESTAMP WITHOUT TIME ZONE NULL
);
ALTER TABLE public.rfid_scan_events
    ALTER COLUMN scanned_at SET DEFAULT (NOW() AT TIME ZONE 'UTC');

CREATE INDEX IF NOT EXISTS ix_rfid_scan_events_card_uid
    ON public.rfid_scan_events (card_uid);
CREATE INDEX IF NOT EXISTS ix_rfid_scan_events_rfid_card_id
    ON public.rfid_scan_events (rfid_card_id);
ALTER TABLE public.rfid_scan_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.rfid_scan_events FROM PUBLIC, anon;
REVOKE INSERT (id, card_uid, rfid_card_id, scan_session_id, scanned_at, processed_at)
    ON TABLE public.rfid_scan_events FROM PUBLIC, anon;
GRANT INSERT (card_uid, rfid_card_id, scan_session_id)
    ON TABLE public.rfid_scan_events TO anon;
GRANT USAGE, SELECT ON SEQUENCE public.rfid_scan_events_id_seq TO anon;

DROP POLICY IF EXISTS "ESP32 can submit admin RFID scan event"
    ON public.rfid_scan_events;
CREATE POLICY "ESP32 can submit admin RFID scan event"
    ON public.rfid_scan_events FOR INSERT TO anon
    WITH CHECK (
        EXISTS (
            SELECT 1
            FROM public.rfid_scan_control AS control
            WHERE control.id = 1
              AND control.is_armed = TRUE
              AND control.session_id = scan_session_id
              AND control.expires_at > (NOW() AT TIME ZONE 'UTC')
        )
        AND (
            rfid_card_id IS NULL
            OR EXISTS (
                SELECT 1
                FROM public.rfid_cards AS card
                WHERE card.id = rfid_card_id
                  AND card.card_uid = rfid_scan_events.card_uid
            )
        )
    );

-- Remove previous anon/PUBLIC registry policies. The ESP32 now writes scan events,
-- and the authenticated Flask app creates the official RFIDCard row on confirm.
DO $$
DECLARE
    policy_to_drop TEXT;
BEGIN
    FOR policy_to_drop IN
        SELECT policyname
        FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'rfid_cards'
          AND EXISTS (
              SELECT 1 FROM unnest(roles) AS policy_role(role_name)
              WHERE role_name IN ('anon', 'public')
          )
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.rfid_cards', policy_to_drop);
    END LOOP;
END $$;

ALTER TABLE public.rfid_cards ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.rfid_cards FROM PUBLIC, anon;
REVOKE ALL ON SEQUENCE public.rfid_cards_id_seq FROM PUBLIC, anon;
REVOKE SELECT (id, card_uid, staff_id, status, notes, created_at, last_used_at)
    ON TABLE public.rfid_cards FROM PUBLIC, anon;
REVOKE INSERT (id, card_uid, staff_id, status, notes, created_at, last_used_at)
    ON TABLE public.rfid_cards FROM PUBLIC, anon;
REVOKE UPDATE (id, card_uid, staff_id, status, notes, created_at, last_used_at)
    ON TABLE public.rfid_cards FROM PUBLIC, anon;
GRANT SELECT (id, card_uid, staff_id, status)
    ON TABLE public.rfid_cards TO anon;
GRANT UPDATE (last_used_at) ON TABLE public.rfid_cards TO anon;

CREATE POLICY "ESP32 can read RFID cards"
    ON public.rfid_cards FOR SELECT TO anon
    USING (TRUE);

CREATE POLICY "ESP32 can refresh RFID last used"
    ON public.rfid_cards FOR UPDATE TO anon
    USING (status IN ('pending', 'active', 'inactive', 'blocked'))
    WITH CHECK (status IN ('pending', 'active', 'inactive', 'blocked'));

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
