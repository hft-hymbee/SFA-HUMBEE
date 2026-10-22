

CREATE TABLE attendance_days (
	employee_id VARCHAR(26) NOT NULL, 
	business_date DATE NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	first_punch_in_id VARCHAR(26), 
	last_punch_out_id VARCHAR(26), 
	punched_in_at TIMESTAMP WITH TIME ZONE, 
	punched_out_at TIMESTAMP WITH TIME ZONE, 
	punch_in_address TEXT, 
	on_duty BOOLEAN NOT NULL, 
	is_late BOOLEAN NOT NULL, 
	leave_request_id VARCHAR(26), 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_attendance_days PRIMARY KEY (id), 
	CONSTRAINT uq_attendance_days UNIQUE (tenant_id, employee_id, business_date), 
	CONSTRAINT ck_attendance_days_status_chk CHECK (status IN ('present', 'late', 'absent', 'leave', 'no_record')), 
	CONSTRAINT ck_attendance_days_leave_chk CHECK ((status = 'leave') = (leave_request_id IS NOT NULL)), 
	CONSTRAINT ck_attendance_days_on_duty_chk CHECK (on_duty = (first_punch_in_id IS NOT NULL AND last_punch_out_id IS NULL)), 
	CONSTRAINT ck_attendance_days_punch_order_chk CHECK (punched_out_at IS NULL OR punched_in_at IS NULL OR punched_out_at >= punched_in_at)
)

;

CREATE TABLE attendance_export_jobs (
	requested_by VARCHAR(26) NOT NULL, 
	scope VARCHAR(16) NOT NULL, 
	date_from DATE NOT NULL, 
	date_to DATE NOT NULL, 
	format VARCHAR(8) NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	artifact_url TEXT, 
	artifact_expires_at TIMESTAMP WITH TIME ZONE, 
	requested_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	row_count INTEGER, 
	failure_reason TEXT, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_attendance_export_jobs PRIMARY KEY (id), 
	CONSTRAINT ck_attendance_export_jobs_scope_chk CHECK (scope = 'org'), 
	CONSTRAINT ck_attendance_export_jobs_format_chk CHECK (format IN ('csv','xlsx','pdf')), 
	CONSTRAINT ck_attendance_export_jobs_status_chk CHECK (status IN ('queued','running','ready','failed')), 
	CONSTRAINT ck_attendance_export_jobs_range_chk CHECK (date_to >= date_from), 
	CONSTRAINT ck_attendance_export_jobs_ready_chk CHECK (status <> 'ready' OR artifact_url IS NOT NULL)
)

;

CREATE TABLE attendance_gps_fixes (
	latitude NUMERIC(9, 6) NOT NULL, 
	longitude NUMERIC(9, 6) NOT NULL, 
	point geography(POINT,4326) NOT NULL, 
	accuracy_m NUMERIC(7, 2) NOT NULL, 
	altitude_m NUMERIC(7, 2), 
	provider VARCHAR(16) NOT NULL, 
	is_mock_location BOOLEAN NOT NULL, 
	captured_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	resolved_address TEXT, 
	geocode_status VARCHAR(16) NOT NULL, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_attendance_gps_fixes PRIMARY KEY (id), 
	CONSTRAINT ck_attendance_gps_fixes_provider_chk CHECK (provider IN ('gps','network','fused')), 
	CONSTRAINT ck_attendance_gps_fixes_geocode_chk CHECK (geocode_status IN ('ok','failed','pending')), 
	CONSTRAINT ck_attendance_gps_fixes_accuracy_chk CHECK (accuracy_m >= 0)
)

;

CREATE TABLE attendance_official_work_sessions (
	employee_id VARCHAR(26) NOT NULL, 
	work_type VARCHAR(32) NOT NULL, 
	form_definition_id VARCHAR(26) NOT NULL, 
	form_response JSONB NOT NULL, 
	started_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	ended_at TIMESTAMP WITH TIME ZONE, 
	duration_seconds INTEGER, 
	status VARCHAR(16) NOT NULL, 
	start_gps_fix_id VARCHAR(26), 
	end_gps_fix_id VARCHAR(26), 
	idempotency_key VARCHAR(128) NOT NULL, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	occurred_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	received_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	business_date DATE NOT NULL, 
	CONSTRAINT pk_attendance_official_work_sessions PRIMARY KEY (id), 
	CONSTRAINT ck_attendance_official_work_sessions_type_chk CHECK (work_type IN ('meeting','training','collection','other')), 
	CONSTRAINT ck_attendance_official_work_sessions_status_chk CHECK (status IN ('running','completed')), 
	CONSTRAINT ck_attendance_official_work_sessions_end_chk CHECK ((status = 'completed') = (ended_at IS NOT NULL)), 
	CONSTRAINT ck_attendance_official_work_sessions_duration_chk CHECK (duration_seconds IS NULL OR duration_seconds >= 0), 
	CONSTRAINT ck_attendance_official_work_sessions_order_chk CHECK (ended_at IS NULL OR ended_at >= started_at)
)

;

CREATE TABLE attendance_punch_events (
	employee_id VARCHAR(26) NOT NULL, 
	attendance_day_id VARCHAR(26) NOT NULL, 
	direction VARCHAR(8) NOT NULL, 
	gps_fix_id VARCHAR(26) NOT NULL, 
	idempotency_key VARCHAR(128) NOT NULL, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	occurred_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	received_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	business_date DATE NOT NULL, 
	CONSTRAINT pk_attendance_punch_events PRIMARY KEY (id), 
	CONSTRAINT ck_attendance_punch_events_direction_chk CHECK (direction IN ('in','out'))
)

;

CREATE TABLE dim_employee (
	employee_key BIGINT GENERATED ALWAYS AS IDENTITY, 
	tenant_id VARCHAR(64) NOT NULL, 
	employee_id VARCHAR(26) NOT NULL, 
	employee_code TEXT NOT NULL, 
	display_name TEXT NOT NULL, 
	short_name TEXT NOT NULL, 
	initials VARCHAR(3) NOT NULL, 
	role_code VARCHAR(32) NOT NULL, 
	manager_employee_id VARCHAR(26), 
	hierarchy_path LTREE, 
	humbee_region_id VARCHAR(64), 
	region_name TEXT, 
	zone_clusters VARCHAR[] DEFAULT '{}' NOT NULL, 
	state_clusters VARCHAR[] DEFAULT '{}' NOT NULL, 
	district_clusters VARCHAR[] DEFAULT '{}' NOT NULL, 
	shop_categories VARCHAR[] DEFAULT '{}' NOT NULL, 
	beat_area_label TEXT, 
	is_active BOOLEAN NOT NULL, 
	valid_from TIMESTAMP WITH TIME ZONE NOT NULL, 
	valid_to TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT pk_dim_employee PRIMARY KEY (employee_key), 
	CONSTRAINT ck_dim_employee_window_chk CHECK (valid_to IS NULL OR valid_to > valid_from)
)

;

CREATE TABLE fact_employee_manufacturer_day (
	tenant_id VARCHAR(64) NOT NULL, 
	employee_id VARCHAR(26) NOT NULL, 
	business_date DATE NOT NULL, 
	humbee_manufacturer_id VARCHAR(64) NOT NULL, 
	manufacturer_label TEXT NOT NULL, 
	orders_count INTEGER NOT NULL, 
	lines_count INTEGER NOT NULL, 
	net_value_paise BIGINT NOT NULL, 
	qty_by_uom JSONB DEFAULT '{}'::jsonb NOT NULL, 
	computed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	CONSTRAINT pk_fact_employee_manufacturer_day PRIMARY KEY (tenant_id, employee_id, business_date, humbee_manufacturer_id)
)

;

CREATE TABLE fact_employee_outlet_day (
	tenant_id VARCHAR(64) NOT NULL, 
	employee_id VARCHAR(26) NOT NULL, 
	business_date DATE NOT NULL, 
	humbee_outlet_id VARCHAR(64) NOT NULL, 
	humbee_district_id VARCHAR(64), 
	visits_physical INTEGER NOT NULL, 
	visits_telephonic INTEGER NOT NULL, 
	is_scheduled BOOLEAN NOT NULL, 
	orders_count INTEGER NOT NULL, 
	net_value_paise BIGINT NOT NULL, 
	lines_count INTEGER NOT NULL, 
	computed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	CONSTRAINT pk_fact_employee_outlet_day PRIMARY KEY (tenant_id, employee_id, business_date, humbee_outlet_id)
)

;

CREATE TABLE identity_auth_audit_events (
	employee_id VARCHAR(26), 
	phone_e164_hmac VARCHAR(64) NOT NULL, 
	event_type VARCHAR(64) NOT NULL, 
	outcome VARCHAR(32) NOT NULL, 
	requester_ip INET, 
	user_agent TEXT, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	occurred_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	received_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	business_date DATE NOT NULL, 
	CONSTRAINT pk_identity_auth_audit_events PRIMARY KEY (id)
)

;

CREATE TABLE identity_devices (
	employee_id VARCHAR(26) NOT NULL, 
	client_device_id VARCHAR(255) NOT NULL, 
	platform VARCHAR(16) NOT NULL, 
	app_version VARCHAR(64), 
	first_seen_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	last_seen_at TIMESTAMP WITH TIME ZONE, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_identity_devices PRIMARY KEY (id), 
	CONSTRAINT uq_identity_devices UNIQUE (tenant_id, client_device_id), 
	CONSTRAINT ck_identity_devices_platform_chk CHECK (platform IN ('web_pwa','android','ios'))
)

;

CREATE TABLE identity_otp_challenges (
	phone_e164_hmac CHAR(64) NOT NULL, 
	employee_id VARCHAR(26), 
	purpose VARCHAR(16) NOT NULL, 
	code_hash VARCHAR(255) NOT NULL, 
	code_length INTEGER NOT NULL, 
	issued_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	resend_available_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	attempts_used INTEGER NOT NULL, 
	max_attempts INTEGER NOT NULL, 
	consumed_at TIMESTAMP WITH TIME ZONE, 
	requester_ip INET, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_identity_otp_challenges PRIMARY KEY (id), 
	CONSTRAINT ck_identity_otp_challenges_purpose_chk CHECK (purpose IN ('login','reauth')), 
	CONSTRAINT ck_identity_otp_challenges_attempts_chk CHECK (attempts_used BETWEEN 0 AND max_attempts), 
	CONSTRAINT ck_identity_otp_challenges_expiry_chk CHECK (expires_at > issued_at)
)

;

CREATE TABLE identity_sessions (
	employee_id VARCHAR(26) NOT NULL, 
	device_id VARCHAR(26) NOT NULL, 
	access_token_expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	refresh_token_hash VARCHAR(255) NOT NULL, 
	refresh_token_expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	last_seen_at TIMESTAMP WITH TIME ZONE, 
	revoked_at TIMESTAMP WITH TIME ZONE, 
	revocation_reason VARCHAR(32), 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_identity_sessions PRIMARY KEY (id), 
	CONSTRAINT uq_identity_sessions_refresh UNIQUE (refresh_token_hash), 
	CONSTRAINT ck_identity_sessions_revocation_chk CHECK (revocation_reason IS NULL OR revocation_reason IN ('user_logout','deactivated','admin_revoke','token_reuse','refresh_expired')), 
	CONSTRAINT ck_identity_sessions_revoked_pair_chk CHECK ((revoked_at IS NULL) = (revocation_reason IS NULL))
)

;

