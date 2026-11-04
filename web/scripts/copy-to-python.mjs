// Copies web/dist into python/dyui/_static so the pip package serves the built app.
import { cpSync, rmSync, existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const dist = resolve(here, "../dist");
const target = resolve(here, "../../python/dyui/_static");
if (!existsSync(dist)) throw new Error("web/dist missing — run `npm run build` first");
rmSync(target, { recursive: true, force: true });
cpSync(dist, target, { recursive: true });
console.log(`copied ${dist} -> ${target}`);
