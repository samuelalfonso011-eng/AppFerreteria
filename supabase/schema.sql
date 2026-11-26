-- FerrePro: contrato PostgreSQL del ORM de la Fase 2.

begin;

set local search_path = public, pg_catalog;

CREATE TABLE IF NOT EXISTS cache_versions (
	scope VARCHAR(30) NOT NULL, 
	token VARCHAR(32) NOT NULL, 
	PRIMARY KEY (scope)
);

alter table public.cache_versions enable row level security;

revoke all on table public.cache_versions from public, anon, authenticated;

CREATE TABLE IF NOT EXISTS categories (
	id SERIAL NOT NULL, 
	name VARCHAR(80) NOT NULL, 
	slug VARCHAR(100) NOT NULL, 
	headline VARCHAR(120), 
	art VARCHAR(20) DEFAULT 'wrench' NOT NULL, 
	sort_order INTEGER DEFAULT '0' NOT NULL, 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);

CREATE INDEX IF NOT EXISTS ix_categories_is_active ON categories (is_active);

CREATE UNIQUE INDEX IF NOT EXISTS ix_categories_slug ON categories (slug);

alter table public.categories enable row level security;

revoke all on table public.categories from public, anon, authenticated;

CREATE TABLE IF NOT EXISTS orders (
	id SERIAL NOT NULL, 
	order_number VARCHAR(30) NOT NULL, 
	status VARCHAR(30) DEFAULT 'PENDING_CONFIRMATION' NOT NULL, 
	subtotal NUMERIC(12, 2) NOT NULL, 
	shipping_cost NUMERIC(12, 2) DEFAULT '0' NOT NULL, 
	total NUMERIC(12, 2) NOT NULL, 
	idempotency_key VARCHAR(64), 
	customer_name VARCHAR(150) NOT NULL, 
	customer_email VARCHAR(254) NOT NULL, 
	customer_phone VARCHAR(30) NOT NULL, 
	doc_type VARCHAR(10) NOT NULL, 
	doc_number VARCHAR(20) NOT NULL, 
	department VARCHAR(100) NOT NULL, 
	city VARCHAR(100) NOT NULL, 
	neighborhood VARCHAR(100) NOT NULL, 
	street_address VARCHAR(255) NOT NULL, 
	complement VARCHAR(100), 
	notes VARCHAR(500), 
	policy_version VARCHAR(20) NOT NULL, 
	terms_accepted_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	privacy_accepted_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT check_order_subtotal CHECK (subtotal >= 0), 
	CONSTRAINT check_order_shipping CHECK (shipping_cost >= 0), 
	CONSTRAINT check_order_total CHECK (total >= 0), 
	CONSTRAINT check_order_status CHECK (status IN ('PENDING_CONFIRMATION', 'CONFIRMED', 'PREPARING', 'SHIPPED', 'DELIVERED', 'CANCELLED')), 
	UNIQUE (idempotency_key)
);

CREATE INDEX IF NOT EXISTS ix_orders_created_at ON orders (created_at);

CREATE INDEX IF NOT EXISTS ix_orders_customer_email ON orders (customer_email);

CREATE UNIQUE INDEX IF NOT EXISTS ix_orders_order_number ON orders (order_number);

CREATE INDEX IF NOT EXISTS ix_orders_status ON orders (status);

CREATE INDEX IF NOT EXISTS ix_orders_status_created ON orders (status, created_at);

alter table public.orders enable row level security;

revoke all on table public.orders from public, anon, authenticated;

CREATE TABLE IF NOT EXISTS store_settings (
	id SERIAL NOT NULL, 
	store_name VARCHAR(150) DEFAULT 'FerrePro' NOT NULL, 
	legal_name VARCHAR(150) DEFAULT 'FerrePro S.A.S.' NOT NULL, 
	nit VARCHAR(30) DEFAULT '' NOT NULL, 
	address VARCHAR(255) DEFAULT 'Calle 50 # 45-20, Medellín, Antioquia' NOT NULL, 
	phone VARCHAR(50) DEFAULT '+57 300 000 0000' NOT NULL, 
	email VARCHAR(254) DEFAULT 'privacidad@ferrepro.example' NOT NULL, 
	business_hours VARCHAR(255) DEFAULT 'Lunes a viernes de 7:00 a. m. a 6:00 p. m. Sábados de 7:00 a. m. a 2:00 p. m.' NOT NULL, 
	shipping_cost NUMERIC(12, 2) DEFAULT '15000' NOT NULL, 
	free_shipping_threshold NUMERIC(12, 2) DEFAULT '300000', 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT check_setting_shipping CHECK (shipping_cost >= 0)
);

