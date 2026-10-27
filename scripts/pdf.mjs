// Typeset an HTML print edition to PDF with the preinstalled Chromium.
// Usage: node scripts/pdf.mjs <input.html> <output.pdf> [probe.json]
// Writes a layout probe (overflowing / clipped elements) for the print QA step.
import { createRequire } from 'node:module';
import { writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import path from 'node:path';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const [, , input, output, probePath] = process.argv;
if (!input || !output) {
  console.error('usage: node scripts/pdf.mjs <input.html> <output.pdf> [probe.json]');
  process.exit(2);
}

const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  await page.emulateMedia({ media: 'print' });
  await page.goto(pathToFileURL(path.resolve(input)).href, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);

  const probe = await page.evaluate(() => {
    const issues = [];
    const bodyRight = document.body.getBoundingClientRect().right + 1;
    for (const el of document.querySelectorAll('table, pre, .box, .st, .idea, svg, img, .board, h1, h2, h3')) {
      const r = el.getBoundingClientRect();
      const label = (el.dataset.headline || el.textContent || el.tagName).trim().slice(0, 70);
      if (el.scrollWidth > el.clientWidth + 1 && getComputedStyle(el).overflowX !== 'visible') {
        issues.push({ kind: 'clipped', tag: el.tagName, label });
      }
      if (r.right > bodyRight) issues.push({ kind: 'overflow-right', tag: el.tagName, label, by: Math.round(r.right - bodyRight) });
    }
    const fonts = [...document.fonts].filter(f => f.status === 'loaded').map(f => `${f.family} ${f.weight} ${f.style}`);
    const headlines = [...document.querySelectorAll('[data-headline]')].map(e => e.dataset.headline);
    return { issues, fonts: [...new Set(fonts)], headlines };
  });

  await page.pdf({ path: output, preferCSSPageSize: true, printBackground: true, tagged: true, outline: true });
  if (probePath) writeFileSync(probePath, JSON.stringify(probe, null, 2));
  console.log(JSON.stringify({ output, issues: probe.issues.length, fonts: probe.fonts.length }));
} finally {
  await browser.close();
}
