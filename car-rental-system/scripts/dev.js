const { spawn } = require("node:child_process");
const path = require("node:path");
const root = path.resolve(__dirname, "..");
const npm = process.platform === "win32" ? "npm.cmd" : "npm";
const demo = process.argv.includes("--demo");
const children = [
  spawn(npm, ["run", demo ? "demo" : "dev"], {
    cwd: path.join(root, "backend"),
    stdio: "inherit",
    shell: process.platform === "win32",
  }),
  spawn(npm, ["run", "dev", "--", "--host", "0.0.0.0"], {
    cwd: path.join(root, "frontend"),
    stdio: "inherit",
    shell: process.platform === "win32",
  }),
];
let stopping = false;
function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) child.kill("SIGTERM");
  process.exitCode = code;
}
for (const child of children) {
  child.on("error", (error) => {
    console.error(error.message);
    stop(1);
  });
  child.on("exit", (code) => {
    if (!stopping) stop(code || 0);
  });
}
process.on("SIGINT", () => stop());
process.on("SIGTERM", () => stop());