CREATE TABLE leave_balances (
	employee_id VARCHAR(26) NOT NULL, 
	leave_type VARCHAR(16) NOT NULL, 
	period_year INTEGER NOT NULL, 
	entitled_days NUMERIC(4, 1) NOT NULL, 
	consumed_days NUMERIC(4, 1) NOT NULL, 
	pending_days NUMERIC(4, 1) NOT NULL, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_leave_balances PRIMARY KEY (id), 
	CONSTRAINT ck_leave_balances_leave_balances_type_chk CHECK (leave_type IN ('privileged', 'casual', 'sick')), 
	CONSTRAINT ck_leave_balances_leave_balances_nonneg_chk CHECK (entitled_days >= 0 AND consumed_days >= 0 AND pending_days >= 0)
)

;

CREATE TABLE leave_requests (
	employee_id VARCHAR(26) NOT NULL, 
	leave_type VARCHAR(16) NOT NULL, 
	from_date DATE NOT NULL, 
	to_date DATE NOT NULL, 
	day_count NUMERIC(4, 1) NOT NULL, 
	is_half_day BOOLEAN NOT NULL, 
	reason VARCHAR(500), 
	status VARCHAR(32) NOT NULL, 
	approval_request_id VARCHAR(26) NOT NULL, 
	balance_before NUMERIC(4, 1) NOT NULL, 
	balance_after_projected NUMERIC(4, 1) NOT NULL, 
	applied_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	applied_business_date DATE NOT NULL, 
	decided_at TIMESTAMP WITH TIME ZONE, 
	decision_note TEXT, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_leave_requests PRIMARY KEY (id), 
	CONSTRAINT ck_leave_requests_leave_type_chk CHECK (leave_type IN ('privileged', 'casual', 'sick')), 
	CONSTRAINT ck_leave_requests_leave_status_chk CHECK (status IN ('pending','approved','approved_with_edits','auto_approved','rejected','withdrawn','expired')), 
	CONSTRAINT ck_leave_requests_leave_date_order_chk CHECK (to_date >= from_date), 
	CONSTRAINT ck_leave_requests_leave_day_count_chk CHECK (day_count > 0), 
	CONSTRAINT ck_leave_requests_leave_half_day_chk CHECK (NOT is_half_day OR from_date = to_date), 
	CONSTRAINT leave_no_overlap_excl EXCLUDE USING gist (tenant_id WITH =, employee_id WITH =, daterange(from_date, to_date, '[]') WITH &&) WHERE (status IN ('pending','approved','auto_approved'))
)

;

CREATE TABLE orders (
	order_number TEXT NOT NULL, 
	order_path VARCHAR(32) NOT NULL, 
	seller_type_snapshot VARCHAR(32) NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	sub_status_reason TEXT, 
	cart_draft_id VARCHAR(26), 
	employee_id VARCHAR(26) NOT NULL, 
	visit_id VARCHAR(26), 
	beat_id VARCHAR(26), 
	humbee_outlet_id VARCHAR(64) NOT NULL, 
	outlet_name_snapshot TEXT NOT NULL, 
	outlet_locality_snapshot TEXT, 
	humbee_manufacturer_id VARCHAR(64) NOT NULL, 
	manufacturer_name_snapshot TEXT NOT NULL, 
	humbee_seller_id VARCHAR(64) NOT NULL, 
	seller_name_snapshot TEXT NOT NULL, 
	humbee_buyer_esi_id VARCHAR(64), 
	humbee_seller_esi_id VARCHAR(64), 
	humbee_po_id VARCHAR(64), 
	ship_to_type VARCHAR(16), 
	ship_to_humbee_outlet_id VARCHAR(64), 
	ship_to_humbee_esi_id VARCHAR(64), 
	ship_to_label_snapshot TEXT, 
	shipping_address_line1 VARCHAR(250), 
	shipping_address_line2 VARCHAR(250), 
	shipping_address_state_id VARCHAR(64), 
	shipping_address_district_id VARCHAR(64), 
	shipping_address_pincode VARCHAR(6), 
	seller_confirmed_live BOOLEAN NOT NULL, 
	snapshot_taken_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	snapshot_source_as_of TIMESTAMP WITH TIME ZONE NOT NULL, 
	requires_approval BOOLEAN NOT NULL, 
	approval_request_id VARCHAR(26), 
	approver_employee_id_snapshot VARCHAR(26), 
	approver_name_snapshot TEXT, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	subtotal_net_paise BIGINT NOT NULL, 
	scheme_discount_paise BIGINT NOT NULL, 
	scheme_label_snapshot TEXT, 
	product_discount_paise BIGINT NOT NULL, 
	taxable_base_paise BIGINT NOT NULL, 
	gst_amount_paise BIGINT NOT NULL, 
	gross_total_paise BIGINT NOT NULL, 
	currency CHAR(3) NOT NULL, 
	approved_subtotal_net_paise BIGINT, 
	approved_gross_total_paise BIGINT, 
	dp_sla_deadline_at TIMESTAMP WITH TIME ZONE, 
	dp_sla_breached_at TIMESTAMP WITH TIME ZONE, 
	dp_created_at TIMESTAMP WITH TIME ZONE, 
	downstream_dp_order_ref TEXT, 
	retry_budget_remaining SMALLINT NOT NULL, 
	cancelled_at TIMESTAMP WITH TIME ZONE, 
	idempotency_key TEXT NOT NULL, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	occurred_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	received_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	business_date DATE NOT NULL, 
	CONSTRAINT pk_orders PRIMARY KEY (id), 
	CONSTRAINT uq_orders_number UNIQUE (tenant_id, order_number), 
	CONSTRAINT uq_orders_idem UNIQUE (tenant_id, idempotency_key), 
	CONSTRAINT ck_orders_orders_path_chk CHECK (order_path IN ('po_backed','direct')), 
	CONSTRAINT ck_orders_orders_status_chk CHECK (status IN ('draft','submitted','pending_approval','approved','approved_with_edits','rejected','dp_creation_pending','dp_created','submission_failed','cancelled')), 
	CONSTRAINT ck_orders_orders_ship_to_chk CHECK (ship_to_type IS NULL OR ship_to_type IN ('self','dealer')), 
	CONSTRAINT ck_orders_orders_currency_chk CHECK (currency = 'INR'), 
	CONSTRAINT ck_orders_orders_po_backed_needs_po_chk CHECK (order_path <> 'po_backed' OR humbee_po_id IS NOT NULL), 
	CONSTRAINT ck_orders_orders_direct_no_po_chk CHECK (order_path <> 'direct' OR humbee_po_id IS NULL), 
	CONSTRAINT ck_orders_orders_po_backed_ship_to_chk CHECK (order_path <> 'po_backed' OR ship_to_type IS NOT NULL), 
	CONSTRAINT ck_orders_orders_ship_to_dealer_chk CHECK (ship_to_type <> 'dealer' OR ship_to_humbee_outlet_id IS NOT NULL), 
	CONSTRAINT ck_orders_orders_approval_handle_chk CHECK (requires_approval = false OR approval_request_id IS NOT NULL), 
	CONSTRAINT ck_orders_orders_money_nonneg_chk CHECK (subtotal_net_paise >= 0 AND scheme_discount_paise >= 0 AND product_discount_paise >= 0 AND taxable_base_paise >= 0 AND gst_amount_paise >= 0 AND gross_total_paise >= 0), 
	CONSTRAINT ck_orders_orders_taxable_base_chk CHECK (taxable_base_paise = subtotal_net_paise - scheme_discount_paise - product_discount_paise), 
	CONSTRAINT ck_orders_orders_gross_total_chk CHECK (gross_total_paise = taxable_base_paise + gst_amount_paise), 
	CONSTRAINT ck_orders_orders_scheme_bound_chk CHECK (scheme_discount_paise <= subtotal_net_paise), 
	CONSTRAINT ck_orders_orders_dp_created_ref_chk CHECK (status <> 'dp_created' OR downstream_dp_order_ref IS NOT NULL), 
	CONSTRAINT ck_orders_orders_retry_budget_chk CHECK (retry_budget_remaining >= 0)
)

;

CREATE TABLE orders_cart_drafts (
	employee_id VARCHAR(26) NOT NULL, 
	visit_id VARCHAR(26), 
	humbee_outlet_id VARCHAR(64) NOT NULL, 
	order_path VARCHAR(32) NOT NULL, 
	seller_type_snapshot VARCHAR(32) NOT NULL, 
	humbee_manufacturer_id VARCHAR(64) NOT NULL, 
	humbee_seller_id VARCHAR(64) NOT NULL, 
	humbee_buyer_esi_id VARCHAR(64), 
	humbee_seller_esi_id VARCHAR(64), 
	humbee_po_id VARCHAR(64), 
	ship_to_type VARCHAR(16), 
	ship_to_humbee_outlet_id VARCHAR(64), 
	ship_to_humbee_esi_id VARCHAR(64), 
	shipping_address_line1 VARCHAR(250), 
	shipping_address_line2 VARCHAR(250), 
	shipping_address_state_id VARCHAR(64), 
	shipping_address_district_id VARCHAR(64), 
	shipping_address_pincode VARCHAR(6), 
	scheme_discount_paise BIGINT NOT NULL, 
	scheme_label TEXT, 
	product_discount_paise BIGINT NOT NULL, 
	gross_total_paise BIGINT, 
	status VARCHAR(16) NOT NULL, 
	converted_order_id VARCHAR(26), 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_orders_cart_drafts PRIMARY KEY (id), 
	CONSTRAINT ck_orders_cart_drafts_orders_cart_path_chk CHECK (order_path IN ('po_backed','direct')), 
	CONSTRAINT ck_orders_cart_drafts_orders_cart_status_chk CHECK (status IN ('open','converted','abandoned','expired')), 
	CONSTRAINT ck_orders_cart_drafts_orders_cart_converted_chk CHECK ((status = 'converted') = (converted_order_id IS NOT NULL))
)

;

CREATE TABLE orders_cart_lines (
	cart_draft_id VARCHAR(26) NOT NULL, 
	humbee_product_id VARCHAR(64) NOT NULL, 
	qty INTEGER NOT NULL, 
	form_type VARCHAR(16), 
	unit_price_net_paise BIGINT, 
	unit_price_as_of TIMESTAMP WITH TIME ZONE NOT NULL, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_orders_cart_lines PRIMARY KEY (id), 
	CONSTRAINT uq_orders_cart_lines UNIQUE (cart_draft_id, humbee_product_id), 
	CONSTRAINT ck_orders_cart_lines_orders_cart_lines_qty_chk CHECK (qty >= 1), 
	CONSTRAINT ck_orders_cart_lines_orders_cart_lines_price_chk CHECK (unit_price_net_paise IS NULL OR unit_price_net_paise > 0), 
	CONSTRAINT ck_orders_cart_lines_orders_cart_lines_form_type_chk CHECK (form_type IS NULL OR form_type IN ('STRAIGHT','BEND'))
)

;

