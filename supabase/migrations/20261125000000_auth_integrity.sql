begin;

lock table public.users in share row exclusive mode;
do $$
begin
    if exists (select 1 from public.users group by lower(trim(email)) having count(*) > 1) then
        raise exception 'Hay colisiones de correo. Resuélvelas antes de migrar.';
    end if;

    if not exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'users'
          and column_name = 'email_verification_pending'
    ) then
        alter table public.users add column email_verification_pending boolean not null default false;
        update public.users set email_verification_pending = true
        where role = 'customer' and not is_active and last_login_at is null;
    end if;
end $$;

update public.users set email = lower(trim(email)) where email <> lower(trim(email));
create unique index if not exists uq_users_normalized_email on public.users (lower(trim(email)));

create table if not exists public.auth_sessions (
    id varchar(64) primary key,
    user_id integer not null references public.users(id) on delete cascade,
    expires_at bigint not null
);
create index if not exists ix_auth_sessions_expires_at on public.auth_sessions (expires_at);
alter table public.auth_sessions enable row level security;
revoke all on public.auth_sessions from public, anon, authenticated;
grant select, insert, update, delete on public.auth_sessions to ferrepro_backend, service_role;
drop policy if exists server_access on public.auth_sessions;
create policy server_access on public.auth_sessions to ferrepro_backend using (true) with check (true);

commit;
