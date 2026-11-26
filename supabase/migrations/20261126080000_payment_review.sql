-- Resolución de pagos pendientes (transferencia, PSE, Nequi) desde el panel.
-- El servidor solo puede cambiar el estado y la fecha de pago; el monto, el método,
-- el comprobante y la factura asociada siguen inmutables. Cada cambio agrega un
-- evento `adjustment` a integrity_ledger en la misma transacción (ver PHASE1_API.md).
begin;
grant update(status, paid_at) on public.payments to ferrepro_backend;
commit;
