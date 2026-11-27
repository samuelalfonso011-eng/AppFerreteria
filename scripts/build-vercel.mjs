import { copyFile, mkdir, readFile, writeFile } from "node:fs/promises";

const root = new URL("../", import.meta.url);
const output = new URL("dist/", root);
const config = JSON.parse(await readFile(new URL("vercel.json", root), "utf8"));
const api = config.rewrites.find(rule => rule.source === "/api/:path*");
const offline = api?.destination === "/api/unavailable";
const local = api?.destination === "/api/index"; // función Flask de este mismo proyecto (api/index.py)
if (!offline && !local && !/^https:\/\/[a-z0-9.-]+(?::\d+)?\/api\/:path\*$/i.test(api?.destination || "")) {
  throw new Error("Configura en vercel.json el destino HTTPS de la API.");
}
const assets = [
  "index.html", "admin.html", "styles.css", "admin.css",
  "theme.css", "app.js", "admin.js", "theme-init.js",
];
await mkdir(output, { recursive: true });
for (const name of assets) {
  const source = new URL(name, root);
  const target = new URL(name, output);
  if (name.endsWith(".html") && offline) {
    const page = await readFile(source, "utf8");
    const notice = '<p role="status">El servidor de la tienda está desconectado. El catálogo, el inicio de sesión y los pedidos estarán disponibles cuando se conecte.</p>';
    await writeFile(target, page.replace("<main>", "<main>" + notice));
  } else {
    await copyFile(source, target);
  }
}