CREATE TABLE org_employees (
	employee_code VARCHAR(64) NOT NULL, 
	full_name VARCHAR(255) NOT NULL, 
	first_name VARCHAR(120) NOT NULL, 
	display_initials VARCHAR(3) NOT NULL, 
	role_code VARCHAR(32) NOT NULL, 
	designation_code VARCHAR(64) NOT NULL, 
	status VARCHAR(16) DEFAULT 'active' NOT NULL, 
	login_enabled BOOLEAN DEFAULT true NOT NULL, 
	manager_employee_id VARCHAR(26), 
	joined_on DATE, 
	hierarchy_path LTREE, 
	phone_e164_hmac CHAR(64) NOT NULL, 
	phone_e164_enc BYTEA NOT NULL, 
	phone_last4 CHAR(4) NOT NULL, 
	geo_scope_id VARCHAR(26), 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_org_employees PRIMARY KEY (id), 
	CONSTRAINT uq_org_employees_tenant_phone UNIQUE (tenant_id, phone_e164_hmac), 
	CONSTRAINT uq_org_employees_tenant_code UNIQUE (tenant_id, employee_code), 
	CONSTRAINT ck_org_employees_role_chk CHECK (role_code IN ('sales_person','manager','admin')), 
	CONSTRAINT ck_org_employees_status_chk CHECK (status IN ('active','inactive')), 
	CONSTRAINT ck_org_employees_no_self_parent_chk CHECK (manager_employee_id <> id), 
	CONSTRAINT ck_org_employees_admin_has_no_parent_chk CHECK (role_code <> 'admin' OR manager_employee_id IS NULL), 
	CONSTRAINT ck_org_employees_designation_role_chk CHECK ((role_code = 'admin' AND designation_code = 'admin') OR (role_code = 'manager' AND designation_code IN ('national_sales_head','segment_business_head','regional_sales_manager','area_sales_manager')) OR (role_code = 'sales_person' AND designation_code IN ('network_officer_salesperson','territory_development_officer_salesperson'))), 
	CONSTRAINT fk_org_employees_manager FOREIGN KEY(manager_employee_id) REFERENCES org_employees (id)
)

;

CREATE TABLE outlets (
	humbee_outlet_id VARCHAR(64) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	gstin VARCHAR(15), 
	pan VARCHAR(10), 
	humbee_shop_category_id VARCHAR(64), 
	humbee_district_id VARCHAR(64), 
	as_of TIMESTAMP WITH TIME ZONE NOT NULL, 
	fetched_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_outlets PRIMARY KEY (id), 
	CONSTRAINT uq_outlets_tenant_humbee_outlet UNIQUE (tenant_id, humbee_outlet_id)
)

;

CREATE TABLE outlets_onboarding_candidates (
	captured_by_employee_id VARCHAR(26) NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	approval_request_id VARCHAR(26) NOT NULL, 
	company_name TEXT, 
	fullname TEXT, 
	company_gstin VARCHAR(15), 
	pancard_no VARCHAR(10), 
	owner_phone_hmac CHAR(64) NOT NULL, 
	owner_phone_enc BYTEA NOT NULL, 
	owner_phone_last4 CHAR(4) NOT NULL, 
	payload JSONB NOT NULL, 
	humbee_company_id VARCHAR(64), 
	submitted_at TIMESTAMP WITH TIME ZONE, 
	submission_error TEXT, 
	version INTEGER NOT NULL, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_outlets_onboarding_candidates PRIMARY KEY (id), 
	CONSTRAINT ck_outlets_onboarding_candidates_outlets_candidates_status_chk CHECK (status IN ('pending_approval','approved','submitted','submission_failed','rejected','withdrawn')), 
	CONSTRAINT ck_outlets_onboarding_candidates_outlets_candidates_doc_9081 CHECK (company_name IS NULL OR company_gstin IS NOT NULL OR pancard_no IS NOT NULL), 
	CONSTRAINT ck_outlets_onboarding_candidates_outlets_candidates_named_chk CHECK (company_name IS NOT NULL OR fullname IS NOT NULL), 
	CONSTRAINT ck_outlets_onboarding_candidates_outlets_candidates_sub_f317 CHECK (status <> 'submitted' OR humbee_company_id IS NOT NULL)
)

;

CREATE TABLE outlets_owner_otp_challenges (
	phone_e164_hmac CHAR(64) NOT NULL, 
	code_hash VARCHAR(255) NOT NULL, 
	code_length INTEGER NOT NULL, 
	issued_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	resend_available_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	attempts_used INTEGER NOT NULL, 
	max_attempts INTEGER NOT NULL, 
	consumed_at TIMESTAMP WITH TIME ZONE, 
	requester_ip INET, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_outlets_owner_otp_challenges PRIMARY KEY (id), 
	CONSTRAINT ck_outlets_owner_otp_challenges_owner_otp_attempts_chk CHECK (attempts_used BETWEEN 0 AND max_attempts), 
	CONSTRAINT ck_outlets_owner_otp_challenges_owner_otp_expiry_chk CHECK (expires_at > issued_at)
)

;

CREATE TABLE platform_attachments (
	object_key TEXT NOT NULL, 
	content_type VARCHAR(128) NOT NULL, 
	byte_size BIGINT NOT NULL, 
	checksum_sha256 VARCHAR(64) NOT NULL, 
	subject_type VARCHAR(64) NOT NULL, 
	subject_id VARCHAR(26) NOT NULL, 
	contains_pii BOOLEAN NOT NULL, 
	uploaded_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_platform_attachments PRIMARY KEY (id), 
	CONSTRAINT uq_platform_attachments_key UNIQUE (object_key), 
	CONSTRAINT ck_platform_attachments_size_chk CHECK (byte_size > 0)
)

;

CREATE TABLE platform_audit_logs (
	entity_type VARCHAR(128) NOT NULL, 
	entity_id VARCHAR(26) NOT NULL, 
	from_state VARCHAR(64), 
	to_state VARCHAR(64) NOT NULL, 
	reason TEXT, 
	request_id VARCHAR(64), 
	change_payload JSONB, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_platform_audit_logs PRIMARY KEY (id)
)

;

CREATE TABLE platform_domain_events (
	event_type VARCHAR(128) NOT NULL, 
	aggregate_type VARCHAR(64) NOT NULL, 
	aggregate_id VARCHAR(26) NOT NULL, 
	payload JSONB NOT NULL, 
	occurred_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	received_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	business_date DATE NOT NULL, 
	request_id VARCHAR(64), 
	stream VARCHAR(32) NOT NULL, 
	partition SMALLINT NOT NULL, 
	event_seq BIGINT GENERATED ALWAYS AS IDENTITY, 
	occurred_at_adjusted BOOLEAN NOT NULL, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_platform_domain_events PRIMARY KEY (id), 
	CONSTRAINT uq_platform_domain_events_seq UNIQUE (stream, partition, event_seq), 
	CONSTRAINT ck_platform_domain_events_stream_chk CHECK (stream IN ('org','identity','attendance','routes','beats','orders','approvals','leave','targets','outlets'))
)

;

CREATE TABLE platform_event_quarantine (
	domain_event_id VARCHAR(26) NOT NULL, 
	reason VARCHAR(64) NOT NULL, 
	detail TEXT, 
	quarantined_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	released_at TIMESTAMP WITH TIME ZONE, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_platform_event_quarantine PRIMARY KEY (id)
)

;

CREATE TABLE platform_feature_flags (
	flag_key VARCHAR(128) NOT NULL, 
	enabled BOOLEAN NOT NULL, 
	rollout_rules JSONB, 
	notes TEXT, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_platform_feature_flags PRIMARY KEY (id), 
	CONSTRAINT uq_platform_feature_flags_tenant_key UNIQUE (tenant_id, flag_key)
)

;

CREATE TABLE platform_form_definitions (
	form_key VARCHAR(128) NOT NULL, 
	version INTEGER NOT NULL, 
	schema_payload JSONB NOT NULL, 
	is_published BOOLEAN NOT NULL, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_platform_form_definitions PRIMARY KEY (id), 
	CONSTRAINT uq_platform_form_definitions_key_version UNIQUE (tenant_id, form_key, version)
)

;

CREATE TABLE platform_form_responses (
	form_definition_id VARCHAR(26) NOT NULL, 
	subject_type VARCHAR(64) NOT NULL, 
	subject_id VARCHAR(26) NOT NULL, 
	response_payload JSONB NOT NULL, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_platform_form_responses PRIMARY KEY (id)
)

;

CREATE TABLE platform_idempotency_records (
	idempotency_key VARCHAR(128) NOT NULL, 
	endpoint VARCHAR(128) NOT NULL, 
	request_fingerprint VARCHAR(128) NOT NULL, 
	response_fingerprint VARCHAR(128) NOT NULL, 
	status_code INTEGER NOT NULL, 
	response_payload JSONB NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_platform_idempotency_records PRIMARY KEY (id), 
	CONSTRAINT uq_platform_idempotency UNIQUE (tenant_id, endpoint, idempotency_key)
)

;

CREATE TABLE platform_rate_limit_counters (
	scope VARCHAR(64) NOT NULL, 
	counter_key VARCHAR(128) NOT NULL, 
	window_start TIMESTAMP WITH TIME ZONE NOT NULL, 
	window_seconds INTEGER NOT NULL, 
	hit_count INTEGER NOT NULL, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_platform_rate_limit_counters PRIMARY KEY (id), 
	CONSTRAINT uq_platform_rate_limits_scope_key_window UNIQUE (tenant_id, scope, counter_key, window_start)
)

;

CREATE TABLE platform_runtime_configs (
	config_key VARCHAR(128) NOT NULL, 
	config_value JSONB NOT NULL, 
	config_type VARCHAR(32) NOT NULL, 
	description TEXT, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_platform_runtime_configs PRIMARY KEY (id), 
	CONSTRAINT uq_platform_runtime_configs_tenant_key UNIQUE (tenant_id, config_key)
)

;

CREATE TABLE platform_sweep_runs (
	sweep_type VARCHAR(64) NOT NULL, 
	business_date DATE NOT NULL, 
	started_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	status VARCHAR(16) NOT NULL, 
	rows_affected INTEGER, 
	failure_reason TEXT, 
	trace_id VARCHAR(64), 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_platform_sweep_runs PRIMARY KEY (id), 
	CONSTRAINT uq_platform_sweep_run UNIQUE (tenant_id, sweep_type, business_date), 
	CONSTRAINT ck_platform_sweep_runs_status_chk CHECK (status IN ('running','succeeded','failed','partial'))
)

;

CREATE TABLE reporting_projector_offset (
	stream VARCHAR(32) NOT NULL, 
	partition SMALLINT NOT NULL, 
	last_event_seq BIGINT NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	CONSTRAINT pk_reporting_projector_offset PRIMARY KEY (stream, partition)
)

;

CREATE TABLE routes_combined_visit_feedback (
	combined_visit_id VARCHAR(26) NOT NULL, 
	form_definition_id VARCHAR(26) NOT NULL, 
	overall_rating VARCHAR(16) NOT NULL, 
	responses JSONB NOT NULL, 
	submitted_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	submitted_by_employee_id VARCHAR(26) NOT NULL, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_routes_combined_visit_feedback PRIMARY KEY (id), 
	CONSTRAINT ck_routes_combined_visit_feedback_rating_chk CHECK (overall_rating IN ('good','average','needs_work'))
)

;

CREATE TABLE routes_combined_visits (
	manager_employee_id VARCHAR(26) NOT NULL, 
	sales_person_employee_id VARCHAR(26) NOT NULL, 
	beat_id VARCHAR(26) NOT NULL, 
	humbee_outlet_id VARCHAR(64) NOT NULL, 
	scheduled_business_date DATE NOT NULL, 
	state VARCHAR(32) NOT NULL, 
	visit_id VARCHAR(26), 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_routes_combined_visits PRIMARY KEY (id), 
	CONSTRAINT ck_routes_combined_visits_state_chk CHECK (state IN ('scheduled','completed','feedback_pending','feedback_submitted','cancelled')), 
	CONSTRAINT ck_routes_combined_visits_distinct_chk CHECK (manager_employee_id <> sales_person_employee_id)
)

;

CREATE TABLE routes_missed_visit_audits (
	visit_id VARCHAR(26) NOT NULL, 
	employee_id VARCHAR(26) NOT NULL, 
	business_date DATE NOT NULL, 
	humbee_outlet_id VARCHAR(64) NOT NULL, 
	planned_visit_type VARCHAR(16) NOT NULL, 
	swept_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	sweep_run_id VARCHAR(26) NOT NULL, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_routes_missed_visit_audits PRIMARY KEY (id)
)

