import { chromium } from 'playwright';
import { readFileSync, mkdirSync } from 'fs';
import { fileURLToPath, pathToFileURL } from 'url';
import { dirname, resolve, join } from 'path';

// usage: node render.mjs <listing.json> <outDir>
const [, , jsonPath, outArg] = process.argv;
if (!jsonPath) {
  console.error('usage: node render.mjs <listing.json> <outDir>');
  process.exit(1);
}
const outDir = outArg || './out';
const __dir = dirname(fileURLToPath(import.meta.url));
const templateUrl = pathToFileURL(resolve(__dir, '../assets/template.html')).href;

const listing = readFileSync(resolve(jsonPath), 'utf8');
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 960 }, deviceScaleFactor: 2 });

// inject data BEFORE template scripts run
await page.addInitScript(`window.LISTING = ${listing};`);
await page.goto(templateUrl, { waitUntil: 'networkidle' });

// disable preview scaling so slides render at native 1280x960
await page.evaluate(() => {
  document.body.classList.add('render');
  document.querySelectorAll('.slide').forEach(s => { s.style.transform = 'none'; s.style.marginBottom = '0'; });
});
await page.waitForTimeout(400); // let fonts settle

const slides = await page.$$('.slide');
const results = [];
for (const el of slides) {
  const id = await el.getAttribute('data-id');
  const file = join(outDir, `${id}.png`);
  await el.screenshot({ path: file });
  results.push(file);
}
await browser.close();
console.log('Готово:\n' + results.map(r => '  ' + r).join('\n'));
