// Exports each delivered archify HTML through its own viewer "Download SVG" path
// (dual-theme canonical SVG) using archify's headless Chrome launcher.
// Usage: node export-svg.mjs <archify-dir> <html-dir> <svg-dir>
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const [archifyDir, htmlDir, svgDir] = process.argv.slice(2);
const { findChrome, ChromeVisualBrowser } = await import(pathToFileURL(path.join(archifyDir, 'bin/visual-check.mjs')).href);

const chrome = findChrome();
const browser = new ChromeVisualBrowser(chrome.path || chrome);
const sessionId = await browser.sessionPromise;
const send = (method, params = {}) => browser.cdp.send(method, params, sessionId);
async function evaluate(expression) {
  const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
  if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails).slice(0, 500));
  return r.result.value;
}

fs.mkdirSync(svgDir, { recursive: true });
await send('Emulation.setDeviceMetricsOverride', { width: 1600, height: 1000, deviceScaleFactor: 1, mobile: false });
for (const file of fs.readdirSync(htmlDir).filter((f) => f.endsWith('.html')).sort()) {
  const loaded = browser.cdp.waitFor('Page.loadEventFired', sessionId);
  await send('Page.navigate', { url: pathToFileURL(path.join(htmlDir, file)).href });
  await loaded;
  const result = await evaluate(`(async function () {
    if (document.fonts && document.fonts.ready) await document.fonts.ready;
    await new Promise(function (r) { requestAnimationFrame(function () { requestAnimationFrame(r); }); });
    var captured = null;
    var original = URL.createObjectURL;
    URL.createObjectURL = function (blob) { captured = blob; return original.call(URL, blob); };
    HTMLAnchorElement.prototype.click = function () {};
    var button = document.querySelector('.export-menu button[data-format="svg"]');
    if (!button) return { error: 'no svg export button' };
    button.click();
    for (var i = 0; i < 100 && !captured; i++) await new Promise(function (r) { setTimeout(r, 50); });
    if (!captured) return { error: 'no blob captured', exportError: document.documentElement.getAttribute('data-last-export-error') };
    return { svg: await captured.text(), type: captured.type };
  })()`);
  if (result.error) throw new Error(`${file}: ${JSON.stringify(result)}`);
  const out = path.join(svgDir, file.replace(/\.html$/, '.svg'));
  fs.writeFileSync(out, result.svg);
  console.log(`${file} -> ${path.basename(out)} ${result.svg.length} bytes`);
}
await browser.close?.();
process.exit(0);
