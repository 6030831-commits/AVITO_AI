import fs from 'fs';
import path from 'path';
import crypto from 'crypto';

const sellers = JSON.parse(fs.readFileSync('./sellers_from_listings.json', 'utf-8'));

// AI-related keywords to filter by
const aiKeywords = /ии|ai|нейро|бот|автоматиз|n8n|chatgpt|gpt|llm|искусственн|ассистент|автовор|make\.com|zapier/i;

const results = [];

for (const seller of sellers) {
  const h = crypto.createHash('md5').update(seller.brandUrl + '\n').digest('hex').slice(0, 10);
  const file = `./brands/${h}.json`;
  if (!fs.existsSync(file)) {
    console.log('MISSING brand file:', seller.name, h);
    results.push({ name: seller.name, brandUrl: seller.brandUrl, aiCount: '?', titles: [] });
    continue;
  }

  const d = JSON.parse(fs.readFileSync(file, 'utf-8'));
  const md = d.markdown || '';

  // Extract listing titles: look for markdown links to /predlozheniya_uslug/..._\d+ pattern
  const linkRe = /\[([^\]]+)\]\(https:\/\/www\.avito\.ru\/[^)]+\/predlozheniya_uslug\/[^)]+_\d+[^)]*\)/g;
  const found = new Map();
  let m;
  while ((m = linkRe.exec(md)) !== null) {
    const title = m[1].trim();
    if (title.length > 3 && !title.startsWith('http') && !/^[\d\s₽]+$/.test(title)) {
      found.set(title, true);
    }
  }

  // Also grab plain H3/H2 headings that might be listing titles on brand pages
  const headingRe = /^#{2,3}\s+(.+)$/gm;
  while ((m = headingRe.exec(md)) !== null) {
    const t = m[1].trim();
    if (t.length > 10 && aiKeywords.test(t)) found.set(t, true);
  }

  const allTitles = [...found.keys()];
  const aiTitles = allTitles.filter(t => aiKeywords.test(t));

  // If no AI titles found from brand page, fall back to what we know from listings scrape
  const knownTitles = seller.listings.map(l => l.title).filter(t => t && t.length > 3);

  const finalTitles = aiTitles.length > 0 ? aiTitles : knownTitles;

  results.push({
    name: seller.name,
    brandUrl: seller.brandUrl,
    totalOnPage: allTitles.length,
    aiCount: finalTitles.length,
    titles: finalTitles,
    allTitles: allTitles.slice(0, 40),
  });
}

fs.writeFileSync('./brand_analysis.json', JSON.stringify(results, null, 2), 'utf-8');

// Print summary
results.sort((a, b) => (b.aiCount === '?' ? -1 : b.aiCount) - (a.aiCount === '?' ? -1 : a.aiCount));
console.log('\n=== ИТОГО: ' + results.length + ' аккаунтов ===\n');
results.forEach((r, i) => {
  console.log(`${i + 1}. ${r.name}`);
  console.log(`   Объявлений по теме ИИ: ${r.aiCount} | Всего на странице: ${r.totalOnPage || '?'}`);
  r.titles.forEach(t => console.log(`   – ${t}`));
  console.log();
});
