// Every language file must have exactly the English keys, the same {placeholders},
// and no empty text, so no screen ever shows a raw key or a broken sentence.
import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { LANGUAGES, STRINGS, loadLanguage, t } from "../../web/js/i18n.js";

const placeholders = (text) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(",");
const english = STRINGS.en;

test("Hindi is complete", () => {
  assert.deepEqual(Object.keys(STRINGS.hi).sort(), Object.keys(english).sort());
});

for (const { code } of LANGUAGES.filter((l) => l.code !== "en" && l.code !== "hi")) {
  test(`${code}: same keys and placeholders as English`, async () => {
    const file = new URL(`../../web/js/lang/${code}.js`, import.meta.url);
    assert.ok(existsSync(file), `missing web/js/lang/${code}.js`);
    const { default: strings } = await import(file);
    assert.deepEqual(Object.keys(strings).sort(), Object.keys(english).sort());
    for (const [key, text] of Object.entries(strings)) {
      assert.equal(typeof text, "string", key);
      assert.ok(text.trim(), `${code} ${key} is empty`);
      assert.equal(placeholders(text), placeholders(english[key]), `${code} ${key} placeholders`);
    }
    assert.equal(await loadLanguage(code), code);
    assert.notEqual(t(code, "home.start"), "home.start");
  });
}

test("an unknown language falls back to English", async () => {
  assert.equal(await loadLanguage("xx"), "en");
});
