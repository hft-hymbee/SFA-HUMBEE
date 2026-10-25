BEGIN;
CREATE UNIQUE INDEX IF NOT EXISTS uq_outlets_candidates_phone ON outlets_onboarding_candidates (tenant_id, owner_phone_hmac) WHERE (status IN ('pending_approval','approved','submitted') OR humbee_company_id IS NOT NULL);
CREATE INDEX IF NOT EXISTS ix_outlets_owner_otp_challenges_tenant_id ON outlets_owner_otp_challenges (tenant_id);
CREATE INDEX IF NOT EXISTS ix_outlets_owner_otp_phone ON outlets_owner_otp_challenges (tenant_id, phone_e164_hmac, issued_at);
ALTER TABLE outlets_onboarding_candidates DROP COLUMN IF EXISTS role_results;
ALTER TABLE platform_domain_events ALTER COLUMN aggregate_id TYPE VARCHAR(26);
DROP TABLE IF EXISTS attendance_geofence_configs;
COMMIT;