;

CREATE TABLE routes_outlet_coordinate_corrections (
	visit_id VARCHAR(26) NOT NULL, 
	humbee_outlet_id VARCHAR(64) NOT NULL, 
	employee_id VARCHAR(26) NOT NULL, 
	latitude NUMERIC(9, 6) NOT NULL, 
	longitude NUMERIC(9, 6) NOT NULL, 
	accuracy_m NUMERIC(7, 2) NOT NULL, 
	provider VARCHAR(16) NOT NULL, 
	captured_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	status VARCHAR(16) DEFAULT 'pending' NOT NULL, 
	rejection_code VARCHAR(64), 
	last_error TEXT, 
	attempts INTEGER DEFAULT 0 NOT NULL, 
	submitted_at TIMESTAMP WITH TIME ZONE, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_routes_outlet_coordinate_corrections PRIMARY KEY (id), 
	CONSTRAINT ck_routes_outlet_coordinate_corrections_status_chk CHECK (status IN ('pending','accepted','rejected','failed')), 
	CONSTRAINT ck_routes_outlet_coordinate_corrections_provider_chk CHECK (provider IN ('gps','network','fused')), 
	CONSTRAINT ck_routes_outlet_coordinate_corrections_accuracy_chk CHECK (accuracy_m >= 0)
)

;

CREATE TABLE routes_plans (
	employee_id VARCHAR(26) NOT NULL, 
	business_date DATE NOT NULL, 
	beat_id VARCHAR(26) NOT NULL, 
	beat_version_id VARCHAR(26) NOT NULL, 
	state VARCHAR(32) NOT NULL, 
	started_at TIMESTAMP WITH TIME ZONE, 
	closed_at TIMESTAMP WITH TIME ZONE, 
	swept_at TIMESTAMP WITH TIME ZONE, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_routes_plans PRIMARY KEY (id), 
	CONSTRAINT ck_routes_plans_state_chk CHECK (state IN ('draft','scheduled','in_progress','closed'))
)

;

CREATE TABLE routes_stops (
	route_plan_id VARCHAR(26) NOT NULL, 
	humbee_outlet_id VARCHAR(64) NOT NULL, 
	sequence_no INTEGER NOT NULL, 
	beat_id VARCHAR(26) NOT NULL, 
	beat_version_id VARCHAR(26) NOT NULL, 
	run_origin VARCHAR(32) NOT NULL, 
	distance_from_prev_km NUMERIC(5, 1), 
	snapshot_name VARCHAR(255) NOT NULL, 
	snapshot_locality VARCHAR(255), 
	snapshot_point geography(POINT,4326), 
	snapshot_category VARCHAR(64), 
	snapshot_as_of TIMESTAMP WITH TIME ZONE NOT NULL, 
	visit_id VARCHAR(26), 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_routes_stops PRIMARY KEY (id), 
	CONSTRAINT uq_routes_stops_outlet UNIQUE (route_plan_id, humbee_outlet_id), 
	CONSTRAINT uq_routes_stops_sequence UNIQUE (route_plan_id, sequence_no) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT ck_routes_stops_sequence_chk CHECK (sequence_no >= 1), 
	CONSTRAINT ck_routes_stops_origin_chk CHECK (run_origin IN ('assigned_beat','unplanned_beat'))
)

;

CREATE TABLE routes_visit_outcomes (
	visit_id VARCHAR(26) NOT NULL, 
	outcome VARCHAR(32) NOT NULL, 
	no_order_reason VARCHAR(32), 
	no_order_note TEXT, 
	photo_attachment_id VARCHAR(26), 
	order_ids VARCHAR[] DEFAULT '{}' NOT NULL, 
	recorded_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_routes_visit_outcomes PRIMARY KEY (id), 
	CONSTRAINT ck_routes_visit_outcomes_outcome_chk CHECK (outcome IN ('order_placed','no_order')), 
	CONSTRAINT ck_routes_visit_outcomes_reason_chk CHECK (no_order_reason IS NULL OR no_order_reason IN ('shop_closed','no_requirement','stock_full','revisit_later','credit_issue','other')), 
	CONSTRAINT ck_routes_visit_outcomes_no_order_chk CHECK (outcome <> 'no_order' OR no_order_reason IS NOT NULL), 
	CONSTRAINT ck_routes_visit_outcomes_order_chk CHECK (outcome <> 'order_placed' OR cardinality(order_ids) >= 1)
)

;

CREATE TABLE routes_visits (
	employee_id VARCHAR(26) NOT NULL, 
	route_plan_id VARCHAR(26), 
	route_stop_id VARCHAR(26), 
	humbee_outlet_id VARCHAR(64) NOT NULL, 
	state VARCHAR(32) NOT NULL, 
	origin VARCHAR(16) NOT NULL, 
	visit_type VARCHAR(16) NOT NULL, 
	planned_for_date DATE, 
	checked_in_at TIMESTAMP WITH TIME ZONE, 
	checked_out_at TIMESTAMP WITH TIME ZONE, 
	checkin_gps geography(POINT,4326), 
	checkin_gps_accuracy_m NUMERIC(7, 2), 
	checkin_gps_provider VARCHAR(16), 
	checkin_gps_is_mock BOOLEAN, 
	note TEXT, 
	combined_visit_id VARCHAR(26), 
	missed_at TIMESTAMP WITH TIME ZONE, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	occurred_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	received_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	business_date DATE NOT NULL, 
	CONSTRAINT pk_routes_visits PRIMARY KEY (id), 
	CONSTRAINT ck_routes_visits_state_chk CHECK (state IN ('scheduled','in_progress','visited_with_order','visited_no_order','missed','cancelled')), 
	CONSTRAINT ck_routes_visits_origin_chk CHECK (origin IN ('planned','unplanned')), 
	CONSTRAINT ck_routes_visits_type_chk CHECK (visit_type IN ('physical','telephonic')), 
	CONSTRAINT ck_routes_visits_telephonic_no_gps_chk CHECK (visit_type <> 'telephonic' OR checkin_gps IS NULL), 
	CONSTRAINT ck_routes_visits_unplanned_state_chk CHECK (origin <> 'unplanned' OR state <> 'scheduled'), 
	CONSTRAINT ck_routes_visits_planned_stop_chk CHECK (origin <> 'planned' OR route_stop_id IS NOT NULL), 
	CONSTRAINT ck_routes_visits_missed_chk CHECK ((state = 'missed') = (missed_at IS NOT NULL))
)

;

CREATE TABLE targets (
	employee_id VARCHAR(26) NOT NULL, 
	target_type VARCHAR(16) NOT NULL, 
	period_type VARCHAR(16) NOT NULL, 
	period_month DATE NOT NULL, 
	target_value BIGINT, 
	outlet_category_scope VARCHAR(32), 
	status VARCHAR(16) NOT NULL, 
	removed_at TIMESTAMP WITH TIME ZONE, 
	removed_by VARCHAR(26), 
	version INTEGER NOT NULL, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_targets PRIMARY KEY (id), 
	CONSTRAINT ck_targets_targets_type_chk CHECK (target_type IN ('sales','outlets','leads')), 
	CONSTRAINT ck_targets_targets_period_type_chk CHECK (period_type = 'month'), 
	CONSTRAINT ck_targets_targets_status_chk CHECK (status IN ('active','removed')), 
	CONSTRAINT ck_targets_targets_month_start_chk CHECK (date_trunc('month', period_month) = period_month), 
	CONSTRAINT ck_targets_targets_value_chk CHECK (target_value IS NULL OR target_value > 0), 
	CONSTRAINT ck_targets_targets_category_scope_chk CHECK ((target_type = 'outlets' AND outlet_category_scope IS NOT NULL) OR (target_type <> 'outlets' AND outlet_category_scope IS NULL)), 
	CONSTRAINT ck_targets_targets_removed_chk CHECK ((status = 'removed') = (removed_at IS NOT NULL))
)

;

CREATE TABLE targets_leads (
	captured_by_employee_id VARCHAR(26) NOT NULL, 
	prospect_name VARCHAR(120) NOT NULL, 
	contact_person VARCHAR(120), 
	contact_designation VARCHAR(120), 
	associated_manufacturer_names VARCHAR(120)[] DEFAULT '{}' NOT NULL, 
	contact_mobile_hmac CHAR(64) NOT NULL, 
	contact_mobile_enc BYTEA NOT NULL, 
	contact_mobile_last4 CHAR(4) NOT NULL, 
	contact_email VARCHAR(255) NOT NULL, 
	company_name VARCHAR(255) NOT NULL, 
	annual_turnover_cr NUMERIC(12, 2), 
	head_office_location VARCHAR(255), 
	interest_level VARCHAR(16) NOT NULL, 
	expected_monthly_units INTEGER, 
	expected_units_uom VARCHAR(32), 
	notes VARCHAR(500), 
	status VARCHAR(16) NOT NULL, 
	humbee_outlet_id VARCHAR(64), 
	geo_point geography(POINT,4326), 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	occurred_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	received_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	business_date DATE NOT NULL, 
	CONSTRAINT pk_targets_leads PRIMARY KEY (id), 
	CONSTRAINT ck_targets_leads_targets_leads_interest_chk CHECK (interest_level IN ('hot','warm','cold')), 
	CONSTRAINT ck_targets_leads_targets_leads_status_chk CHECK (status IN ('captured','in_review','qualified','rejected')), 
	CONSTRAINT ck_targets_leads_targets_leads_prospect_chk CHECK (length(btrim(prospect_name)) >= 2), 
	CONSTRAINT ck_targets_leads_targets_leads_units_chk CHECK (expected_monthly_units IS NULL OR expected_monthly_units > 0), 
	CONSTRAINT ck_targets_leads_targets_leads_company_chk CHECK (length(btrim(company_name)) >= 2), 
	CONSTRAINT ck_targets_leads_targets_leads_turnover_chk CHECK (annual_turnover_cr IS NULL OR annual_turnover_cr > 0), 
	CONSTRAINT ck_targets_leads_targets_leads_manufacturers_chk CHECK (cardinality(associated_manufacturer_names) >= 1)
)

;

