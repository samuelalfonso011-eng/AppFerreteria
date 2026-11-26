begin;
set local search_path = public, pg_catalog;
CREATE TABLE IF NOT EXISTS data_quality_runs (
	id SERIAL NOT NULL,
	executed_at TIMESTAMP WITH TIME ZONE NOT NULL,
	executed_by INTEGER NOT NULL,
	total_records_scanned INTEGER NOT NULL,
	issues_found INTEGER NOT NULL,
	auto_fixed_count INTEGER NOT NULL,
	pending_review_count INTEGER NOT NULL,
	quality_score NUMERIC(5, 2) NOT NULL,
	summary_by_module JSONB NOT NULL,
	PRIMARY KEY (id),
	CHECK (quality_score BETWEEN 0 AND 100),
	FOREIGN KEY(executed_by) REFERENCES users (id)
);
alter table public.data_quality_runs enable row level security;
revoke all on public.data_quality_runs from public, anon, authenticated, service_role;
CREATE TABLE IF NOT EXISTS data_quality_issues (
	id SERIAL NOT NULL,
	run_id INTEGER NOT NULL,
	module VARCHAR(16) NOT NULL,
	entity_id INTEGER NOT NULL,
	issue_type VARCHAR(24) NOT NULL,
	severity VARCHAR(8) NOT NULL,
	status VARCHAR(16) NOT NULL,
	original_value TEXT,
	normalized_value TEXT,
	details JSONB NOT NULL,
	PRIMARY KEY (id),
	CHECK (module IN ('users','categories','products','orders','invoices','payments')),
	CHECK (issue_type IN ('duplicate_candidate','inconsistent_category','invalid_price','malformed_string','missing_field')),
	CHECK (severity IN ('low','medium','high')),
	CHECK (status IN ('auto_fixed','pending_review','resolved')),
	FOREIGN KEY(run_id) REFERENCES data_quality_runs (id)
);
CREATE INDEX IF NOT EXISTS ix_data_quality_issues_run_id ON data_quality_issues (run_id);
alter table public.data_quality_issues enable row level security;
revoke all on public.data_quality_issues from public, anon, authenticated, service_role;
CREATE TABLE IF NOT EXISTS anomaly_alerts (
	id SERIAL NOT NULL,
	user_id INTEGER NOT NULL,
	user_role VARCHAR(12) NOT NULL,
	alert_type VARCHAR(32) NOT NULL,
	anomaly_score NUMERIC(5, 2) NOT NULL,
	threshold_info JSONB NOT NULL,
	explanation TEXT NOT NULL,
	source_record_ids JSONB NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (user_id, user_role, alert_type),
	CHECK (user_role IN ('customer','employee')),
	CHECK (alert_type IN ('high_amount_outlier','excessive_cancellations','abusive_discounts','unusual_frequency')),
	CHECK (anomaly_score BETWEEN 0 AND 100),
	FOREIGN KEY(user_id) REFERENCES users (id)
);
alter table public.anomaly_alerts enable row level security;
revoke all on public.anomaly_alerts from public, anon, authenticated, service_role;
revoke all on public.data_quality_runs from public, anon, authenticated, service_role, ferrepro_backend;
grant select, insert on public.data_quality_runs to ferrepro_backend;
grant select on public.data_quality_runs to service_role;
revoke all on sequence public.data_quality_runs_id_seq from public, anon, authenticated, service_role;
grant usage on sequence public.data_quality_runs_id_seq to ferrepro_backend;
drop policy if exists server_access on public.data_quality_runs;
create policy server_access on public.data_quality_runs to ferrepro_backend using (true) with check (true);
revoke all on public.data_quality_issues from public, anon, authenticated, service_role, ferrepro_backend;
grant select, insert on public.data_quality_issues to ferrepro_backend;
grant select on public.data_quality_issues to service_role;
revoke all on sequence public.data_quality_issues_id_seq from public, anon, authenticated, service_role;
grant usage on sequence public.data_quality_issues_id_seq to ferrepro_backend;
drop policy if exists server_access on public.data_quality_issues;
create policy server_access on public.data_quality_issues to ferrepro_backend using (true) with check (true);
revoke all on public.anomaly_alerts from public, anon, authenticated, service_role, ferrepro_backend;
grant select, insert, update, delete on public.anomaly_alerts to ferrepro_backend;
grant select on public.anomaly_alerts to service_role;
revoke all on sequence public.anomaly_alerts_id_seq from public, anon, authenticated, service_role;
grant usage on sequence public.anomaly_alerts_id_seq to ferrepro_backend;
drop policy if exists server_access on public.anomaly_alerts;
create policy server_access on public.anomaly_alerts to ferrepro_backend using (true) with check (true);
commit;
