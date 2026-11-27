import { copyFile, mkdir, readFile, writeFile } from "node:fs/promises";

const root = new URL("../", import.meta.url);
const output = new URL("dist/", root);
const assets = [
  "index.html", "admin.html", "styles.css", "admin.css",
  "theme.css", "app.js", "admin.js", "theme-init.js",
];
await mkdir(output, { recursive: true });
for (const name of assets) {
  const source = new URL(name, root);
  const target = new URL(name, output);
  if (name.endsWith(".html") && !process.env.FLASK_API_ORIGIN?.trim()) {
    const page = await readFile(source, "utf8");
    const notice = '<p role="status">El servidor de la tienda está desconectado. El catálogo, el inicio de sesión y los pedidos estarán disponibles cuando se conecte.</p>';
    await writeFile(target, page.replace("<main>", "<main>" + notice));
  } else {
    await copyFile(source, target);
  }
}