alter table public.store_settings enable row level security;

revoke all on table public.store_settings from public, anon, authenticated;

CREATE TABLE IF NOT EXISTS users (
	id SERIAL NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	full_name VARCHAR(150) NOT NULL, 
	role VARCHAR(20) DEFAULT 'customer' NOT NULL,
	email_verification_pending boolean default false not null, 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	last_login_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT check_user_role CHECK (role IN ('admin', 'customer'))
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email);
create unique index if not exists uq_users_normalized_email on public.users (lower(trim(email)));

alter table public.users enable row level security;

revoke all on table public.users from public, anon, authenticated;

create table if not exists public.auth_sessions (
    id varchar(64) primary key,
    user_id integer not null references public.users(id) on delete cascade,
    expires_at bigint not null
);
create index if not exists ix_auth_sessions_expires_at on public.auth_sessions (expires_at);
alter table public.auth_sessions enable row level security;
revoke all on public.auth_sessions from public, anon, authenticated;


CREATE TABLE IF NOT EXISTS order_status_history (
	id SERIAL NOT NULL, 
	order_id INTEGER NOT NULL, 
	previous_status VARCHAR(30), 
	new_status VARCHAR(30) NOT NULL, 
	changed_by_user_id INTEGER, 
	comment VARCHAR(500), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(order_id) REFERENCES orders (id) ON DELETE CASCADE, 
	FOREIGN KEY(changed_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_order_status_history_order_id ON order_status_history (order_id);

alter table public.order_status_history enable row level security;

revoke all on table public.order_status_history from public, anon, authenticated;

CREATE TABLE IF NOT EXISTS privacy_consents (
	id SERIAL NOT NULL, 
	order_id INTEGER, 
	user_id INTEGER, 
	purpose VARCHAR(30) NOT NULL, 
	document VARCHAR(30) NOT NULL CHECK (document IN ('habeas_data', 'terms')), 
	policy_version VARCHAR(20) NOT NULL, 
	accepted_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(order_id) REFERENCES orders (id) ON DELETE SET NULL, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_privacy_consents_order_id ON privacy_consents (order_id);

CREATE INDEX IF NOT EXISTS ix_privacy_consents_user_id ON privacy_consents (user_id);

alter table public.privacy_consents enable row level security;

revoke all on table public.privacy_consents from public, anon, authenticated;

CREATE TABLE IF NOT EXISTS products (
	id SERIAL NOT NULL, 
	category_id INTEGER NOT NULL, 
	sku VARCHAR(50) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	slug VARCHAR(220) NOT NULL, 
	description TEXT, 
	specs TEXT, 
	price NUMERIC(12, 2) NOT NULL, 
	stock INTEGER DEFAULT '0' NOT NULL, 
	min_stock_alert INTEGER DEFAULT '5' NOT NULL, 
	art VARCHAR(20) DEFAULT 'wrench' NOT NULL, 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT check_product_price CHECK (price >= 0), 
	CONSTRAINT check_product_stock CHECK (stock >= 0), 
	CONSTRAINT check_product_min_stock CHECK (min_stock_alert >= 0), 
	FOREIGN KEY(category_id) REFERENCES categories (id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS ix_products_category_id ON products (category_id);

CREATE INDEX IF NOT EXISTS ix_products_is_active ON products (is_active);

CREATE INDEX IF NOT EXISTS ix_products_name ON products (name);

CREATE UNIQUE INDEX IF NOT EXISTS ix_products_sku ON products (sku);

CREATE UNIQUE INDEX IF NOT EXISTS ix_products_slug ON products (slug);

alter table public.products enable row level security;

revoke all on table public.products from public, anon, authenticated;

CREATE TABLE IF NOT EXISTS inventory_movements (
	id SERIAL NOT NULL, 
	product_id INTEGER NOT NULL, 
	user_id INTEGER, 
	movement_type VARCHAR(30) NOT NULL, 
	quantity INTEGER NOT NULL, 
	previous_stock INTEGER NOT NULL, 
	new_stock INTEGER NOT NULL, 
	reason VARCHAR(255) NOT NULL, 
	reference VARCHAR(100), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT check_movement_quantity CHECK (quantity > 0), 
	CONSTRAINT check_movement_new_stock CHECK (new_stock >= 0), 
	CONSTRAINT check_movement_type CHECK (movement_type IN ('PURCHASE_ENTRY', 'SALE_EXIT', 'ADJUSTMENT_IN', 'ADJUSTMENT_OUT', 'ORDER_CANCEL_RESTORE')), 
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_inventory_movements_created_at ON inventory_movements (created_at);

CREATE INDEX IF NOT EXISTS ix_inventory_movements_movement_type ON inventory_movements (movement_type);

CREATE INDEX IF NOT EXISTS ix_inventory_movements_product_id ON inventory_movements (product_id);

CREATE INDEX IF NOT EXISTS ix_inventory_movements_reference ON inventory_movements (reference);

alter table public.inventory_movements enable row level security;

revoke all on table public.inventory_movements from public, anon, authenticated;

CREATE TABLE IF NOT EXISTS order_items (
	id SERIAL NOT NULL, 
	order_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	product_name VARCHAR(200) NOT NULL, 
	product_sku VARCHAR(50) NOT NULL, 
	unit_price NUMERIC(12, 2) NOT NULL, 
	quantity INTEGER NOT NULL, 
	subtotal NUMERIC(12, 2) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT check_item_price CHECK (unit_price >= 0), 
	CONSTRAINT check_item_quantity CHECK (quantity > 0), 
	CONSTRAINT check_item_subtotal CHECK (subtotal >= 0), 
	FOREIGN KEY(order_id) REFERENCES orders (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS ix_order_items_order_id ON order_items (order_id);

CREATE INDEX IF NOT EXISTS ix_order_items_product_id ON order_items (product_id);

alter table public.order_items enable row level security;

revoke all on table public.order_items from public, anon, authenticated;

alter table categories add column if not exists description text;
alter table products add column if not exists image_url text,
    add column if not exists is_featured boolean not null default false;
alter table orders add column if not exists total_amount numeric(12,2) generated always as (total) stored,
    add column if not exists shipping_address text generated always as
    (street_address || coalesce(', ' || nullif(complement,''),'') || ', ' || neighborhood || ', ' || city || ', ' || department) stored;
alter table privacy_consents add column if not exists ip_address varchar(45);
create unique index if not exists uq_consent_document_per_order on privacy_consents(order_id, document);
create or replace view legal_consents with (security_invoker=true) as
select id, order_id, user_id, document as consent_type, accepted_at, ip_address, policy_version, purpose
from public.privacy_consents;
revoke all on public.legal_consents from public, anon, authenticated;

create or replace function public.touch_updated_at() returns trigger
language plpgsql set search_path = pg_catalog as $$
begin
    new.updated_at = clock_timestamp();
    return new;
end;
$$;

create or replace trigger ferrepro_updated before update on orders
for each row execute function public.touch_updated_at();

create or replace trigger ferrepro_updated before update on store_settings
for each row execute function public.touch_updated_at();

create or replace trigger ferrepro_updated before update on products
for each row execute function public.touch_updated_at();

insert into cache_versions (scope,token) values ('catalog',md5(gen_random_uuid()::text)), ('store',md5(gen_random_uuid()::text)) on conflict do nothing;

insert into store_settings (id) select 1 where not exists (select from store_settings);

select setval(pg_get_serial_sequence('public.store_settings','id'), greatest((select max(id) from store_settings),(select last_value from store_settings_id_seq)));

do $$ begin
if to_regclass('public.invoices') is null then
create table if not exists public.integrity_ledger (
    id bigint generated by default as identity primary key,
    seq_no bigint not null unique check (seq_no > 0),
    entity_type varchar(10) not null check (entity_type in ('invoice','payment')),
    entity_id integer not null check (entity_id > 0),
    event_type varchar(20) not null check (event_type in ('issued','voided','payment_recorded','adjustment')),
    canonical_payload text not null,
    prev_hash varchar(64) not null,
    current_hash varchar(64) not null unique,
    created_at timestamptz not null default now()
);
create index if not exists ix_integrity_entity on public.integrity_ledger(entity_type, entity_id);
create table if not exists public.integrity_verifications (
    id bigint generated by default as identity primary key,
    checked_at timestamptz not null default now(),
    checked_by varchar(40) not null,
    status varchar(12) not null check (status in ('valid','compromised')),
    total_records_checked bigint not null check (total_records_checked >= 0),
    first_broken_seq_no bigint,
    first_broken_entity_type varchar(10),
    first_broken_entity_id integer,
    failure_reason varchar(32),
    details jsonb not null default '{}'
);
alter table public.integrity_ledger enable row level security;
alter table public.integrity_verifications enable row level security;
revoke all on public.integrity_ledger, public.integrity_verifications from public, anon, authenticated, service_role;
end if;
end $$;
commit;
