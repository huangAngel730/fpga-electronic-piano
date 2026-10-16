const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require('C:/Users/songdongkuan/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
  try {
    const page = await browser.newPage({viewport:{width:1500,height:1100}, deviceScaleFactor:1});
    const errors = [];
    page.on('pageerror', e => errors.push(String(e)));
    await page.goto(pathToFileURL(path.join(__dirname, '138K_Pro_引脚关系与适配核对.html')).href);
    if (await page.locator('.pins tbody tr').count() !== 110) throw new Error('Wrong table size');
    await page.screenshot({path:path.join(__dirname,'report_preview.png')});
    await page.locator('#search').fill('R17');
    const r17 = await page.locator('.pins tbody tr:not([hidden])').allTextContents();
    if (!r17.some(x=>x.includes('J22/5') && x.includes('PMOD0_IO3'))) throw new Error('R17 lookup failed');
    await page.locator('#search').fill('');
    await page.locator('#group').selectOption({label:'音频'});
    const audio = await page.locator('.pins tbody tr:not([hidden])').allTextContents();
    if (audio.length !== 6 || !audio.some(x=>x.includes('H17') && x.includes('高=正常工作'))) throw new Error('Audio filter failed');
    await page.locator('#allpins').scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(__dirname,'audio_table_preview.png')});
    await page.locator('#group').selectOption('');
    await page.locator('#search').fill('冲突');
    if (await page.locator('.pins tbody tr:not([hidden])').count() !== 1) throw new Error('Conflict search failed');
    const overflow = await page.evaluate(()=>document.documentElement.scrollWidth > window.innerWidth);
    if (overflow) throw new Error('Unexpected full-page horizontal overflow');
    if (errors.length) throw new Error(errors.join('\n'));
    const result={headless_render:true,rows:110,search_r17:true,audio_filter:true,conflict_filter:true,page_errors:errors,hardware_opened:false};
    fs.writeFileSync(path.join(__dirname,'ui_validation.json'),JSON.stringify(result,null,2)+'\n');
    console.log(JSON.stringify(result));
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