CREATE TABLE approvals_requests (
	subject_type VARCHAR(32) NOT NULL, 
	subject_id VARCHAR(26) NOT NULL, 
	subject_version INTEGER NOT NULL, 
	requester_id VARCHAR(26) NOT NULL, 
	requester_manager_id VARCHAR(26), 
	assigned_approver_id VARCHAR(26), 
	routing_reason VARCHAR(32) NOT NULL, 
	escalated_from_id VARCHAR(26), 
	escalation_depth SMALLINT NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	title VARCHAR(120) NOT NULL, 
	subtitle VARCHAR(200) NOT NULL, 
	amount_paise BIGINT, 
	submitted_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	submitted_business_date DATE NOT NULL, 
	decided_at TIMESTAMP WITH TIME ZONE, 
	decided_by_id VARCHAR(26), 
	decision_note TEXT, 
	edit_applied BOOLEAN NOT NULL, 
	sla_due_at TIMESTAMP WITH TIME ZONE, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_approvals_requests PRIMARY KEY (id), 
	CONSTRAINT ck_approvals_requests_subject_type_chk CHECK (subject_type IN ('beat_create','beat_edit','dp_order','leave','outlet_verification')), 
	CONSTRAINT ck_approvals_requests_status_chk CHECK (status IN ('pending','approved','approved_with_edits','auto_approved','rejected','withdrawn','expired')), 
	CONSTRAINT ck_approvals_requests_routing_reason_chk CHECK (routing_reason IN ('direct_parent','escalated_parent_on_leave','auto_top_of_hierarchy')), 
	CONSTRAINT ck_approvals_requests_escalation_depth_chk CHECK (escalation_depth >= 0), 
	CONSTRAINT ck_approvals_requests_amount_chk CHECK (amount_paise IS NULL OR amount_paise >= 0), 
	CONSTRAINT ck_approvals_requests_pending_has_approver_chk CHECK (status <> 'pending' OR assigned_approver_id IS NOT NULL), 
	CONSTRAINT ck_approvals_requests_auto_no_approver_chk CHECK (status <> 'auto_approved' OR assigned_approver_id IS NULL), 
	CONSTRAINT ck_approvals_requests_reject_note_chk CHECK (status <> 'rejected' OR (decision_note IS NOT NULL AND length(btrim(decision_note)) > 0)), 
	CONSTRAINT ck_approvals_requests_terminal_decided_chk CHECK (status = 'pending' OR decided_at IS NOT NULL), 
	CONSTRAINT ck_approvals_requests_escalation_pair_chk CHECK (routing_reason <> 'escalated_parent_on_leave' OR escalated_from_id IS NOT NULL), 
	CONSTRAINT fk_approvals_requests_requester_id_org_employees FOREIGN KEY(requester_id) REFERENCES org_employees (id), 
	CONSTRAINT fk_approvals_requests_requester_manager_id_org_employees FOREIGN KEY(requester_manager_id) REFERENCES org_employees (id), 
	CONSTRAINT fk_approvals_requests_assigned_approver_id_org_employees FOREIGN KEY(assigned_approver_id) REFERENCES org_employees (id), 
	CONSTRAINT fk_approvals_requests_escalated_from_id_org_employees FOREIGN KEY(escalated_from_id) REFERENCES org_employees (id), 
	CONSTRAINT fk_approvals_requests_decided_by_id_org_employees FOREIGN KEY(decided_by_id) REFERENCES org_employees (id)
)

;

CREATE TABLE beats (
	code VARCHAR(64) NOT NULL, 
	display_name VARCHAR(120) NOT NULL, 
	owner_employee_id VARCHAR(26) NOT NULL, 
	lifecycle_state VARCHAR(32) NOT NULL, 
	activation_state VARCHAR(32) NOT NULL, 
	current_version_id VARCHAR(26), 
	draft_version_id VARCHAR(26), 
	deactivation_reason TEXT, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_beats PRIMARY KEY (id), 
	CONSTRAINT uq_beats_tenant_code UNIQUE (tenant_id, code), 
	CONSTRAINT ck_beats_lifecycle_chk CHECK (lifecycle_state IN ('draft','pending_approval','approved','rejected')), 
	CONSTRAINT ck_beats_activation_chk CHECK (activation_state IN ('active','inactive')), 
	CONSTRAINT ck_beats_current_version_chk CHECK ((lifecycle_state = 'approved') = (current_version_id IS NOT NULL)), 
	CONSTRAINT fk_beats_owner_employee_id_org_employees FOREIGN KEY(owner_employee_id) REFERENCES org_employees (id)
)

;

CREATE TABLE fact_employee_day (
	tenant_id VARCHAR(64) NOT NULL, 
	employee_id VARCHAR(26) NOT NULL, 
	business_date DATE NOT NULL, 
	employee_key BIGINT NOT NULL, 
	punched_in BOOLEAN NOT NULL, 
	first_punch_in_at TIMESTAMP WITH TIME ZONE, 
	first_punch_in_local_time TIME WITHOUT TIME ZONE, 
	last_punch_out_at TIMESTAMP WITH TIME ZONE, 
	is_late_punch_in BOOLEAN NOT NULL, 
	on_duty_seconds INTEGER NOT NULL, 
	official_work_seconds INTEGER NOT NULL, 
	official_work_task_count INTEGER NOT NULL, 
	is_leave_day BOOLEAN NOT NULL, 
	leave_type VARCHAR(16), 
	punch_in_location_label TEXT, 
	planned_outlets INTEGER NOT NULL, 
	visited_planned_outlets INTEGER NOT NULL, 
	unplanned_visits INTEGER NOT NULL, 
	visits_total INTEGER NOT NULL, 
	visits_physical INTEGER NOT NULL, 
	visits_telephonic INTEGER NOT NULL, 
	productive_visits INTEGER NOT NULL, 
	missed_visits INTEGER NOT NULL, 
	outlet_seconds INTEGER NOT NULL, 
	travel_seconds INTEGER NOT NULL, 
	idle_seconds INTEGER NOT NULL, 
	distance_metres INTEGER NOT NULL, 
	orders_submitted_count INTEGER NOT NULL, 
	order_lines_count INTEGER NOT NULL, 
	order_net_value_paise BIGINT NOT NULL, 
	order_gross_value_paise BIGINT NOT NULL, 
	orders_approved_count INTEGER NOT NULL, 
	orders_rejected_count INTEGER NOT NULL, 
	orders_edited_on_approval_count INTEGER NOT NULL, 
	orders_submission_failed_count INTEGER NOT NULL, 
	leads_captured_count INTEGER NOT NULL, 
	outlets_onboarded_submitted_count INTEGER NOT NULL, 
	outlets_onboarded_verified_count INTEGER NOT NULL, 
	revision INTEGER NOT NULL, 
	formula_version INTEGER NOT NULL, 
	last_event_at TIMESTAMP WITH TIME ZONE, 
	computed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	CONSTRAINT pk_fact_employee_day PRIMARY KEY (tenant_id, employee_id, business_date), 
	CONSTRAINT fk_fact_employee_day_employee_key_dim_employee FOREIGN KEY(employee_key) REFERENCES dim_employee (employee_key)
)

;

CREATE TABLE orders_lines (
	order_id VARCHAR(26) NOT NULL, 
	line_no SMALLINT NOT NULL, 
	humbee_product_id VARCHAR(64) NOT NULL, 
	product_name_snapshot TEXT NOT NULL, 
	category_snapshot TEXT, 
	form_type VARCHAR(16), 
	pack_size_snapshot TEXT, 
	uom_snapshot TEXT NOT NULL, 
	humbee_manufacturer_id_snapshot VARCHAR(64) NOT NULL, 
	hsn_code_snapshot VARCHAR(16), 
	gst_rate_bp INTEGER NOT NULL, 
	price_source VARCHAR(16) NOT NULL, 
	humbee_po_line_id VARCHAR(64), 
	unit_price_net_paise BIGINT, 
	unit_price_as_of TIMESTAMP WITH TIME ZONE NOT NULL, 
	requested_qty INTEGER NOT NULL, 
	approved_qty INTEGER, 
	line_net_paise BIGINT NOT NULL, 
	line_gst_amount_paise BIGINT NOT NULL, 
	approved_line_net_paise BIGINT, 
	approved_line_gst_amount_paise BIGINT, 
	stock_status_at_add VARCHAR(16) NOT NULL, 
	scheme_code_snapshot TEXT, 
	scheme_line_discount_paise BIGINT NOT NULL, 
	product_line_discount_paise BIGINT NOT NULL, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_orders_lines PRIMARY KEY (id), 
	CONSTRAINT uq_orders_lines_product UNIQUE (order_id, humbee_product_id), 
	CONSTRAINT uq_orders_lines_no UNIQUE (order_id, line_no), 
	CONSTRAINT ck_orders_lines_orders_lines_line_no_chk CHECK (line_no >= 1), 
	CONSTRAINT ck_orders_lines_orders_lines_qty_chk CHECK (requested_qty >= 1), 
	CONSTRAINT ck_orders_lines_orders_lines_price_chk CHECK (unit_price_net_paise IS NULL OR unit_price_net_paise > 0), 
	CONSTRAINT ck_orders_lines_orders_lines_net_chk CHECK (line_net_paise = unit_price_net_paise * requested_qty), 
	CONSTRAINT ck_orders_lines_orders_lines_approved_qty_chk CHECK (approved_qty IS NULL OR approved_qty BETWEEN 0 AND requested_qty), 
	CONSTRAINT ck_orders_lines_orders_lines_approved_net_chk CHECK (approved_qty IS NULL OR approved_line_net_paise = unit_price_net_paise * approved_qty), 
	CONSTRAINT ck_orders_lines_orders_lines_stock_chk CHECK (stock_status_at_add IN ('in_stock','low_stock','out_of_stock','unavailable')), 
	CONSTRAINT ck_orders_lines_orders_lines_scheme_chk CHECK (scheme_line_discount_paise >= 0), 
	CONSTRAINT ck_orders_lines_orders_lines_product_discount_chk CHECK (product_line_discount_paise >= 0), 
	CONSTRAINT ck_orders_lines_orders_lines_gst_rate_chk CHECK (gst_rate_bp BETWEEN 0 AND 10000), 
	CONSTRAINT ck_orders_lines_orders_lines_gst_amount_chk CHECK (line_gst_amount_paise >= 0), 
	CONSTRAINT ck_orders_lines_orders_lines_price_source_chk CHECK (price_source IN ('po_line','price_master')), 
	CONSTRAINT ck_orders_lines_orders_lines_po_line_chk CHECK ((price_source = 'po_line') = (humbee_po_line_id IS NOT NULL)), 
	CONSTRAINT ck_orders_lines_orders_lines_form_type_chk CHECK (form_type IS NULL OR form_type IN ('STRAIGHT','BEND')), 
	CONSTRAINT fk_orders_lines_order_id_orders FOREIGN KEY(order_id) REFERENCES orders (id) ON DELETE CASCADE
)

;

CREATE TABLE orders_po_references (
	order_id VARCHAR(26) NOT NULL, 
	humbee_po_id VARCHAR(64) NOT NULL, 
	po_number_snapshot TEXT NOT NULL, 
	po_status_snapshot VARCHAR(32) NOT NULL, 
	po_manufacturer_id_snapshot VARCHAR(64) NOT NULL, 
	po_manufacturer_name_snapshot TEXT NOT NULL, 
	po_date_snapshot DATE NOT NULL, 
	po_valid_until_snapshot DATE, 
	po_payment_terms_snapshot TEXT, 
	po_credit_days_snapshot SMALLINT, 
	po_net_value_paise_snapshot BIGINT NOT NULL, 
	po_balance_value_paise_snapshot BIGINT NOT NULL, 
	po_as_of TIMESTAMP WITH TIME ZONE NOT NULL, 
	consumed_value_paise BIGINT, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_orders_po_references PRIMARY KEY (id), 
	CONSTRAINT uq_orders_po_order UNIQUE (order_id), 
	CONSTRAINT ck_orders_po_references_orders_po_net_value_chk CHECK (po_net_value_paise_snapshot >= 0), 
	CONSTRAINT ck_orders_po_references_orders_po_balance_value_chk CHECK (po_balance_value_paise_snapshot >= 0), 
	CONSTRAINT fk_orders_po_references_order_id_orders FOREIGN KEY(order_id) REFERENCES orders (id) ON DELETE CASCADE
)

;

CREATE TABLE orders_status_events (
	order_id VARCHAR(26) NOT NULL, 
	seq INTEGER NOT NULL, 
	kind VARCHAR(64) NOT NULL, 
	title TEXT NOT NULL, 
	detail TEXT, 
	occurred_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	timeline_state VARCHAR(16) NOT NULL, 
	actor_employee_id VARCHAR(26), 
	attempt_id VARCHAR(26), 
	visible_to_sp BOOLEAN NOT NULL, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_orders_status_events PRIMARY KEY (id), 
	CONSTRAINT uq_orders_status_events_seq UNIQUE (order_id, seq), 
	CONSTRAINT ck_orders_status_events_orders_status_events_seq_chk CHECK (seq >= 1), 
	CONSTRAINT ck_orders_status_events_orders_status_events_state_chk CHECK (timeline_state IN ('done','current','edited','rejected','todo')), 
	CONSTRAINT fk_orders_status_events_order_id_orders FOREIGN KEY(order_id) REFERENCES orders (id) ON DELETE CASCADE
)

