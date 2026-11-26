-- Cerrar incidencias de calidad revisadas a mano (POST /api/admin/data-quality/issues/{id}/resolve).
-- El servidor solo puede cambiar el estado; valores, tipo y módulo de la incidencia siguen inmutables.
begin;
grant update(status) on public.data_quality_issues to ferrepro_backend;
commit;
