import fs from 'fs';
import path from 'path';

const dir = './listings';
const files = fs.readdirSync(dir).filter(f => f.endsWith('.json'));
const results = [];

for (const f of files) {
  const d = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf-8'));
  const md = d.markdown || '';
  const meta = d.metadata || {};
  if (md.length < 2000) continue;

  const lines = md.split('\n').map(l => l.trim()).filter(Boolean);

  const h1 = lines.find(l => /^#\s+/.test(l));
  const title = (h1 ? h1.replace(/^#+\s+/, '') : (meta.title || '').replace(/\s*[-–—]\s*Авито.*/, '')).trim();
  if (!title || title.length < 5) continue;

  const url = meta.sourceURL || meta.url || '';
  const priceLine = lines.find(l => /\d[\d\s]*₽/.test(l) && l.length < 60);
  const price = priceLine ? priceLine.replace(/[^\d\s₽отдоговр]/gi, '').trim() : '';

  const sellerRe = /\[([^\]]+)\]\(https:\/\/www\.avito\.ru\/brands\/[a-z0-9]+[^)]*"Нажмите, чтобы перейти в (?:профиль|магазин)"\)/;
  const sM = md.match(sellerRe);
  const seller = sM ? sM[1].replace(/\\/g, '').trim() : 'Частный исполнитель';

  const cityM = url.match(/avito\.ru\/([a-z_-]+)\//);
  const cityRaw = cityM ? cityM[1] : '';
  const cityMap = { moskva: 'Москва', 'sankt-peterburg': 'СПб', ekaterinburg: 'Екатеринбург',
    kazan: 'Казань', novosibirsk: 'Новосибирск', samara: 'Самара', stavropol: 'Ставрополь',
    nalchik: 'Нальчик', groznyy: 'Грозный', tambov: 'Тамбов', arhangelsk: 'Архангельск',
    hasavyurt: 'Хасавюрт', svetlograd: 'Светлоград', morozovsk: 'Морозовск', krymsk: 'Крымск',
    kasli: 'Касли', slavgorod: 'Славгород', kotelnich: 'Котельнич', bogdanovich: 'Богданович',
    serov: 'Серов', m: 'Москва' };
  const city = cityMap[cityRaw] || cityRaw;

  // Extract clean description
  const titleIdx = lines.findIndex(l => l === title);
  const endIdx = lines.findIndex(l => /Похожие объявления|Подписаться на продавца|Спросите у исполнителя|Эковклад/i.test(l));
  const descLines = lines
    .slice(Math.max(0, titleIdx + 2), endIdx > 0 ? endIdx : titleIdx + 70)
    .filter(l => l.length > 25 &&
      !/^\[|^!\[|Написать сообщение|Добавить в избранное|Показать телефон|Все категории|Поиск по|Авито — сайт|Главная|Пользователь$|^от \d+\s*₽$/i.test(l)
    );
  const description = descLines.slice(0, 25).join('\n');

  results.push({ title, price, seller, city, description, url });
}

// Dedup by seller+title[:30]
const seen = new Set();
const deduped = results.filter(r => {
  const key = (r.seller + r.title.toLowerCase().slice(0, 30)).replace(/\s+/g, ' ');
  if (seen.has(key)) return false;
  seen.add(key);
  return true;
});

console.log('Unique listings:', deduped.length);
deduped.slice(0, 20).forEach((r, i) => console.log(`${i + 1}. [${r.city}] ${r.title} | ${r.price} | ${r.seller}`));
fs.writeFileSync('./listings_data.json', JSON.stringify(deduped.slice(0, 20), null, 2), 'utf-8');