;

CREATE TABLE orders_submission_attempts (
	order_id VARCHAR(26) NOT NULL, 
	attempt_no SMALLINT NOT NULL, 
	trigger VARCHAR(32) NOT NULL, 
	triggered_by_employee_id VARCHAR(26), 
	request_idempotency_key TEXT NOT NULL, 
	request_payload_hash CHAR(64) NOT NULL, 
	started_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	duration_ms INTEGER, 
	outcome VARCHAR(32), 
	failure_class VARCHAR(64), 
	humbee_error_code TEXT, 
	humbee_error_message TEXT, 
	humbee_http_status SMALLINT, 
	sfa_display_reason TEXT, 
	downstream_dp_order_ref TEXT, 
	humbee_accepted_gross_total_paise BIGINT, 
	next_retry_at TIMESTAMP WITH TIME ZONE, 
	trace_id VARCHAR(64) NOT NULL, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_orders_submission_attempts PRIMARY KEY (id), 
	CONSTRAINT uq_orders_attempt_no UNIQUE (order_id, attempt_no), 
	CONSTRAINT ck_orders_submission_attempts_orders_attempt_no_chk CHECK (attempt_no >= 1), 
	CONSTRAINT ck_orders_submission_attempts_orders_attempt_trigger_chk CHECK (trigger IN ('outbox_auto','sla_sweeper','manual_sp_retry','manual_admin_retry','reconciliation')), 
	CONSTRAINT ck_orders_submission_attempts_orders_attempt_outcome_chk CHECK (outcome IS NULL OR outcome IN ('success','failed_retryable','failed_terminal','timeout','circuit_open')), 
	CONSTRAINT ck_orders_submission_attempts_orders_attempt_complete_chk CHECK ((completed_at IS NULL) = (outcome IS NULL)), 
	CONSTRAINT ck_orders_submission_attempts_orders_attempt_reason_chk CHECK (outcome IS NULL OR outcome = 'success' OR sfa_display_reason IS NOT NULL), 
	CONSTRAINT fk_orders_submission_attempts_order_id_orders FOREIGN KEY(order_id) REFERENCES orders (id) ON DELETE CASCADE
)

;

CREATE TABLE org_geography_scope_assignments (
	employee_id VARCHAR(26) NOT NULL, 
	zone_cluster_ids VARCHAR[] DEFAULT '{}'::text[] NOT NULL, 
	state_cluster_ids VARCHAR[] DEFAULT '{}'::text[] NOT NULL, 
	district_cluster_ids VARCHAR[] DEFAULT '{}'::text[] NOT NULL, 
	geo_labels JSONB DEFAULT '{}'::jsonb NOT NULL, 
	assigned_by VARCHAR(26) NOT NULL, 
	assigned_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_org_geography_scope_assignments PRIMARY KEY (id), 
	CONSTRAINT uq_org_geo_scope_employee UNIQUE (tenant_id, employee_id), 
	CONSTRAINT ck_org_geography_scope_assignments_districts_chk CHECK (cardinality(district_cluster_ids) >= 1), 
	CONSTRAINT fk_org_geo_scope_employee FOREIGN KEY(employee_id) REFERENCES org_employees (id), 
	CONSTRAINT fk_org_geo_scope_assigner FOREIGN KEY(assigned_by) REFERENCES org_employees (id)
)

;

CREATE TABLE org_hierarchy_edges (
	ancestor_employee_id VARCHAR(26) NOT NULL, 
	descendant_employee_id VARCHAR(26) NOT NULL, 
	depth INTEGER NOT NULL, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_org_hierarchy_edges PRIMARY KEY (id), 
	CONSTRAINT uq_org_hierarchy_edges UNIQUE (tenant_id, ancestor_employee_id, descendant_employee_id), 
	CONSTRAINT ck_org_hierarchy_edges_depth_chk CHECK (depth >= 0), 
	CONSTRAINT fk_org_hierarchy_ancestor FOREIGN KEY(ancestor_employee_id) REFERENCES org_employees (id), 
	CONSTRAINT fk_org_hierarchy_descendant FOREIGN KEY(descendant_employee_id) REFERENCES org_employees (id)
)

;

CREATE TABLE targets_manufacturer_lines (
	target_id VARCHAR(26) NOT NULL, 
	humbee_manufacturer_id VARCHAR(64) NOT NULL, 
	manufacturer_label_snapshot TEXT NOT NULL, 
	line_basis VARCHAR(16) NOT NULL, 
	uom_label_snapshot TEXT NOT NULL, 
	line_value BIGINT NOT NULL, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_targets_manufacturer_lines PRIMARY KEY (id), 
	CONSTRAINT ck_targets_manufacturer_lines_targets_lines_value_chk CHECK (line_value > 0), 
	CONSTRAINT ck_targets_manufacturer_lines_targets_lines_basis_chk CHECK (line_basis IN ('amount','volume')), 
	CONSTRAINT fk_targets_manufacturer_lines_target_id_targets FOREIGN KEY(target_id) REFERENCES targets (id) ON DELETE CASCADE
)

;

CREATE TABLE approvals_decisions (
	request_id VARCHAR(26) NOT NULL, 
	sequence INTEGER NOT NULL, 
	action VARCHAR(32) NOT NULL, 
	actor_id VARCHAR(26), 
	actor_role VARCHAR(32), 
	note TEXT, 
	edit_patch JSONB, 
	occurred_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_approvals_decisions PRIMARY KEY (id), 
	CONSTRAINT uq_approvals_decisions_seq UNIQUE (request_id, sequence), 
	CONSTRAINT ck_approvals_decisions_action_chk CHECK (action IN ('submitted','routed','escalated','edited','approved','rejected','auto_approved','withdrawn')), 
	CONSTRAINT ck_approvals_decisions_sequence_chk CHECK (sequence >= 1), 
	CONSTRAINT fk_approvals_decisions_request_id_approvals_requests FOREIGN KEY(request_id) REFERENCES approvals_requests (id), 
	CONSTRAINT fk_approvals_decisions_actor_id_org_employees FOREIGN KEY(actor_id) REFERENCES org_employees (id)
)

;

CREATE TABLE beats_activation_events (
	beat_id VARCHAR(26) NOT NULL, 
	action VARCHAR(32) NOT NULL, 
	actor_employee_id VARCHAR(26) NOT NULL, 
	reason TEXT, 
	occurred_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_beats_activation_events PRIMARY KEY (id), 
	CONSTRAINT ck_beats_activation_events_action_chk CHECK (action IN ('deactivated','reactivated')), 
	CONSTRAINT fk_beats_activation_events_beat_id_beats FOREIGN KEY(beat_id) REFERENCES beats (id), 
	CONSTRAINT fk_beats_activation_events_actor_employee_id_org_employees FOREIGN KEY(actor_employee_id) REFERENCES org_employees (id)
)

;

CREATE TABLE beats_versions (
	beat_id VARCHAR(26) NOT NULL, 
	version_no INTEGER NOT NULL, 
	state VARCHAR(32) NOT NULL, 
	display_name VARCHAR(120) NOT NULL, 
	code VARCHAR(64) NOT NULL, 
	geo_scope JSONB NOT NULL, 
	frequency JSONB NOT NULL, 
	outlet_count INTEGER NOT NULL, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	approved_by_employee_id VARCHAR(26), 
	approval_request_id VARCHAR(26), 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_beats_versions PRIMARY KEY (id), 
	CONSTRAINT uq_beats_versions_no UNIQUE (beat_id, version_no), 
	CONSTRAINT ck_beats_versions_state_chk CHECK (state IN ('draft','pending_approval','approved','superseded','rejected','withdrawn')), 
	CONSTRAINT ck_beats_versions_version_no_chk CHECK (version_no >= 1), 
	CONSTRAINT ck_beats_versions_outlet_count_chk CHECK (outlet_count >= 0), 
	CONSTRAINT ck_beats_versions_districts_chk CHECK (jsonb_array_length(geo_scope -> 'districts') >= 1), 
	CONSTRAINT fk_beats_versions_beat_id_beats FOREIGN KEY(beat_id) REFERENCES beats (id), 
	CONSTRAINT fk_beats_versions_approved_by_employee_id_org_employees FOREIGN KEY(approved_by_employee_id) REFERENCES org_employees (id)
)

;

CREATE TABLE notifications (
	recipient_id VARCHAR(26) NOT NULL, 
	kind VARCHAR(32) NOT NULL, 
	title VARCHAR(120) NOT NULL, 
	subtitle VARCHAR(200), 
	deep_link_type VARCHAR(32), 
	deep_link_id VARCHAR(26), 
	source_request_id VARCHAR(26), 
	read_at TIMESTAMP WITH TIME ZONE, 
	dedupe_key VARCHAR(200) NOT NULL, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_notifications PRIMARY KEY (id), 
	CONSTRAINT ck_notifications_kind_chk CHECK (kind IN ('submitted','approved','edited','rejected','auto_approved','escalated','beat','withdrawn')), 
	CONSTRAINT ck_notifications_deep_link_chk CHECK (deep_link_type IS NULL OR deep_link_type IN ('order','beat','leave','outlet','approval_request')), 
	CONSTRAINT ck_notifications_deep_link_pair_chk CHECK ((deep_link_type IS NULL) = (deep_link_id IS NULL)), 
	CONSTRAINT fk_notifications_recipient_id_org_employees FOREIGN KEY(recipient_id) REFERENCES org_employees (id), 
	CONSTRAINT fk_notifications_source_request_id_approvals_requests FOREIGN KEY(source_request_id) REFERENCES approvals_requests (id)
)

;

CREATE TABLE orders_approval_edits (
	order_id VARCHAR(26) NOT NULL, 
	order_line_id VARCHAR(26) NOT NULL, 
	approval_decision_id VARCHAR(26) NOT NULL, 
	product_name_snapshot TEXT NOT NULL, 
	field VARCHAR(16) NOT NULL, 
	before_value INTEGER NOT NULL, 
	after_value INTEGER NOT NULL, 
	edited_by_employee_id VARCHAR(26) NOT NULL, 
	edited_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_orders_approval_edits PRIMARY KEY (id), 
	CONSTRAINT ck_orders_approval_edits_orders_approval_edits_field_chk CHECK (field = 'qty'), 
	CONSTRAINT ck_orders_approval_edits_orders_approval_edits_change_chk CHECK (before_value <> after_value), 
	CONSTRAINT fk_orders_approval_edits_order_id_orders FOREIGN KEY(order_id) REFERENCES orders (id) ON DELETE CASCADE, 
	CONSTRAINT fk_orders_approval_edits_order_line_id_orders_lines FOREIGN KEY(order_line_id) REFERENCES orders_lines (id) ON DELETE CASCADE
)

;

