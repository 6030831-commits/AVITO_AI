import fs from 'fs';
import path from 'path';

const dir = './listings';
const files = fs.readdirSync(dir).filter(f => f.endsWith('.json'));

const sellers = new Map(); // brandUrl -> {name, listings: [{title, url}]}

for (const f of files) {
  let d;
  try {
    d = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf-8'));
  } catch (e) { continue; }
  const md = d.markdown || '';
  const url = d.metadata?.sourceURL || d.metadata?.url || '';

  // title: prefer the page's H1 heading (more reliable than og:title, which can be generic)
  const h1 = md.match(/^#\s+(.+)$/m);
  const title = (h1 ? h1[1] : d.metadata?.title?.replace(/\s*-\s*Авито.*$/, ''))?.trim() || '';

  // brand link pattern: [NAME](https://www.avito.ru/brands/<hash>...) "Нажмите, чтобы перейти в профиль/магазин"
  const m = md.match(/\[([^\]]+)\]\((https:\/\/www\.avito\.ru\/brands\/[a-z0-9]+)[^)]*"Нажмите, чтобы перейти в (?:профиль|магазин)"\)/);
  if (!m) {
    console.log('NO BRAND FOUND:', f, url);
    continue;
  }
  const name = m[1].trim();
  const brandUrl = m[2].split('?')[0];

  if (!sellers.has(brandUrl)) sellers.set(brandUrl, { name, listings: [] });
  sellers.get(brandUrl).listings.push({ title, url });
}

console.log('Unique sellers found:', sellers.size);
for (const [brandUrl, info] of sellers) {
  console.log(`- ${info.name} | ${brandUrl}`);
  info.listings.forEach(l => console.log(`    · ${l.title}`));
}

fs.writeFileSync('./sellers_from_listings.json', JSON.stringify([...sellers.entries()].map(([url, info]) => ({ brandUrl: url, ...info })), null, 2), 'utf-8');
