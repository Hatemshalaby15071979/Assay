#!/usr/bin/env bash
# Sheet Solution — GUI decision-loop E2E (REAL browser, no audit theater).
#
# Drives the actual GUI in a real browser through the fail-closed loop:
#   run checks -> plan proposals -> deny -> see alternatives -> re-propose
#   -> approve -> apply. Asserts the state transitions are visible in the
#   decision cards and that zero page errors occur. Nothing is applied before
#   an explicit approve + apply by a named human.
#
# Prereqs: node + a system Chrome (default /usr/bin/google-chrome) + network
# for `npm install playwright` (done once into a throwaway dir; repo stays clean).
#
# Run:   bash tests/gui-decisions-test.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PWD_ABS="$(pwd)"

PORT="${PORT:-8601}"
CHROME="${CHROME:-/usr/bin/google-chrome}"

# --- start the GUI (one instance) ---
if [ -x ".venv/bin/python" ]; then PY=".venv/bin/python"; else PY="python3"; fi
$PY gui/main.py --port "$PORT" >/tmp/gui-dec-pt.log 2>&1 &
GUI_PID=$!
cleanup() { kill "$GUI_PID" 2>/dev/null || true; rm -rf "$PWDIR" 2>/dev/null || true; }
trap cleanup EXIT
for _ in $(seq 1 40); do
  curl -s "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1 && break
  sleep 0.3
done

PWDIR="$(mktemp -d)"
cat > "$PWDIR/policy.json" <<'JSON'
{"version":1,"defaults":{"on_unresolved":"propose","confirm_required":true},"checks":[{"id":"CH-002","column":"qa_score","rule":"not_blank","params":{},"severity":"high","on_fail":{"actions":["tag_row","flag_for_human"],"confirm_required":true}}]}
JSON

(
  cd "$PWDIR"
  npm init -y >/dev/null 2>&1
  npm install playwright >/dev/null 2>&1

  cat > "$PWDIR/t.mjs" <<'MJS'
import { chromium } from 'playwright';
import fs from 'fs';
const PORT = process.env.PORT;
const CHROME = process.env.CHROME || '/usr/bin/google-chrome';
const b64 = (p) => fs.readFileSync(p).toString('base64');
const SH = b64(process.env.SHEET), TPL = b64(process.env.TPL), POL = b64(process.env.POLICY);
const browser = await chromium.launch({ executablePath: CHROME, headless: true });
const page = await browser.newPage();
const errs = [];
page.on('pageerror', e => errs.push(String(e)));
await page.goto(`http://127.0.0.1:${PORT}/`);
await page.waitForLoadState('networkidle');

async function drop(id, content, name) {
  await page.evaluate(({ id, content, name }) => {
    const el = document.getElementById(id);
    const bin = atob(content); const u8 = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
    const f = new File([u8], name); const dt = new DataTransfer(); dt.items.add(f);
    el.dispatchEvent(new Event('dragover', { bubbles: true }));
    const ev = new Event('drop', { bubbles: true }); ev.dataTransfer = dt;
    el.dispatchEvent(ev);
  }, { id, content, name });
}

// 1) Run checks through the UI.
await page.click('#tab-checks');
await drop('drop-sheet', SH, 'example-sheet.xlsx');
await drop('drop-template', TPL, 'check-template.example.txt');
await page.waitForFunction(() => !!(state.checks.sheet && state.checks.template));
await page.click('#run-checks');
await page.waitForSelector('#results-checks .card', { timeout: 8000 });
console.log('PASS-1: checks ran, cards =', await page.$$eval('#results-checks .card', e => e.length));

// 2) Plan proposals through the UI.
await page.click('#tab-decide');
await drop('drop-policy', POL, 'policy.json');
await page.waitForFunction(() => !!state.decisions.policy);
await page.waitForFunction(() => !!document.getElementById('dec-out').value.trim());
await page.fill('#dec-actor', 'alice');
await page.click('#plan-decisions');
await page.waitForSelector('#results-decide .card.proposed', { timeout: 8000 });
const fid = await page.$eval('#results-decide .card', n => n.dataset.fid);
console.log('PASS-2: decision proposed', fid);

const card = `#results-decide .card[data-fid="${fid}"]`;

// 3) Deny -> alternatives must still be offered, nothing applied.
await page.click(`${card} button[data-act="decline"]`);
await page.waitForSelector(`${card}.declined`, { timeout: 8000 });
const alts = await page.$$eval(`#alt-${fid} option`, o => o.map(x => x.value));
console.log('PASS-3: declined, alternatives =', alts.join(','));
if (!alts.includes('flag_for_human')) throw new Error('no alternative offered after denial');

// 4) Re-propose the alternative -> still needs approval.
await page.selectOption(`#alt-${fid}`, 'flag_for_human');
await page.click(`${card} button[data-act="re-propose"]`);
await page.waitForFunction((f) => {
  const c = document.querySelector(`#results-decide .card[data-fid="${f}"]`);
  return c && c.classList.contains('proposed') && c.textContent.includes('flag_for_human');
}, fid, { timeout: 8000 });
console.log('PASS-4: alternative re-proposed (still needs approval)');

// 5) Approve -> APPROVED, still not applied.
await page.click(`${card} button[data-act="approve"]`);
await page.waitForSelector(`${card}.approved`, { timeout: 8000 });
console.log('PASS-5: approved');

// 6) Apply -> APPLIED.
await page.click(`${card} button[data-act="apply"]`);
await page.waitForSelector(`${card}.applied`, { timeout: 8000 });
console.log('PASS-6: applied');

console.log('page errors:', errs.length, errs.join('|'));
if (errs.length) process.exit(1);
await browser.close();
console.log('GUI DECISION E2E: PASS');
MJS

  cd "$PWDIR"
  PORT="$PORT" CHROME="$CHROME" \
  SHEET="$PWD_ABS/examples/example-sheet.xlsx" \
  TPL="$PWD_ABS/examples/check-template.example.txt" \
  POLICY="$PWDIR/policy.json" node t.mjs
)
