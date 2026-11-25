-- Roles que Supabase trae de fabrica. Se crean sin login para que schema.sql y
-- rls_policies.sql se ejecuten sin cambios en un PostgreSQL local.
do $$ begin
    if not exists (select from pg_roles where rolname = 'anon') then
        create role anon nologin;
    end if;
    if not exists (select from pg_roles where rolname = 'authenticated') then
        create role authenticated nologin;
    end if;
    if not exists (select from pg_roles where rolname = 'service_role') then
        create role service_role nologin bypassrls;
    end if;
end $$;