CREATE TABLE orders_po_reference_lines (
	po_reference_id VARCHAR(26) NOT NULL, 
	order_line_id VARCHAR(26), 
	humbee_po_line_id VARCHAR(64) NOT NULL, 
	humbee_product_id VARCHAR(64) NOT NULL, 
	sku_code_snapshot TEXT NOT NULL, 
	sku_name_snapshot TEXT NOT NULL, 
	hsn_code_snapshot VARCHAR(16) NOT NULL, 
	uom_snapshot TEXT NOT NULL, 
	ordered_qty_snapshot INTEGER NOT NULL, 
	fulfilled_qty_snapshot INTEGER NOT NULL, 
	balance_qty_snapshot INTEGER NOT NULL, 
	rate_per_unit_net_paise BIGINT NOT NULL, 
	gst_rate_bp_snapshot INTEGER NOT NULL, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_orders_po_reference_lines PRIMARY KEY (id), 
	CONSTRAINT uq_orders_po_lines UNIQUE (po_reference_id, humbee_po_line_id), 
	CONSTRAINT ck_orders_po_reference_lines_orders_po_lines_qty_chk CHECK (ordered_qty_snapshot >= 0 AND fulfilled_qty_snapshot >= 0 AND balance_qty_snapshot >= 0), 
	CONSTRAINT ck_orders_po_reference_lines_orders_po_lines_balance_chk CHECK (balance_qty_snapshot = ordered_qty_snapshot - fulfilled_qty_snapshot), 
	CONSTRAINT ck_orders_po_reference_lines_orders_po_lines_rate_chk CHECK (rate_per_unit_net_paise > 0), 
	CONSTRAINT ck_orders_po_reference_lines_orders_po_lines_gst_rate_chk CHECK (gst_rate_bp_snapshot BETWEEN 0 AND 10000), 
	CONSTRAINT fk_orders_po_reference_lines_po_reference_id_orders_po__1560 FOREIGN KEY(po_reference_id) REFERENCES orders_po_references (id) ON DELETE CASCADE
)

;

CREATE TABLE beats_edit_requests (
	beat_id VARCHAR(26) NOT NULL, 
	base_version_id VARCHAR(26) NOT NULL, 
	proposed_version_id VARCHAR(26) NOT NULL, 
	state VARCHAR(32) NOT NULL, 
	approval_request_id VARCHAR(26), 
	diff JSONB NOT NULL, 
	submitted_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	submitted_by_employee_id VARCHAR(26) NOT NULL, 
	resolved_at TIMESTAMP WITH TIME ZONE, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_beats_edit_requests PRIMARY KEY (id), 
	CONSTRAINT ck_beats_edit_requests_state_chk CHECK (state IN ('pending_approval','applied','rejected','withdrawn')), 
	CONSTRAINT ck_beats_edit_requests_resolved_chk CHECK ((state = 'pending_approval') = (resolved_at IS NULL)), 
	CONSTRAINT fk_beats_edit_requests_beat_id_beats FOREIGN KEY(beat_id) REFERENCES beats (id), 
	CONSTRAINT fk_beats_edit_requests_base_version_id_beats_versions FOREIGN KEY(base_version_id) REFERENCES beats_versions (id), 
	CONSTRAINT fk_beats_edit_requests_proposed_version_id_beats_versions FOREIGN KEY(proposed_version_id) REFERENCES beats_versions (id), 
	CONSTRAINT fk_beats_edit_requests_submitted_by_employee_id_org_employees FOREIGN KEY(submitted_by_employee_id) REFERENCES org_employees (id)
)

;

CREATE TABLE beats_outlets (
	beat_version_id VARCHAR(26) NOT NULL, 
	outlet_id VARCHAR(26) NOT NULL, 
	sequence_hint INTEGER, 
	id VARCHAR(26) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_by_employee_id VARCHAR(26), 
	on_behalf_of_employee_id VARCHAR(26), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	deactivated_by VARCHAR(26), 
	tenant_id VARCHAR(64) NOT NULL, 
	CONSTRAINT pk_beats_outlets PRIMARY KEY (id), 
	CONSTRAINT uq_beats_outlets UNIQUE (beat_version_id, outlet_id), 
	CONSTRAINT fk_beats_outlets_beat_version_id_beats_versions FOREIGN KEY(beat_version_id) REFERENCES beats_versions (id), 
	CONSTRAINT fk_beats_outlets_outlet_id_outlets FOREIGN KEY(outlet_id) REFERENCES outlets (id)
)

;

