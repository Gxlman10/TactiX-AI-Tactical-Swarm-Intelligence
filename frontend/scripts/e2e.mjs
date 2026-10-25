import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";

const cwd = fileURLToPath(new URL("..", import.meta.url));
const env = { ...process.env, VITE_API_BASE: "http://127.0.0.1:8018" };
for (const [file, args] of [
  ["typescript/bin/tsc", ["-p", "tsconfig.e2e.json"]],
  ["typescript/bin/tsc", ["-b"]],
  ["vite/bin/vite.js", ["build"]],
  ["@playwright/test/cli.js", ["test", ...process.argv.slice(2)]],
]) {
  const result = spawnSync(
    process.execPath,
    [resolve(cwd, "node_modules", file), ...args],
    {
      cwd,
      env,
      stdio: "inherit",
    },
  );
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}
