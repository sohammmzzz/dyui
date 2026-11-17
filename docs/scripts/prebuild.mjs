// Prebuild for the docs site:
//  1. copy brand assets that must live in public/ (favicon) — never edited by hand here,
//     so a logo swap in ../brand propagates on the next build;
//  2. regenerate the component data (src/data/components.json) and the Python API
//     reference (src/content/docs/reference/api/) from the dyui package;
//  3. copy every complete example into public/examples/ so pages can link a download.
// Python is optional for local work: without it the committed components.json is used
// and the API reference is replaced by a short placeholder page.
import { spawnSync } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
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

// 3. downloadable complete examples → public/examples/ (the "Download app.py" links)
//    examples/<f>.py                     → examples/<f>.py            (cookbook, keeps its name)
//    docs/examples/<section>/<page>.py   → examples/<section>/<page>/app.py
//    components.json  c.app              → examples/components/<name>/app.py
// Always LF and newline-terminated, whatever the checkout's line endings are.
const outDir = join(docs, "public", "examples");
rmSync(outDir, { recursive: true, force: true });
const lf = (text) => text.replace(/\r\n?/g, "\n").replace(/\n*$/, "\n");
const put = (rel, text) => {
  const file = join(outDir, rel);
  mkdirSync(dirname(file), { recursive: true });
  writeFileSync(file, lf(text));
};
let copied = 0;
for (const f of readdirSync(join(repo, "examples"))) {
  if (f.endsWith(".py")) {
    put(f, readFileSync(join(repo, "examples", f), "utf8"));
    copied++;
  }
}
const docExamples = join(docs, "examples");
for (const section of existsSync(docExamples) ? readdirSync(docExamples) : []) {
  for (const f of readdirSync(join(docExamples, section))) {
    if (!f.endsWith(".py")) continue;
    put(join(section, f.replace(/\.py$/, "").replace(/_/g, "-"), "app.py"), readFileSync(join(docExamples, section, f), "utf8"));
    copied++;
  }
}
const { components } = JSON.parse(readFileSync(join(docs, "src", "data", "components.json"), "utf8"));
for (const c of components) {
  if (c.app) {
    put(join("components", c.name, "app.py"), c.app);
    copied++;
  }
}
console.log(`prebuild: ${copied} example files -> public/examples/`);
