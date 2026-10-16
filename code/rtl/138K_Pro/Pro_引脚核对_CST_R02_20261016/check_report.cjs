const fs=require('node:fs'),path=require('node:path'),{pathToFileURL}=require('node:url');
const {chromium}=require('C:/Users/songdongkuan/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1100},deviceScaleFactor:1});
  const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(pathToFileURL(path.join(__dirname,'138K_Pro_引脚关系与适配核对_CST_R02.html')).href);
  const records=await page.locator('.pins tbody tr').evaluateAll(rs=>rs.map(r=>[...r.cells].map(c=>c.textContent)));
  if(records.length!==110||records.some(r=>r.length!==12))throw Error('Rows/columns mismatch');
  const net=n=>records.find(r=>r[1]===n);
  if(!net('PMOD0_IO1')[2].startsWith('N26')||!net('PMOD0_IO1')[10].includes('pmod_0[5]'))throw Error('N26 resolution missing');
  if(!net('PMOD0_IO3')[10].includes('pmod_0[1]')||!net('PMOD0_IO3')[5].includes('J22/5'))throw Error('R17 alias mismatch');
  if(!net('USR_KEY.1')[10].includes('key[2]')||!net('USR_KEY.2')[10].includes('key[1]'))throw Error('Key naming mismatch');
  if(!net('USR_LED.0')[10].includes('led[1]')||!net('USR_LED.1')[10].includes('led[0]'))throw Error('LED naming mismatch');
  if(!net('CPU_RST / U4_USR_KEY')[11].includes('IO_TYPE=LVCMOS15'))throw Error('Reset voltage missing');
  for(const n of ['PA_EN','DBG_UART.TX / FPGA_TXD','DBG_UART.RX / FPGA_RXD'])if(!net(n)[10].startsWith('未列'))throw Error('CST missing coverage hidden');
  await page.screenshot({path:path.join(__dirname,'cst_summary_preview.png')});
  await page.locator('#group').selectOption({label:'PMOD0'});
  if(await page.locator('.pins tbody tr:not([hidden])').count()!==8)throw Error('PMOD filter failed');
  await page.locator('#allpins').scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(__dirname,'pmod_table_preview.png')});
  await page.locator('#search').fill('N26');
  if(await page.locator('.pins tbody tr:not([hidden])').count()!==1)throw Error('N26 search failed');
  await page.locator('#search').fill('');await page.locator('#group').selectOption({label:'音频'});
  if(await page.locator('.pins tbody tr:not([hidden])').count()!==6)throw Error('Audio filter failed');
  if(errors.length)throw Error(errors.join('\n'));
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Outer horizontal overflow');
  const result={render:true,rows:110,columns:12,n26_cst_and_btb:true,r17_alias:true,key_indices:true,led_indices:true,reset_lv_cmos15:true,missing_uart_and_pa_en_visible:true,search_and_filters:true,page_errors:errors,hardware_opened:false};
  fs.writeFileSync(path.join(__dirname,'ui_validation.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
