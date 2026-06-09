import fs from 'fs';

const listings = JSON.parse(fs.readFileSync('./listings_data.json', 'utf-8'));

function esc(s) {
  if (!s) return '';
  let o = '';
  for (const ch of String(s)) {
    const c = ch.codePointAt(0);
    if (ch === '\\' || ch === '{' || ch === '}') { o += '\\' + ch; }
    else if (c < 128) { o += ch; }
    else { o += `\\u${c > 32767 ? c - 65536 : c}?`; }
  }
  return o;
}

function row(label, value) {
  if (!value || value.trim() === '') return '';
  return `{\\pard\\fi-2880\\li2880\\fs22 {\\b ${esc(label + ':')}\\tab} ${esc(value)}\\par}\n`;
}

let body = `{\\pard\\qc\\b\\fs36 ${esc('Анализ объявлений Авито: контент-заводы и ИИ-видео')}\\par}\n\\par\n`;
body += `{\\pard\\qc\\fs20\\i ${esc('Дата: 09.06.2026 · Запросы: «контент завод», «производство ai контента», «создание ии видео» · Всего объявлений: 20')}\\par}\n\\par\\par\n`;

listings.forEach((r, i) => {
  // Section header
  body += `{\\pard\\b\\fs30 ${esc(`${i + 1}. ${r.title}`)}\\par}\n`;
  body += `{\\pard\\fs20\\i ${esc(r.url)}\\par}\n\\par\n`;

  body += row('Продавец', r.seller);
  body += row('Город', r.city);
  body += row('Цена', r.price || 'не указана');

  // Description — split into lines and output as separate paragraphs
  if (r.description) {
    body += `{\\pard\\b\\fs22 ${esc('Описание:')}\\par}\n`;
    const descLines = r.description.split('\n').filter(l => l.trim().length > 0);
    descLines.forEach(l => {
      body += `{\\pard\\fs22\\li360 ${esc(l.trim())}\\par}\n`;
    });
  }

  body += `\\par\n{\\pard\\brdrb\\brdrs\\brdrw10\\brsp20 \\par}\\par\n`;
});

const rtf = `{\\rtf1\\ansi\\ansicpg1251\\deff0\\deflang1049
{\\fonttbl{\\f0\\fswiss\\fcharset204 Calibri;}}
{\\colortbl;\\red0\\green0\\blue0;}
\\viewkind4\\uc1
${body}}`;

fs.writeFileSync('../../Контент_Завод_Авито_20.rtf', rtf, 'latin1');
console.log('Written: Контент_Завод_Авито_20.rtf');
listings.forEach((r, i) => console.log(`${i + 1}. [${r.city}] ${r.title} — ${r.price || 'нет цены'}`));
