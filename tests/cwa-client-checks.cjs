const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const test = require('node:test');
const path = require('node:path');
const clientPath = process.env.CWA_CLIENT_PATH || path.join(__dirname, '../site/audience.js');
const source = fs.readFileSync(clientPath, 'utf8');
const config = JSON.parse(source.match(/const config = \/\* CWA_CONFIG \*\/ (\{[^\n]+\});/)[1]);
const host = config.hosts[0];

function harness({ browser={}, stored={}, pathname='/', search='', referrer='', cookie='auth_session=keep; _ga=old; minilytics_vid=old' }={}) {
  const storage = new Map(Object.entries(stored));
  const scripts=[], writes=[], elements=[], events={}, docEvents={};
  let reloads=0;
  const location={hostname:host,origin:`https://${host}`,href:`https://${host}${pathname}${search}`,reload(){reloads++;}};
  const element = tag => ({tag,dataset:{},children:[],listeners:{},appendChild(el){this.children.push(el);elements.push(el);},setAttribute(){},addEventListener(name,fn){this.listeners[name]=fn;},showModal(){this.open=true;},close(){this.open=false;},remove(){this.removed=true;}});
  const document={referrer,head:{appendChild(el){if(el.tag==='script')scripts.push(el);}},body:element('body'),getElementById(id){return elements.find(el=>el.id===id&&!el.removed)||null;},createElement:element,addEventListener(name,fn){docEvents[name]=fn;}};
  Object.defineProperty(document,'cookie',{get:()=>cookie,set:value=>writes.push(value)});
  const context={location,document,navigator:browser,URL,localStorage:{getItem:key=>storage.get(key)||null,setItem:(key,value)=>storage.set(key,value)},addEventListener:(name,fn)=>events[name]=fn};context.window=context;
  const tokenSource=source.replace(/"token":"[^"]*"/,`"token":"${'a'.repeat(32)}"`);
  vm.runInNewContext(tokenSource,context);
  return {context,storage,scripts,writes,elements,events,rerun(){vm.runInNewContext(tokenSource,context);},get reloads(){return reloads;}};
}

test('Cloudflare starts by default without a banner, visitor cookies or stored identifiers',()=>{
  const h=harness();assert.equal(h.scripts.length,1);assert.equal(h.scripts[0].src,'https://static.cloudflareinsights.com/beacon.min.js');
  assert.equal(h.storage.size,0);assert.ok(h.elements.every(el=>el.tag==='button'),'No initial banner or dialog');
  assert.ok(h.writes.length>0);assert.ok(h.writes.every(value=>value.includes('Max-Age=0')));assert.ok(h.writes.every(value=>!value.startsWith('auth_session=')));
  h.rerun();assert.equal(h.scripts.length,1,'Repeated mounting must not double count');
});
test('prior refusals, owner exclusions, privacy signals and automation remain excluded',()=>{
  for(const key of config.legacyChoices||[])for(const value of ['declined',JSON.stringify({choice:'reject'}),JSON.stringify({choice:'deny'})])assert.equal(harness({stored:{[key]:value}}).scripts.length,0);
  for(const key of config.legacyChoices||[])assert.equal(harness({cookie:key+'='+encodeURIComponent(JSON.stringify({choice:'reject'}))}).scripts.length,0);
  for(const key of config.exclusions||[])assert.equal(harness({stored:{[key]:'true'}}).scripts.length,0);
  for(const key of config.exclusions||[])assert.equal(harness({cookie:key+'=true'}).scripts.length,0);
  for(const browser of [{doNotTrack:'1'},{doNotTrack:'yes'},{globalPrivacyControl:true},{webdriver:true}])assert.equal(harness({browser}).scripts.length,0);
  assert.equal(harness({stored:{'cloudflare-analytics-choice-v1':'off'}}).scripts.length,0);
});
test('sensitive URLs and authentication pages do not start analytics',()=>{
  for(const pathname of ['/api/private','/auth/callback','/account','/checkout','/login','/reset-password'])assert.equal(harness({pathname}).scripts.length,0);
  assert.equal(harness({search:'?token=private'}).scripts.length,0);
  assert.equal(harness({referrer:`https://${host}/auth/callback?code=private`}).scripts.length,0);
});
test('the privacy panel is user-invoked and changing the preference unloads measurement',()=>{
  const h=harness();h.context.cloudflareAnalytics.openPreferences();
  const dialog=h.elements.find(el=>el.tag==='dialog');assert.ok(dialog.open);
  const off=h.elements.find(el=>el.textContent==='Turn analytics off');off.listeners.click();
  assert.equal(h.storage.get('cloudflare-analytics-choice-v1'),'off');assert.equal(h.reloads,1);
  const after=harness({stored:Object.fromEntries(h.storage)});assert.equal(after.scripts.length,0);
  assert.equal(after.context.cloudflareAnalytics.setEnabled(true),true);
  assert.equal(harness({stored:Object.fromEntries(after.storage)}).scripts.length,1);
});
test('privacy preferences propagate to other open tabs',()=>{
  const h=harness();h.events.storage({key:'cloudflare-analytics-choice-v1'});assert.equal(h.reloads,1);
});
