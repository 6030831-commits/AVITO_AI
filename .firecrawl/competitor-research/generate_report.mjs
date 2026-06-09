import fs from 'fs';

const raw = JSON.parse(fs.readFileSync('./brand_analysis.json', 'utf-8'));

const aiKw = /\bии\b|ии-|ai[\s\-\/]|нейро|чат.?бот|автоматиз|n8n|chatgpt|gpt|llm|искусственн|ассистент|автовор|ии-агент|ИИ/i;
const junkRe = /^Отзывы о|^Свежие объявления|^Написать|^Все объявления|^Подписаться|^от \d/i;

function cleanTitles(titles) {
  return [...new Set(
    titles
      .map(t => t.replace(/\[([^\]]+)\]\(.*\)/, '$1').trim())
      .filter(t => t.length > 5 && !junkRe.test(t) && !/^https/.test(t) && aiKw.test(t))
  )];
}

const sellers = raw.map(r => {
  const allTitles = (r.allTitles || []).concat(r.titles || []);
  const cleaned = cleanTitles(allTitles);
  return { name: r.name.replace(/\\/g, ''), brandUrl: r.brandUrl, count: cleaned.length, titles: cleaned };
}).filter(s => s.count > 0).sort((a, b) => b.count - a.count);

// RTF helpers
function esc(s) {
  let o = '';
  for (const ch of s) {
    const c = ch.codePointAt(0);
    if (ch === '\\' || ch === '{' || ch === '}') { o += '\\' + ch; }
    else if (c < 128) { o += ch; }
    else { o += `\\u${c > 32767 ? c - 65536 : c}?`; }
  }
  return o;
}

let body = `{\\pard\\qc\\b\\fs36 ${esc('Анализ конкурентов: Авито — ИИ, боты, автоматизация')}\\par}\n\\par\n`;
body += `{\\pard\\fs20\\i ${esc('Дата: 08.06.2026 · Проанализировано аккаунтов: ' + sellers.length + ' · Запросы: «интеграция ии», «создание ботов», «настройка n8n» и похожие')}\\par}\n\\par\\par\n`;

sellers.forEach((s, i) => {
  body += `{\\pard\\b\\fs28 ${esc(`${i + 1}. ${s.name}`)}\\par}\n`;
  body += `{\\pard\\fs22 ${esc(`Объявлений по теме ИИ/автоматизации: ${s.count} · ${s.brandUrl}`)}\\par}\n\\par\n`;
  s.titles.forEach(t => {
    body += `{\\pard\\fi-360\\li360\\fs24 \\bullet\\tab ${esc(t)}\\par}\n`;
  });
  body += `\\par\n`;
});

const rtf = `{\\rtf1\\ansi\\ansicpg1251\\deff0\\deflang1049\n{\\fonttbl{\\f0\\fswiss\\fcharset204 Calibri;}}\n\\viewkind4\\uc1\n${body}}`;
fs.writeFileSync('../../Конкуренты_ИИ_Авито.rtf', rtf, 'latin1');
console.log('Done!', sellers.length, 'sellers');
sellers.forEach(s => console.log(`  ${s.count} — ${s.name}`));
