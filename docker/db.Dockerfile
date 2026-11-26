# PostgreSQL local con el mismo esquema, RLS y datos de Supabase.
# Los scripts se copian a la imagen (no se montan), asi funciona en cualquier unidad y en CI.
# Corren en orden alfabetico solo cuando el volumen de datos esta vacio.
FROM postgres:17-alpine
COPY docker/postgres-init/00_supabase_roles.sql /docker-entrypoint-initdb.d/00_supabase_roles.sql
COPY supabase/schema.sql /docker-entrypoint-initdb.d/10_schema.sql
COPY supabase/migrations/20261125233808_phase1_billing.sql /docker-entrypoint-initdb.d/15_phase1_billing.sql
COPY supabase/rls_policies.sql /docker-entrypoint-initdb.d/20_rls_policies.sql
COPY supabase/seed.sql /docker-entrypoint-initdb.d/30_seed.sql
COPY docker/postgres-init/40_backend_password.sh /docker-entrypoint-initdb.d/40_backend_password.sh