CREATE INDEX ix_attendance_days_date ON attendance_days (tenant_id, business_date, status);
CREATE INDEX ix_attendance_days_tenant_id ON attendance_days (tenant_id);
CREATE INDEX ix_attendance_export_jobs_tenant_id ON attendance_export_jobs (tenant_id);
CREATE INDEX ix_attendance_export_queue ON attendance_export_jobs (status, requested_at) WHERE status IN ('queued','running');
CREATE INDEX ix_attendance_gps_fixes_tenant_id ON attendance_gps_fixes (tenant_id);
CREATE INDEX ix_attendance_gps_latest_fix ON attendance_gps_fixes (tenant_id, created_by_employee_id, captured_at);
CREATE INDEX ix_attendance_gps_pending ON attendance_gps_fixes (tenant_id) WHERE geocode_status = 'pending';
CREATE INDEX ix_attendance_gps_point ON attendance_gps_fixes USING gist (point);
CREATE INDEX ix_attendance_official_day ON attendance_official_work_sessions (tenant_id, employee_id, business_date);
CREATE INDEX ix_attendance_official_work_sessions_tenant_id ON attendance_official_work_sessions (tenant_id);
CREATE UNIQUE INDEX uq_attendance_official_idem ON attendance_official_work_sessions (tenant_id, idempotency_key);
CREATE UNIQUE INDEX uq_attendance_official_running ON attendance_official_work_sessions (tenant_id, employee_id) WHERE status = 'running';
CREATE INDEX ix_attendance_punch_day ON attendance_punch_events (attendance_day_id, occurred_at);
CREATE INDEX ix_attendance_punch_emp ON attendance_punch_events (tenant_id, employee_id, business_date, direction);
CREATE INDEX ix_attendance_punch_events_tenant_id ON attendance_punch_events (tenant_id);
CREATE UNIQUE INDEX uq_attendance_punch_idem ON attendance_punch_events (tenant_id, idempotency_key);
CREATE INDEX ix_dim_employee_natural ON dim_employee (tenant_id, employee_id, valid_from DESC);
CREATE INDEX ix_dim_employee_path ON dim_employee USING gist (hierarchy_path);
CREATE UNIQUE INDEX uq_dim_employee_current ON dim_employee (tenant_id, employee_id) WHERE valid_to IS NULL;
CREATE INDEX ix_femd_scope ON fact_employee_manufacturer_day (tenant_id, business_date, humbee_manufacturer_id);
CREATE INDEX ix_fact_employee_outlet_day_key ON fact_employee_outlet_day (tenant_id, employee_id, business_date);
CREATE INDEX ix_fact_employee_outlet_day_outlet ON fact_employee_outlet_day (tenant_id, humbee_outlet_id, business_date);
CREATE INDEX ix_feod_district ON fact_employee_outlet_day (tenant_id, business_date, humbee_district_id);
CREATE INDEX ix_identity_auth_audit_employee ON identity_auth_audit_events (tenant_id, employee_id, business_date);
CREATE INDEX ix_identity_auth_audit_events_tenant_id ON identity_auth_audit_events (tenant_id);
CREATE INDEX ix_identity_auth_audit_phone ON identity_auth_audit_events (tenant_id, phone_e164_hmac, occurred_at);
CREATE INDEX ix_identity_devices_tenant_id ON identity_devices (tenant_id);
CREATE INDEX ix_identity_otp_challenges_tenant_id ON identity_otp_challenges (tenant_id);
CREATE INDEX ix_identity_otp_phone ON identity_otp_challenges (tenant_id, phone_e164_hmac, issued_at);
CREATE UNIQUE INDEX uq_identity_otp_live ON identity_otp_challenges (tenant_id, phone_e164_hmac, purpose) WHERE consumed_at IS NULL;
CREATE INDEX ix_identity_sessions_live ON identity_sessions (tenant_id, employee_id) WHERE revoked_at IS NULL;
CREATE INDEX ix_identity_sessions_tenant_id ON identity_sessions (tenant_id);
CREATE INDEX ix_leave_balances_tenant_id ON leave_balances (tenant_id);
CREATE UNIQUE INDEX uq_leave_balances ON leave_balances (tenant_id, employee_id, leave_type, period_year);
CREATE INDEX ix_leave_mine ON leave_requests (tenant_id, employee_id, from_date DESC);
CREATE INDEX ix_leave_on_leave_oracle ON leave_requests (tenant_id, employee_id, from_date, to_date) WHERE status IN ('approved','auto_approved');
CREATE INDEX ix_leave_requests_tenant_id ON leave_requests (tenant_id);
CREATE UNIQUE INDEX uq_leave_approval_request ON leave_requests (approval_request_id);
CREATE INDEX ix_orders_failed ON orders (tenant_id, business_date DESC) WHERE status = 'submission_failed';
CREATE INDEX ix_orders_mine ON orders (tenant_id, employee_id, business_date DESC);
CREATE INDEX ix_orders_outlet ON orders (tenant_id, humbee_outlet_id, business_date DESC);
CREATE INDEX ix_orders_sla_watch ON orders (dp_sla_deadline_at) WHERE status IN ('approved','approved_with_edits','dp_creation_pending') AND dp_created_at IS NULL;
CREATE INDEX ix_orders_status ON orders (tenant_id, status, business_date DESC);
CREATE INDEX ix_orders_tenant_id ON orders (tenant_id);
CREATE INDEX ix_orders_visit ON orders (tenant_id, visit_id);
CREATE UNIQUE INDEX uq_orders_downstream ON orders (tenant_id, downstream_dp_order_ref) WHERE downstream_dp_order_ref IS NOT NULL;
CREATE INDEX ix_orders_cart_drafts_tenant_id ON orders_cart_drafts (tenant_id);
CREATE INDEX ix_orders_cart_expiry ON orders_cart_drafts (expires_at) WHERE status = 'open';
CREATE UNIQUE INDEX uq_orders_cart_open ON orders_cart_drafts (tenant_id, employee_id, visit_id, humbee_outlet_id, humbee_manufacturer_id) WHERE status = 'open';
CREATE INDEX ix_orders_cart_lines_tenant_id ON orders_cart_lines (tenant_id);
CREATE INDEX ix_org_employees_manager ON org_employees (tenant_id, manager_employee_id);
CREATE INDEX ix_org_employees_role ON org_employees (tenant_id, role_code) WHERE status = 'active';
CREATE INDEX ix_org_employees_tenant_id ON org_employees (tenant_id);
CREATE INDEX ix_outlets_tenant_id ON outlets (tenant_id);
CREATE INDEX ix_outlets_candidates_mine ON outlets_onboarding_candidates (tenant_id, captured_by_employee_id, created_at DESC);
CREATE INDEX ix_outlets_candidates_status ON outlets_onboarding_candidates (tenant_id, status);
CREATE INDEX ix_outlets_onboarding_candidates_tenant_id ON outlets_onboarding_candidates (tenant_id);
CREATE UNIQUE INDEX uq_outlets_candidates_company ON outlets_onboarding_candidates (tenant_id, humbee_company_id) WHERE humbee_company_id IS NOT NULL;
CREATE UNIQUE INDEX uq_outlets_candidates_gstin ON outlets_onboarding_candidates (tenant_id, company_gstin) WHERE company_gstin IS NOT NULL AND (status IN ('pending_approval','approved','submitted') OR humbee_company_id IS NOT NULL);
CREATE UNIQUE INDEX uq_outlets_candidates_pan ON outlets_onboarding_candidates (tenant_id, pancard_no) WHERE pancard_no IS NOT NULL AND (status IN ('pending_approval','approved','submitted') OR humbee_company_id IS NOT NULL);
CREATE UNIQUE INDEX uq_outlets_candidates_phone ON outlets_onboarding_candidates (tenant_id, owner_phone_hmac) WHERE (status IN ('pending_approval','approved','submitted') OR humbee_company_id IS NOT NULL);
CREATE INDEX ix_outlets_owner_otp_challenges_tenant_id ON outlets_owner_otp_challenges (tenant_id);
CREATE INDEX ix_outlets_owner_otp_phone ON outlets_owner_otp_challenges (tenant_id, phone_e164_hmac, issued_at);
CREATE INDEX ix_platform_attachments_subject ON platform_attachments (tenant_id, subject_type, subject_id);
CREATE INDEX ix_platform_attachments_tenant_id ON platform_attachments (tenant_id);
CREATE INDEX ix_platform_audit_actor ON platform_audit_logs (tenant_id, created_by_employee_id, created_at);
CREATE INDEX ix_platform_audit_entity ON platform_audit_logs (tenant_id, entity_type, entity_id, created_at);
CREATE INDEX ix_platform_audit_logs_entity_id ON platform_audit_logs (entity_id);
CREATE INDEX ix_platform_audit_logs_tenant_id ON platform_audit_logs (tenant_id);
CREATE INDEX ix_platform_domain_events_aggregate ON platform_domain_events (aggregate_type, aggregate_id, occurred_at);
CREATE INDEX ix_platform_domain_events_aggregate_id ON platform_domain_events (aggregate_id);
CREATE INDEX ix_platform_domain_events_business_date ON platform_domain_events (business_date);
CREATE INDEX ix_platform_domain_events_day ON platform_domain_events (tenant_id, stream, event_type, business_date);
CREATE INDEX ix_platform_domain_events_plan ON platform_domain_events (tenant_id, stream, event_type, (payload ->> 'employee_id'), (payload ->> 'business_date'));
CREATE INDEX ix_platform_domain_events_replay ON platform_domain_events (stream, partition, event_seq) INCLUDE (aggregate_id, business_date);
CREATE INDEX ix_platform_domain_events_tenant_id ON platform_domain_events (tenant_id);
CREATE INDEX ix_platform_event_quarantine_open ON platform_event_quarantine (tenant_id, quarantined_at) WHERE released_at IS NULL;
CREATE INDEX ix_platform_event_quarantine_tenant_id ON platform_event_quarantine (tenant_id);
CREATE INDEX ix_platform_feature_flags_tenant_id ON platform_feature_flags (tenant_id);
CREATE INDEX ix_platform_form_definitions_tenant_id ON platform_form_definitions (tenant_id);
CREATE INDEX ix_platform_form_responses_subject ON platform_form_responses (tenant_id, subject_type, subject_id);
CREATE INDEX ix_platform_form_responses_tenant_id ON platform_form_responses (tenant_id);
CREATE INDEX ix_platform_idempotency_expiry ON platform_idempotency_records (expires_at);
CREATE INDEX ix_platform_idempotency_records_tenant_id ON platform_idempotency_records (tenant_id);
CREATE INDEX ix_platform_rate_limit_counters_tenant_id ON platform_rate_limit_counters (tenant_id);
CREATE INDEX ix_platform_runtime_configs_tenant_id ON platform_runtime_configs (tenant_id);
CREATE INDEX ix_platform_sweep_runs_tenant_id ON platform_sweep_runs (tenant_id);
CREATE INDEX ix_routes_combined_visit_feedback_tenant_id ON routes_combined_visit_feedback (tenant_id);
CREATE UNIQUE INDEX uq_routes_combined_feedback ON routes_combined_visit_feedback (combined_visit_id);
CREATE INDEX ix_routes_combined_manager ON routes_combined_visits (tenant_id, manager_employee_id, scheduled_business_date);
CREATE INDEX ix_routes_combined_sp ON routes_combined_visits (tenant_id, sales_person_employee_id, scheduled_business_date);
CREATE INDEX ix_routes_combined_visits_tenant_id ON routes_combined_visits (tenant_id);
CREATE INDEX ix_routes_missed_day ON routes_missed_visit_audits (tenant_id, employee_id, business_date);
CREATE INDEX ix_routes_missed_visit_audits_tenant_id ON routes_missed_visit_audits (tenant_id);
CREATE UNIQUE INDEX uq_routes_missed_visit ON routes_missed_visit_audits (visit_id);
CREATE INDEX ix_routes_coord_corr_outlet ON routes_outlet_coordinate_corrections (tenant_id, humbee_outlet_id, captured_at);
CREATE INDEX ix_routes_coord_corr_visit ON routes_outlet_coordinate_corrections (tenant_id, visit_id);
CREATE INDEX ix_routes_outlet_coordinate_corrections_tenant_id ON routes_outlet_coordinate_corrections (tenant_id);
CREATE INDEX ix_routes_plans_sweep ON routes_plans (tenant_id, business_date) WHERE state IN ('scheduled','in_progress');
CREATE INDEX ix_routes_plans_tenant_id ON routes_plans (tenant_id);
CREATE UNIQUE INDEX uq_routes_plans_employee_date ON routes_plans (tenant_id, employee_id, business_date);
CREATE INDEX ix_routes_stops_tenant_id ON routes_stops (tenant_id);
CREATE INDEX ix_routes_visit_outcomes_tenant_id ON routes_visit_outcomes (tenant_id);
CREATE UNIQUE INDEX uq_routes_visit_outcomes_visit ON routes_visit_outcomes (visit_id);
CREATE INDEX ix_routes_visits_day ON routes_visits (tenant_id, employee_id, business_date);
CREATE INDEX ix_routes_visits_gps ON routes_visits USING gist (checkin_gps) WHERE checkin_gps IS NOT NULL;
CREATE UNIQUE INDEX ix_routes_visits_open ON routes_visits (tenant_id, employee_id) WHERE state = 'in_progress';
CREATE INDEX ix_routes_visits_outlet ON routes_visits (tenant_id, humbee_outlet_id, business_date DESC);
CREATE INDEX ix_routes_visits_plan ON routes_visits (route_plan_id, state);
CREATE INDEX ix_routes_visits_tenant_id ON routes_visits (tenant_id);
CREATE INDEX ix_targets_period ON targets (tenant_id, period_month, target_type) WHERE status = 'active';
CREATE INDEX ix_targets_tenant_id ON targets (tenant_id);
CREATE UNIQUE INDEX uq_targets_active ON targets (tenant_id, employee_id, target_type, period_month) WHERE status = 'active';
CREATE INDEX idx_targets_leads_geo_point ON targets_leads USING gist (geo_point);
CREATE INDEX ix_targets_leads_mine ON targets_leads (tenant_id, captured_by_employee_id, business_date DESC);
CREATE INDEX ix_targets_leads_month ON targets_leads (tenant_id, captured_by_employee_id, business_date) WHERE status <> 'rejected';
CREATE INDEX ix_targets_leads_tenant_id ON targets_leads (tenant_id);
CREATE INDEX ix_approvals_inbox ON approvals_requests (tenant_id, assigned_approver_id, status, submitted_at DESC);
CREATE INDEX ix_approvals_mine ON approvals_requests (tenant_id, requester_id, submitted_at DESC);
CREATE INDEX ix_approvals_requests_tenant_id ON approvals_requests (tenant_id);
CREATE INDEX ix_approvals_subject ON approvals_requests (tenant_id, subject_type, subject_id);
CREATE INDEX ix_approvals_sweep ON approvals_requests (tenant_id, submitted_business_date) WHERE status = 'pending';
CREATE UNIQUE INDEX uq_approvals_one_pending_per_subject ON approvals_requests (tenant_id, subject_type, subject_id) WHERE status = 'pending';
CREATE INDEX ix_beats_owner ON beats (tenant_id, owner_employee_id, lifecycle_state);
CREATE INDEX ix_beats_plannable ON beats (tenant_id, owner_employee_id) WHERE lifecycle_state = 'approved' AND activation_state = 'active';
CREATE INDEX ix_beats_tenant_id ON beats (tenant_id);
CREATE INDEX ix_fact_employee_day_mtd ON fact_employee_day (tenant_id, employee_id, business_date DESC);
CREATE INDEX ix_fact_employee_day_scope ON fact_employee_day (tenant_id, business_date, employee_key);
CREATE INDEX ix_orders_lines_tenant_id ON orders_lines (tenant_id);
CREATE INDEX ix_orders_po_humbee ON orders_po_references (tenant_id, humbee_po_id);
CREATE INDEX ix_orders_po_references_tenant_id ON orders_po_references (tenant_id);
CREATE INDEX ix_orders_status_events_sp ON orders_status_events (order_id, seq) WHERE visible_to_sp;
CREATE INDEX ix_orders_status_events_tenant_id ON orders_status_events (tenant_id);
CREATE INDEX ix_orders_attempt_order ON orders_submission_attempts (order_id, attempt_no DESC);
CREATE INDEX ix_orders_attempt_retry ON orders_submission_attempts (next_retry_at) WHERE outcome IN ('failed_retryable','timeout','circuit_open');
CREATE INDEX ix_orders_submission_attempts_tenant_id ON orders_submission_attempts (tenant_id);
CREATE INDEX ix_org_geo_scope_districts_gin ON org_geography_scope_assignments USING gin (district_cluster_ids);
CREATE INDEX ix_org_geography_scope_assignments_tenant_id ON org_geography_scope_assignments (tenant_id);
CREATE INDEX ix_org_hierarchy_edges_descendant ON org_hierarchy_edges (tenant_id, descendant_employee_id, depth);
CREATE INDEX ix_org_hierarchy_edges_tenant_id ON org_hierarchy_edges (tenant_id);
CREATE INDEX ix_org_hierarchy_edges_tree ON org_hierarchy_edges (tenant_id, ancestor_employee_id, depth);
CREATE INDEX ix_targets_manufacturer_lines_tenant_id ON targets_manufacturer_lines (tenant_id);
CREATE UNIQUE INDEX uq_targets_lines ON targets_manufacturer_lines (target_id, humbee_manufacturer_id);
CREATE INDEX ix_approvals_decisions_request ON approvals_decisions (request_id, sequence);
CREATE INDEX ix_approvals_decisions_tenant_id ON approvals_decisions (tenant_id);
CREATE INDEX ix_beats_activation_beat ON beats_activation_events (beat_id, occurred_at DESC);
CREATE INDEX ix_beats_activation_events_tenant_id ON beats_activation_events (tenant_id);
CREATE INDEX ix_beats_versions_tenant_id ON beats_versions (tenant_id);
CREATE UNIQUE INDEX uq_beats_versions_one_approved ON beats_versions (beat_id) WHERE state = 'approved';
CREATE UNIQUE INDEX uq_beats_versions_one_pending ON beats_versions (beat_id) WHERE state = 'pending_approval';
CREATE INDEX ix_notifications_feed ON notifications (tenant_id, recipient_id, created_at DESC);
CREATE INDEX ix_notifications_tenant_id ON notifications (tenant_id);
CREATE INDEX ix_notifications_unread ON notifications (tenant_id, recipient_id) WHERE read_at IS NULL;
CREATE UNIQUE INDEX uq_notifications_dedupe ON notifications (tenant_id, recipient_id, dedupe_key);
CREATE INDEX ix_orders_approval_edits_order ON orders_approval_edits (order_id, edited_at);
CREATE INDEX ix_orders_approval_edits_tenant_id ON orders_approval_edits (tenant_id);
CREATE INDEX ix_orders_po_lines_order_line ON orders_po_reference_lines (order_line_id);
CREATE INDEX ix_orders_po_reference_lines_tenant_id ON orders_po_reference_lines (tenant_id);
CREATE INDEX ix_beats_edit_requests_tenant_id ON beats_edit_requests (tenant_id);
CREATE UNIQUE INDEX uq_beats_edit_one_pending ON beats_edit_requests (beat_id) WHERE state = 'pending_approval';
CREATE INDEX ix_beats_outlets_outlet ON beats_outlets (tenant_id, outlet_id);
CREATE INDEX ix_beats_outlets_tenant_id ON beats_outlets (tenant_id);
