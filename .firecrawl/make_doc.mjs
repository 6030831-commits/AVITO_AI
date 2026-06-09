import fs from 'fs';

const data = JSON.parse(fs.readFileSync(new URL('./theses_data.json', import.meta.url), 'utf-8'));

// Escape text for RTF: backslash, braces, and non-ASCII -> \uNNNN?
function rtfEscape(str) {
  let out = '';
  for (const ch of str) {
    const code = ch.codePointAt(0);
    if (ch === '\\' || ch === '{' || ch === '}') {
      out += '\\' + ch;
    } else if (code < 128) {
      out += ch;
    } else {
      // RTF \u takes signed 16-bit integer
      const signed = code > 32767 ? code - 65536 : code;
      out += `\\u${signed}?`;
    }
  }
  return out;
}

let body = '';

// Title
body += `{\\pard\\qc\\b\\fs36 ${rtfEscape(data.title)}\\par}\n`;
body += `\\par\n`;

// Intro
body += `{\\pard\\fs22\\i ${rtfEscape(data.intro)}\\par}\n`;
body += `\\par\\par\n`;

for (const section of data.sections) {
  body += `{\\pard\\b\\fs28 ${rtfEscape(section.heading)}\\par}\n`;
  body += `\\par\n`;
  for (const item of section.items) {
    body += `{\\pard\\fi-360\\li360\\fs24 \\bullet\\tab ${rtfEscape(item)}\\par}\n`;
  }
  body += `\\par\n`;
}

const rtf = `{\\rtf1\\ansi\\ansicpg1251\\deff0\\deflang1049
{\\fonttbl{\\f0\\fswiss\\fcharset204 Calibri;}}
\\viewkind4\\uc1
${body}
}`;

const outPath = process.argv[2];
fs.writeFileSync(outPath, rtf, 'latin1');
console.log('Written to', outPath);
