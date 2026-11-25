#!/bin/sh
# Asigna la contrasena del rol de servidor (creado por rls_policies.sql) desde la variable de entorno.
# Se pasa como variable de psql para que nunca aparezca en la linea de comandos ni en el historial.
set -eu
: "${BACKEND_DB_PASSWORD:?Falta BACKEND_DB_PASSWORD}"
psql -v ON_ERROR_STOP=1 -v pw="$BACKEND_DB_PASSWORD" --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'EOSQL'
alter role ferrepro_backend with login password :'pw';
EOSQL
