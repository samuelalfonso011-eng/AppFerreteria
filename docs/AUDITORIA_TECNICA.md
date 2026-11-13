# Auditoría técnica — 13 de noviembre de 2026

## Alcance y estado
Auditoría y correcciones en cinco fases sobre Flask, SQLAlchemy, formularios, plantillas, CSS y JavaScript. Se preservaron cambios previos del usuario. No se desplegó ni migró la base de datos existente. Este informe distingue correcciones de propuestas pendientes; no certifica cumplimiento legal ni ausencia de vulnerabilidades.

## 1. Rendimiento
- `app/services/cart_service.py`: sincronización del carrito con mapa por producto y consulta en lote. Antes, búsqueda repetida O(g·c) y consultas por producto; ahora O(g+c) de procesamiento y consultas acotadas. Serialización compartida y cantidades de sesión validadas.
- `app/services/inventory_service.py:84`: agregación de cantidades duplicadas y bloqueo de productos en una consulta ordenada. Antes O(n) consultas; ahora una consulta de productos, manteniendo O(n) de procesamiento y escrituras por movimiento. Valida toda la compra antes de descontar.
- `app/models/category.py:13`: candidatos de slug consultados una vez; búsqueda en set. Antes k consultas para k colisiones; ahora una consulta y O(k) de memoria/procesamiento.
- `app/routes/admin/dashboard.py`: siete sumas diarias sustituidas por agregación SQL y conteos de estado agrupados. Intervalos temporales semiabiertos. Carga anticipada de relaciones en listados administrativos.
- Índices compuestos para pedidos, pagos, inventario y productos; comando aditivo para instalaciones existentes.
- Pendiente: reemplazar `cat.products.count()` en home, `c.products.count()` en categorías y `c.orders.count()` en clientes por conteos agrupados y mapas por ID. En público contar solo productos activos. Paginar historial de cliente y alertas; usar búsqueda remota en creación manual de pedidos.
- No se convirtió Flask a async: las consultas SQLAlchemy actuales son síncronas. Para correo e imágenes costosas, propuesta concreta: cola de trabajos con estado persistido, reintentos e idempotencia. No afirmar que un timeout de hilo cancela trabajo.

## 2. Código y transacciones
- `clear_cart(commit=False)` permite que pedido, stock, autorización y vaciado confirmen juntos. Prueba de fallo de commit verifica rollback.
- Caché aislada por aplicación; invalidación después del commit, descarte en rollback y listeners registrados una sola vez.
- JSON de gateway malformado se maneja con excepciones específicas; errores de imagen se registran sin ocultarlos silenciosamente.
- Formularios aceptan cero donde es válido. Validación de enteros rechaza booleanos, fracciones y límites excesivos.
- Pendiente: `StoreSetting.get_settings()` no debería escribir desde una lectura; inicializar configuración en migración. Dividir creación manual de pedidos y factoría de aplicación en funciones pequeñas. Revisar o retirar `worker_guard`, que no garantiza cancelación del hilo. Caché local requiere estrategia compartida para varios procesos.

## 3. Seguridad
- Crítico corregido en nuevos datos demo: cuenta técnica inactiva y contraseña aleatoria; seed bloqueado en producción. Instalaciones anteriores requieren ejecutar el comando de revocación indicado abajo.
- Sesiones vinculadas a huella de contraseña; cambio de contraseña o desactivación invalida acceso. IDs de sesión antiguos dejan de aceptarse.
- ProxyFix desactivado por defecto; número explícito de proxies confiables. Producción exige secreto fuerte y hosts permitidos.
- Respuestas dinámicas no-store, CSRF JSON coherente, límites en checkout/pago, validación estricta de cantidades y URLs de retorno.
- Idempotencia comprueba propietario. Cancelación y expiración vuelven a validar bajo bloqueo. Bloqueo SQL evita relaciones externas incompatibles con PostgreSQL FOR UPDATE.
- Pendiente de producción: pruebas concurrentes con PostgreSQL real, almacén compartido de rate limiting, auditoría de dependencias con versiones fijadas y envío real de recuperación por SMTP. Los tests SQLite no demuestran garantías de bloqueo de PostgreSQL.

