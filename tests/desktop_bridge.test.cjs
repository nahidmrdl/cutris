const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(process.env.CUTRIS_BRIDGE_SOURCE || path.join(__dirname, '../web/desktop.js'), 'utf8');

function editor(pywebview) {
  const elements = new Map(), listeners = new Map(), timers = [], notices = [], calls = [];
  const element = id => {
    if (!elements.has(id)) elements.set(id, {hidden:true, disabled:false, textContent:'', addEventListener(){}});
    return elements.get(id);
  };
  const state = {dirty:false, busy:false, job:null};
  const window = {pywebview, addEventListener:(name, callback)=>listeners.set(name, callback), location:{assign:url=>calls.push(['navigate',url])}};
  const context = vm.createContext({window, state, $:element, document:{body:{classList:{contains:()=>false,add(){}}},querySelector:()=>({})},
    setInterval:callback=>timers.push(callback), renderQueue(){}, notice:text=>notices.push(text),
    safely:fn=>async(...args)=>{try{await fn(...args);}catch(error){notices.push(error.message);}}, api:async()=>({})});
  vm.runInContext(source, context);
  return {context,window,state,element,timers,notices,calls,ready:()=>listeners.get('pywebviewready')()};
}

test('an empty bridge during startup cannot interrupt editor state updates',()=>{
  const ui = editor({api:{}});
  ui.state.dirty = true;
  assert.doesNotThrow(()=>vm.runInContext('syncDesktopState()',ui.context));
  assert.doesNotThrow(()=>ui.timers.forEach(callback=>callback()));
  assert.equal(ui.element('modelsButton').hidden,true);
  assert.deepEqual(ui.notices,[]);
});

test('native ready reports the latest unsaved state and enables available actions',async()=>{
  const ui = editor({api:{}}), reports = [];
  ui.state.dirty = true; ui.state.job = {status:'running'};
  ui.window.pywebview.api = {document_state:async(...args)=>reports.push(args),setup_models:async()=>({}),open_saved_work:async()=>true,integration_context:async()=>({workspace:null})};
  ui.ready();
  assert.deepEqual(reports,[[true,true]]);
  assert.equal(ui.element('modelsButton').hidden,false);
  assert.equal(ui.element('savedWorkButton').hidden,false);
  ui.state.dirty = false; ui.state.job.status = 'complete';
  ui.timers[0]();
  assert.deepEqual(reports[1],[false,false]);
});

test('browser mode and missing optional native methods leave editing usable',()=>{
  const browser = editor(undefined);
  assert.doesNotThrow(()=>browser.timers[0]());
  const desktop = editor({api:{document_state:()=>{}}});
  assert.doesNotThrow(()=>desktop.ready());
  assert.equal(desktop.element('modelsButton').hidden,true);
});

test('bridge shutdown cannot throw into save or tool updates',async()=>{
  const ui = editor({api:{document_state:()=>{throw new Error('closing');}}});
  assert.doesNotThrow(()=>ui.timers[0]());
  ui.window.pywebview.api.document_state = ()=>Promise.reject(new Error('closed'));
  ui.timers[0]();
  await new Promise(resolve=>setImmediate(resolve));
  assert.deepEqual(ui.notices,[]);
});

test('save and return saves edits, clears native dirty state, then navigates',async()=>{
  const ui = editor({api:{document_state:async(...args)=>ui.calls.push(['state',...args]),return_to_workspace:async id=>{ui.calls.push(['return',id]);return {ok:true,url:'http://127.0.0.1/queue'};}}});
  ui.calls.length = 0;
  ui.state.dirty = true; ui.state.job = {id:'project'};
  ui.element('save').onclick = async()=>{ui.calls.push(['save']);ui.state.dirty=false;};
  await ui.element('returnToWorkspace').onclick();
  assert.deepEqual(ui.calls,[['save'],['state',false,false],['return','project'],['navigate','http://127.0.0.1/queue']]);
  assert.equal(ui.window.leavingWorkspace,true);
});

test('a failed save or incomplete bridge cannot leave the editor',async()=>{
  const ui = editor({api:{}});
  await ui.element('returnToWorkspace').onclick();
  assert.match(ui.notices[0],/connection is still starting/);
  assert.deepEqual(ui.calls,[]);
  ui.notices.length=0;ui.state.dirty=true;
  ui.element('save').onclick=async()=>{};
  await ui.element('returnToWorkspace').onclick();
  assert.equal(ui.state.dirty,true);
  assert.deepEqual(ui.calls,[]);
});
