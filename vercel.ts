const rawOrigin = process.env.FLASK_API_ORIGIN?.trim();
let apiDestination = "/api/unavailable";
if (rawOrigin) {
  const url = new URL(rawOrigin);
  if (url.protocol !== "https:" || url.username || url.password || url.href !== url.origin + "/") {
    throw new Error("FLASK_API_ORIGIN debe ser un origen HTTPS, sin credenciales, ruta ni parámetros.");
  }
  apiDestination = url.origin + "/api/:path*";
}

export const config = {
  framework: null,
  buildCommand: "node scripts/build-vercel.mjs",
  outputDirectory: "dist",
  rewrites: [
    { source: "/admin", destination: "/admin.html" },
    { source: "/api/:path*", destination: apiDestination },
  ],
  headers: [
    { source: "/(.*)", headers: [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      { key: "Content-Security-Policy", value: "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'" },
    ] },
    { source: "/api/:path*", headers: [{ key: "Cache-Control", value: "private, no-store" }] },
    { source: "/admin", headers: [{ key: "X-Robots-Tag", value: "noindex, nofollow" }] },
  ],
};
