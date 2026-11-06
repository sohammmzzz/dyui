// Prebuild for the docs site:
//  1. copy brand assets that must live in public/ (favicon) — never edited by hand here,
//     so a logo swap in ../brand propagates on the next build;
//  2. regenerate the component data (src/data/components.json) and the Python API
//     reference (src/content/docs/reference/api/) from the dyui package.
// Python is optional for local work: without it the committed components.json is used
// and the API reference is replaced by a short placeholder page.
import { spawnSync } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const docs = dirname(dirname(fileURLToPath(import.meta.url)));
const repo = dirname(docs);

// 1. brand → public
mkdirSync(join(docs, "public"), { recursive: true });
copyFileSync(join(repo, "brand", "favicon.svg"), join(docs, "public", "favicon.svg"));

// 2. python generators
function findPython() {
  const candidates = [
    process.env.PYTHON,
    join(repo, ".venv", "Scripts", "python.exe"),
    join(repo, ".venv", "bin", "python"),
    "python3",
    "python",
  ].filter(Boolean);
  for (const exe of candidates) {
    const probe = spawnSync(exe, ["-c", "import dyui, griffe"], { encoding: "utf8" });
    if (probe.status === 0) return exe;
  }
  return null;
}

const py = findPython();
const env = { ...process.env, PYTHONIOENCODING: "utf-8" };
const apiDir = join(docs, "src", "content", "docs", "reference", "api");
if (py) {
  for (const script of ["gen_components.py", "gen_api.py"]) {
    const r = spawnSync(py, [join(docs, "scripts", script)], { stdio: "inherit", env });
    if (r.status !== 0) {
      console.error(`prebuild: ${script} failed`);
      process.exit(r.status ?? 1);
    }
  }
} else if (process.env.CI) {
  console.error("prebuild: CI needs Python with `dyui` and `griffe` installed (pip install griffe -e python).");
  process.exit(1);
} else {
  console.warn("prebuild: Python with dyui + griffe not found — using committed component data; API reference skipped.");
  if (!existsSync(join(apiDir, "index.md"))) {
    mkdirSync(apiDir, { recursive: true });
    writeFileSync(
      join(apiDir, "index.md"),
      '---\ntitle: "Python API reference"\ndescription: "Generated at build time."\n---\n\n' +
        "The API reference is generated from the package docstrings at build time. Install `griffe` and the " +
        "`dyui` package (`pip install griffe -e python`) and rebuild to see it.\n",
    );
  }
}
