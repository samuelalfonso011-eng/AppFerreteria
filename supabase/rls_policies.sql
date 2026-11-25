-- El servidor Flask autentica al administrador y valida cada checkout.
begin;
revoke all on public.cache_versions, public.categories, public.orders, public.store_settings, public.users, public.order_status_history, public.privacy_consents, public.products, public.inventory_movements, public.order_items, public.legal_consents from public, anon, authenticated;
grant select on public.categories, public.products to anon, authenticated;
drop policy if exists catalog_categories on public.categories;
create policy catalog_categories on public.categories for select to anon, authenticated
using (is_active);
drop policy if exists catalog_products on public.products;
create policy catalog_products on public.products for select to anon, authenticated
using (is_active and exists (select from public.categories c where c.id = category_id and c.is_active));

-- Rol reservado al servidor. La clave se asigna fuera del repositorio.
do $$ begin
    if not exists (select from pg_roles where rolname = 'ferrepro_backend') then
        create role ferrepro_backend login;
    end if;
end $$;
grant usage on schema public to ferrepro_backend;
grant select, insert, update, delete on public.auth_sessions to ferrepro_backend, service_role;
drop policy if exists server_access on public.auth_sessions;
create policy server_access on public.auth_sessions to ferrepro_backend using (true) with check (true);

grant select, insert, update, delete on public.cache_versions, public.categories, public.orders, public.store_settings, public.users, public.order_status_history, public.privacy_consents, public.products, public.inventory_movements, public.order_items to ferrepro_backend, service_role;
grant select on public.legal_consents to ferrepro_backend, service_role;
drop policy if exists server_access on public.cache_versions;
create policy server_access on public.cache_versions to ferrepro_backend using (true) with check (true);
drop policy if exists server_access on public.categories;
create policy server_access on public.categories to ferrepro_backend using (true) with check (true);
grant usage, select on sequence public.categories_id_seq to ferrepro_backend, service_role;
drop policy if exists server_access on public.orders;
create policy server_access on public.orders to ferrepro_backend using (true) with check (true);
grant usage, select on sequence public.orders_id_seq to ferrepro_backend, service_role;
drop policy if exists server_access on public.store_settings;
create policy server_access on public.store_settings to ferrepro_backend using (true) with check (true);
grant usage, select on sequence public.store_settings_id_seq to ferrepro_backend, service_role;
drop policy if exists server_access on public.users;
create policy server_access on public.users to ferrepro_backend using (true) with check (true);
grant usage, select on sequence public.users_id_seq to ferrepro_backend, service_role;
drop policy if exists server_access on public.order_status_history;
create policy server_access on public.order_status_history to ferrepro_backend using (true) with check (true);
grant usage, select on sequence public.order_status_history_id_seq to ferrepro_backend, service_role;
drop policy if exists server_access on public.privacy_consents;
create policy server_access on public.privacy_consents to ferrepro_backend using (true) with check (true);
grant usage, select on sequence public.privacy_consents_id_seq to ferrepro_backend, service_role;
drop policy if exists server_access on public.products;
create policy server_access on public.products to ferrepro_backend using (true) with check (true);
grant usage, select on sequence public.products_id_seq to ferrepro_backend, service_role;
drop policy if exists server_access on public.inventory_movements;
create policy server_access on public.inventory_movements to ferrepro_backend using (true) with check (true);
grant usage, select on sequence public.inventory_movements_id_seq to ferrepro_backend, service_role;
drop policy if exists server_access on public.order_items;
create policy server_access on public.order_items to ferrepro_backend using (true) with check (true);
grant usage, select on sequence public.order_items_id_seq to ferrepro_backend, service_role;
commit;
