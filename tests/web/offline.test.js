// The offline cache (web/sw.js) must list every file the app needs, and only real files.
import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";

const WEB = new URL("../../web/", import.meta.url).pathname;

function walk(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? walk(join(dir, e.name)) : [relative(WEB, join(dir, e.name))]);
}

test("service worker caches exactly the app's files", () => {
  const src = readFileSync(join(WEB, "sw.js"), "utf8");
  const listed = [...src.matchAll(/"\.\/([^"]*)"/g)].map((m) => m[1]).filter(Boolean);
  for (const f of listed) assert.ok(existsSync(join(WEB, f)), `listed but missing: ${f}`);
  const needed = walk(WEB).filter((f) => !/^_headers$|LICENSE|^sw\.js$/.test(f));
  for (const f of needed) assert.ok(listed.includes(f), `not cached for offline use: ${f}`);
});
