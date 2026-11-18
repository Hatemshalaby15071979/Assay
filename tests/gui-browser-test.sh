# Sheet Solution — GUI regression test (REAL browser DOM drag-and-drop).
#
# Guards the bug where the Compare button stayed disabled after dropping two
# sheets. Drives the real GUI in a real browser: switches to the Compare tab,
# dispatches actual DOM 'drop' events (with a real DataTransfer + File) on the
# two drop zones, fills key/fields, asserts the Compare button ENABLES, clicks
# it, and asserts diff cards render with zero page errors.
#
# Prereqs: node + a system Chrome (default /usr/bin/google-chrome) + network
# for `npm install playwright` (done once into a throwaway dir; repo stays clean).
#
# Run:   bash tests/gui-browser-test.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PWD_ABS="$(pwd)"

PORT="${PORT:-8600}"
CHROME="${CHROME:-/usr/bin/google-chrome}"

# --- start the GUI (one instance) ---
if [ -x ".venv/bin/python" ]; then PY=".venv/bin/python"; else PY="python3"; fi
$PY gui/main.py --port "$PORT" >/tmp/gui-pt.log 2>&1 &
GUI_PID=$!
cleanup() { kill "$GUI_PID" 2>/dev/null || true; rm -rf "$PWDIR" 2>/dev/null || true; }
trap cleanup EXIT
for _ in $(seq 1 40); do
  curl -s "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1 && break
  sleep 0.3
done

# --- playwright (node) in a throwaway dir ---
PWDIR="$(mktemp -d)"
(
  cd "$PWDIR"
  npm init -y >/dev/null 2>&1
  npm install playwright >/dev/null 2>&1

  cat > "$PWDIR/t.mjs" <<'MJS'
import { chromium } from 'playwright';
import fs from 'fs';
const PORT = process.env.PORT, A = process.env.SHEET_A, B = process.env.SHEET_B;
const CHROME = process.env.CHROME || '/usr/bin/google-chrome';
const aB64 = fs.readFileSync(A).toString('base64');
const bB64 = fs.readFileSync(B).toString('base64');
const browser = await chromium.launch({ executablePath: CHROME, headless: true });
const page = await browser.newPage();
const errs = [];
page.on('pageerror', e => errs.push(String(e)));
await page.goto(`http://127.0.0.1:${PORT}/`);
await page.waitForLoadState('networkidle');
await page.click('#tab-compare');
await page.waitForTimeout(150);

// Dispatch a real DOM 'drop' (DataTransfer + File) on a drop zone, then wait
// until the async /api/upload finished and set the state flag.
// NOTE: drop-zone element ids are 'drop-A' / 'drop-B' (NO leading '#').
async function drop(id, b64, name) {
  for (let i = 0; i < 10; i++) {
    if (await page.evaluate((s) => !!document.getElementById(s), id)) break;
    await page.waitForTimeout(100);
  }
  await page.evaluate(({ id, b64, name }) => {
    const el = document.getElementById(id);
    const bin = atob(b64); const u8 = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
    const f = new File([u8], name); const dt = new DataTransfer(); dt.items.add(f);
    el.dispatchEvent(new Event('dragover', { bubbles: true }));
    const ev = new Event('drop', { bubbles: true }); ev.dataTransfer = dt;
    el.dispatchEvent(ev);
  }, { id, b64, name });
  await page.waitForFunction(
    (id) => (id === 'drop-A' ? !!state.compare.A : !!state.compare.B),
    id, { timeout: 10000 });
}

await drop('drop-A', aB64, 'baseline.xlsx');
await drop('drop-B', bB64, 'new.xlsx');
await page.fill('#cmp-key', 'item_id');
await page.fill('#cmp-fields', 'amount,status');
await page.waitForTimeout(100);

if (await page.$eval('#run-compare', n => n.disabled)) {
  console.error('FAIL: Compare button still disabled after dropping both sheets');
  process.exit(1);
}
console.log('PASS-1: Compare button ENABLED after dropping Sheet A + Sheet B');

await page.click('#run-compare');
await page.waitForSelector('#results-compare .card', { timeout: 5000 });
const cards = await page.$$eval('#results-compare .card', e => e.length);
const sum = await page.$eval('#results-compare .summary', n => n.textContent.replace(/\s+/g, ' ').trim());
console.log('PASS-2: diff cards =', cards, '|', sum);
console.log('page errors:', errs.length, errs.join('|'));
if (cards === 0 || errs.length) process.exit(1);
await browser.close();
console.log('GUI DOM-DROP COMPARE: PASS');
MJS

  cd "$PWDIR"
  PORT="$PORT" CHROME="$CHROME" \
  SHEET_A="$PWD_ABS/examples/compare-baseline.xlsx" \
  SHEET_B="$PWD_ABS/examples/compare-new.xlsx" node t.mjs
)
