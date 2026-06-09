import fs from 'fs';
import path from 'path';

const dir = './listings';
const files = fs.readdirSync(dir).filter(f => f.endsWith('.json'));

const results = [];

for (const f of files) {
  let d;
  try { d = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf-8')); }
  catch { continue; }

  const md = d.markdown || '';
  const meta = d.metadata || {};
  const url = meta.sourceURL || meta.url || '';

  // Skip if page too short (blocked/error)
  if (md.length < 2000) continue;

  const lines = md.split('\n').map(l => l.trim()).filter(Boolean);

  // --- Title ---
  const h1 = lines.find(l => /^#\s+/.test(l));
  const title = (h1 ? h1.replace(/^#+\s+/, '') : meta.title?.replace(/\s*[-–—]\s*Авито.*$/, '')).trim() || '';

  // --- Price ---
  const priceLine = lines.find(l => /\d[\d\s]*[₽р]/.test(l) && l.length < 60);
  const price = priceLine ? priceLine.replace(/[^\d\s₽отдоговр]/gi, '').trim() : '';

  // --- Seller ---
  const sellerM = md.match(/\[([^\]]+)\]\(https:\/\/www\.avito\.ru\/brands\/[a-z0-9]+[^)]*"Нажмите, чтобы перейти в (?:профиль|магазин)"\)/);
  const seller = sellerM ? sellerM[1].trim() : 'Частный исполнитель';
  const brandM = md.match(/https:\/\/www\.avito\.ru\/brands\/([a-z0-9]+)/);
  const brandUrl = brandM ? `https://www.avito.ru/brands/${brandM[1]}` : '';

  // --- Description body ---
  // Find lines after title up until "Похожие объявления" / seller block / "Отзывы"
  const titleIdx = lines.findIndex(l => h1 && l === h1.replace(/^#+\s+/, ''));
  const endIdx = lines.findIndex(l => /Похожие объявления|Подписаться на продавца|Спросите у исполнителя|Эковклад/i.test(l));
  const descLines = lines.slice(Math.max(0, titleIdx + 2), endIdx > 0 ? endIdx : titleIdx + 60);

  // Filter out noise lines (nav, breadcrumbs, button text, short fragments)
  const descClean = descLines.filter(l =>
    l.length > 20 &&
    !/^\[|^!\[|Написать сообщение|Добавить в избранное|Показать телефон|Все категории|Поиск по объявлениям|Авито — сайт|Главная|от \d+\s*₽$|Пользователь$/i.test(l)
  );

  const description = descClean.slice(0, 30).join('\n');

  // --- City ---
  const cityM = url.match(/avito\.ru\/([a-z_-]+)\//);
  const cityRaw = cityM ? cityM[1] : '';
  const cityMap = { moskva:'Москва', 'sankt-peterburg':'СПб', ekaterinburg:'Екатеринбург',
    kazan:'Казань', novosibirsk:'Новосибирск', samara:'Самара', stavropol:'Ставрополь',
    nalchik:'Нальчик', groznyy:'Грозный', tambov:'Тамбов', arhangelsk:'Архангельск',
    hasavyurt:'Хасавюрт', svetlograd:'Светлоград', morozovsk:'Морозовск', krymsk:'Крымск',
    kasli:'Касли', slavgorod:'Славгород', kotelnich:'Котельнич', bogdanovich:'Богданович',
    serov:'Серов', m:'Москва (моб.)' };
  const city = cityMap[cityRaw] || cityRaw;

  if (title) results.push({ title, price, seller, brandUrl, city, description, url });
}

// Deduplicate by title similarity — keep first occurrence
const seen = new Set();
const deduped = results.filter(r => {
  const key = r.title.toLowerCase().replace(/\s+/g, ' ').slice(0, 40);
  if (seen.has(key)) return false;
  seen.add(key);
  return true;
}).slice(0, 20);

fs.writeFileSync('./listings_data.json', JSON.stringify(deduped, null, 2), 'utf-8');
console.log('Extracted:', deduped.length, 'unique listings');
deduped.forEach((r, i) => console.log(`${i+1}. [${r.city}] ${r.title} | ${r.price} | ${r.seller}`));
