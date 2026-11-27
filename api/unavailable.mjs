export default function unavailable(_request, response) {
  response.setHeader("Cache-Control", "private, no-store");
  response.status(503).json({
    error: "backend_unavailable",
    message: "El servidor de la tienda aún no está conectado a este despliegue.",
  });
}