## 4. Privacidad y textos legales
- Autorización expresa sin premarcar y validada en servidor para registro, perfil, direcciones, contacto y checkout. Términos separados del registro.
- Evidencia transaccional con usuario/pedido/contacto, finalidad, versión y fecha; sin almacenar IP por defecto.
- Política de tratamiento y enlaces visibles. Banner con rechazo, aceptación y selección granular; analítica/marketing desactivados inicialmente. Preferencia local con versión y caducidad. Futuras integraciones deben consultar `cookieConsent.allows` antes de cargar o enviar datos.
- Fuentes remotas retiradas. Documentación distingue cookies de localStorage.
- Comprobantes marcados como simulación sin validez fiscal; retiradas credenciales y afirmaciones ficticias de validación DIAN. Campos hash legacy conservados por compatibilidad, sin presentarlos como validación oficial.
- Pendiente del responsable: identidad legal real, canales, encargados, transferencias, calendario de retención/borrado y procedimiento operativo de derechos. Revisar base jurídica de cada finalidad y alcance territorial GDPR. Un checkbox no acredita por sí solo cumplimiento.
- Fuentes: [Ley 1581](https://jurinfo.jep.gov.co/normograma/compilacion/docs/ley_1581_2012.htm), [SIC: autorización](https://sedeelectronica.sic.gov.co/publicaciones/boletin-juridico/concepto/para-el-adecuado-tratamiento-de-los-datos-es-indispensable-la-autorizacion-expresa-previa-e-informada), [privacidad y cookies UE](https://europa.eu/youreurope/business/growing/digitalising/online-privacy/index_en.htm), [DIAN: validación](https://micrositios.dian.gov.co/sistema-de-facturacion-electronica/como-verifico-si-una-factura-fue-validada-por-la-dian/).

## 5. Interfaz
- Controles públicos con estilo compartido y etiquetas asociadas; resumen de errores; tema con variables; grids adaptables y textos largos contenidos.
- Estado de envío, prevención de doble envío y restauración al volver desde historial. Alertas no desaparecen antes de ser leídas.
- Navegación nativa conserva scripts y comportamiento de cada página. Movimiento reducido respetado. Preferencias de cookies reabribles.
- Verificación automatizada pública en 320, 768 y 1440 px, claro/oscuro: ver `browser-results.json`. Esta prueba mide HTTP, desbordamiento y errores JS; no sustituye inspección visual completa, teclado, lector de pantalla ni recorridos autenticados.

## Activación sobre una instalación existente
Respaldar la base y ejecutar en una ventana controlada antes de servir formularios nuevos:

```powershell
.\venv\Scripts\python.exe -m flask init-privacy-schema
.\venv\Scripts\python.exe -m flask apply-audit-indexes
.\venv\Scripts\python.exe -m flask disable-legacy-demo-account
```

Configurar `SECRET_KEY`, `TRUSTED_HOSTS` y `TRUSTED_PROXY_HOPS` para el despliegue real. La revocación de la cuenta demo conserva historial. Crear índices puede bloquear tablas durante la operación; planificar según tamaño y motor.

## Validación
Regresiones nuevas en `tests/test_audit_regressions.py`: consultas acotadas, rollback, aislamiento/invalidez de caché, entradas malformadas, CSRF, proxy, sesiones revocadas, privacidad y consentimiento. Suite completa: **124 passed, 10 warnings en 135,56 s**. Advertencias: API legacy de SQLAlchemy en tests, prueba deliberada de imagen excesiva y caché de pytest. Navegador: **42 comprobaciones, cero estados HTTP erróneos, cero desbordamientos y cero errores JavaScript** en siete rutas públicas, tres anchos y dos temas. JavaScript main, consent y navigation pasa `node --check`.
