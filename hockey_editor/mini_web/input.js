'use strict';
let inputState=null,draftId='',draftLoaded='',inputStep='setup',inputBrowser=null,inputFolderTarget='inputParent',deviceBusy=false,uploadStop=false;
let createRequest=crypto.randomUUID(),serverScriptVersion='';
function inputStepTo(step){
 if(step!=='setup'&&!draftId){errorNotice('Сначала выберите папку выпуска или сохранённый черновик.');return}
 if(step==='files'&&inputState?.draft&&!inputState.draft.blocks.length){errorNotice('Сначала сохраните сценарий и определите разборы.');return}
 inputStep=step;$('inputCommon').hidden=step!=='setup';for(const s of ['setup','script','files','summary'])$('input_'+s).hidden=s!==step;
 $('serverImportPanel').hidden=step!=='setup';
 for(const b of $('inputSteps').querySelectorAll('button'))b.classList.toggle('active',b.dataset.step===step);
}
function inputProfiles(){
 $('inputProfile').replaceChildren();for(const [id,label] of inputState.profiles[$('inputSpeaker').value])$('inputProfile').add(new Option(label,id));
}
function line(parent,text,tag='p'){const e=document.createElement(tag);e.textContent=text;parent.append(e);return e}
function fileAction(parent,label,action){const b=document.createElement('button');b.textContent=label;b.onclick=()=>guard(action);parent.append(b);return b}
async function refreshInputs(){
 inputState=await api('input-status',{id:draftId});const d=inputState.draft;
 $('draftChoice').replaceChildren(new Option('Новый выпуск…',''));for(const r of inputState.drafts.slice().reverse())$('draftChoice').add(new Option(r.name+' · '+r.profile,r.id));$('draftChoice').value=draftId;
 if(!$('inputProfile').options.length)inputProfiles();
 for(const p of inputState.presets)if(![...$('inputPreset').options].some(o=>o.value===p))$('inputPreset').add(new Option(p,p));
 if(!d){$('draftFolder').textContent='';inputStepTo('setup');return}
 $('draftFolder').textContent=d.folder;$('scriptSourceHint').textContent=d.script_source?'Файл для повторного чтения: '+d.script_source:'Сценарий ещё не сохранён.';
 const reuse=$('reuseChoice').value;$('reuseChoice').replaceChildren();for(const r of inputState.reusable)$('reuseChoice').add(new Option(r.label,r.draft+':'+r.file));if([...$('reuseChoice').options].some(x=>x.value===reuse))$('reuseChoice').value=reuse;
 if(draftLoaded!==d.id){
  draftLoaded=d.id;$('inputSpeaker').value=d.profile.startsWith('uz_')?'uz':'ru';inputProfiles();$('inputProfile').value=d.profile;$('inputScript').value=d.script;$('inputAssets').value=d.asset_folder||inputState.kits[d.profile]||'';
  for(const id of ['inputPreset','draftPreset']){$(id).replaceChildren(new Option('Стандартные',''));for(const p of inputState.presets)$(id).add(new Option(p,p));} $('draftPreset').value=d.preset;
  renderInputBlocks(d);inputStepTo(d.project?'summary':d.blocks.length?'files':'script');
 }
 if(!$('inputPreset').options.length||$('inputPreset').options.length===1){for(const p of inputState.presets)if(![...$('inputPreset').options].some(o=>o.value===p))$('inputPreset').add(new Option(p,p));}
 $('hostParts').replaceChildren();
 const hosts=d.files.filter(r=>r.role==='host'&&r.status!=='removed');
 for(let i=0;i<hosts.length;i++){
  const r=hosts[i],box=line($('hostParts'),`${i+1}. ${r.name}`,'div');
  line(box,r.message||r.status,'small');if(r.url)line(box,r.url,'small');
  if(!d.project)for(const [label,step] of [['↑ Раньше',-1],['↓ Позже',1]]){
   const j=i+step;if(j<0||j>=hosts.length)continue;
   fileAction(box,label,async()=>{const expected=hosts.map(x=>x.id),order=[...expected];[order[i],order[j]]=[order[j],order[i]];await api('input-host-order',{id:d.id,expected,order});await refreshInputs()});
  }
 }
 const micSelected=$('micHost').value;$('micHost').replaceChildren();for(const h of hosts.filter(r=>r.status==='ready'))$('micHost').add(new Option(h.name,h.id));if([...$('micHost').options].some(o=>o.value===micSelected))$('micHost').value=micSelected;
 $('inputFiles').replaceChildren();
 for(const r of d.files.filter(r=>r.status!=='removed')){
  const card=document.createElement('div');card.className='input-file';$('inputFiles').append(card);
  line(card,({host:'Ведущий',match:'Запись матча',script:'Сценарий',mic:'Микрофон'})[r.role]+' · '+r.name,'strong');
  if(r.role==='mic')line(card,'Для части: '+(hosts.find(h=>h.id===r.block)?.name||'удалена'),'small');
  if(r.block&&r.role!=='mic')line(card,d.blocks.find(b=>b.uid===r.block)?.title||'','small');
  line(card,r.message||({uploading:'Передача с устройства',waiting:'Ожидание'})[r.status]||r.status);
  if(r.size)line(card,Math.min(100,Math.round(r.received/r.size*100))+'% · '+(r.received/1048576).toFixed(1)+' / '+(r.size/1048576).toFixed(1)+' МБ','small');
  if(r.role==='match'){
   line(card,/^(ru|uz)_combat/.test(d.profile)?(r.fighter||'Укажите бойца'):(r.home||'?')+' — '+(r.away||'?'));
   fileAction(card,'Участники записи',async()=>{const home=prompt(/^(ru|uz)_combat/.test(d.profile)?'Какому бойцу принадлежит запись?':'Первая команда архивной записи',r.fighter||r.home);if(home===null)return;const away=/^(ru|uz)_combat/.test(d.profile)?'':prompt('Вторая команда архивной записи',r.away);if(away===null)return;await api('input-edit',{id:d.id,file:r.id,home,away,fighter:home});await refreshInputs()});
  }
  if(['paused','error','queued'].includes(r.status))fileAction(card,'Продолжить',async()=>{if(r.source==='device'&&r.received<r.size){notice('Выберите тот же файл ещё раз в поле загрузки с устройства.');return}await api('input-retry',{id:d.id,file:r.id});await refreshInputs()});
  if(!d.project&&!['downloading','checking'].includes(r.status))fileAction(card,'Убрать из выпуска',async()=>{if(!confirm('Убрать материал из выпуска? Скачанный файл останется на сервере.'))return;await api('input-edit',{id:d.id,file:r.id,remove:true});await refreshInputs()});
 }
 const statusFor=role=>d.files.filter(r=>r.role===role&&r.status!=='removed'&&(role==='host'||r.block===$('inputBlock').value)).map(r=>r.name+' · '+(r.message||r.status)+(r.size?' · '+Math.min(100,Math.round(r.received/r.size*100))+'%':'')).join('\n');
 $('hostStatus').textContent=statusFor('host')||'Ведущий ещё не добавлен.';$('matchStatus').textContent=statusFor('match')||'Для этого разбора запись ещё не добавлена.';
 $('pauseInput').hidden=!inputState.busy;
 $('inputSummary').replaceChildren();const summary=d.summary;
 line($('inputSummary'),d.name,'h3');line($('inputSummary'),'Шаблон: '+d.profile);line($('inputSummary'),'Ведущий: '+(summary.hosts.join(', ')||'не добавлен'));
 line($('inputSummary'),'Настройки: '+(d.preset||'стандартные'));line($('inputSummary'),'Постоянные материалы: '+(d.asset_folder||inputState.kits[d.profile]||'сохранённый набор шаблона'));
 for(const b of d.blocks)line($('inputSummary'),b.title+' · записей: '+summary.counts[b.uid]);
 for(const p of [...summary.problems,...summary.notes])line($('inputSummary'),p);
 $('activateInput').disabled=!d.project&&!summary.can_create;$('activateInput').textContent=d.project?'Открыть проект и перейти к обработке':'Создать проект и перейти к обработке';
}
function renderInputBlocks(d){
 $('inputBlocks').replaceChildren();const old=$('inputBlock').value;$('inputBlock').replaceChildren();
 for(const b of d.blocks){const label=line($('inputBlocks'),'Название разбора','label'),field=document.createElement('input');field.value=b.title;label.append(field);$('inputBlock').add(new Option(b.title,b.uid));}
 if(d.blocks.some(b=>b.uid===old))$('inputBlock').value=old;
}
async function inputBrowse(path='',offset=0){
 inputBrowser=await api('folders',{path,offset});$('inputBrowser').hidden=false;$('inputBrowserPath').textContent=inputBrowser.path||'Диски сервера';
 if(!offset)$('inputFolders').replaceChildren();for(const f of inputBrowser.folders)fileAction($('inputFolders'),'📁 '+f.name,()=>inputBrowse(f.path));
 $('inputMore').hidden=inputBrowser.next==null;$('inputUseFolder').disabled=!inputBrowser.path;$('inputMkdir').disabled=!inputBrowser.path;
 $('inputBrowser').scrollIntoView({block:'start'});
}
$('inputTab').onclick=()=>guard(()=>switchPage('input'));
function serverPayload(){return {folder:$('serverFolder').value,profile:$('inputProfile').value,preset:$('inputPreset').value}}
$('chooseServerFolder').onclick=()=>guard(async()=>{inputFolderTarget='serverFolder';await inputBrowse($('serverFolder').value)});
$('scanServerFolder').onclick=()=>guard(async()=>{const r=await api('input-server-files',serverPayload());for(const [id,key] of [['serverHost','hosts'],['serverScript','scripts']]){$(id).replaceChildren();for(const p of r[key])$(id).add(new Option(p.split(/[\\/]/).pop(),p));$(id).add(new Option('Добавлю позже / сохранить уже добавленное',''));}notice('Выберите доступные материалы. Недостающие можно добавить позже.');});
async function importServerFresh(attach=false){
 if(attach&&!draftId)throw Error('Сначала создайте или выберите черновик.');
 $('serverScriptStatus').textContent='Читаю сохранённый файл и заново определяю разборы…';
 const r=await api('input-server-import',{...serverPayload(),id:attach?draftId:undefined,host:$('serverHost').value,script:$('serverScript').value,refresh:true});
 draftId=r.id;draftLoaded='';await refreshInputs();inputStepTo('summary');
 const message='Файл перечитан · '+new Date(r.updated*1000).toLocaleTimeString()+' · разборов: '+r.count+'. Проверьте сводку и откройте обновлённый проект.';
 $('serverScriptStatus').textContent=message;notice(message);
}
$('importServerFolder').onclick=()=>guard(()=>importServerFresh());
$('attachServerFolder').onclick=()=>guard(()=>importServerFresh(true));
for(const b of $('inputSteps').querySelectorAll('button'))b.onclick=()=>inputStepTo(b.dataset.step);
$('inputSpeaker').onchange=inputProfiles;
$('draftChoice').onchange=()=>guard(async()=>{draftId=$('draftChoice').value;draftLoaded='';await refreshInputs()});
$('chooseInputParent').onclick=()=>guard(async()=>{inputFolderTarget='inputParent';await inputBrowse($('inputParent').value)});
$('chooseInputAssets').onclick=()=>guard(async()=>{inputFolderTarget='inputAssets';await inputBrowse($('inputAssets').value)});
$('inputRoots').onclick=()=>guard(()=>inputBrowse());$('inputUp').onclick=()=>guard(()=>inputBrowse(inputBrowser.parent));$('inputMore').onclick=()=>guard(()=>inputBrowse(inputBrowser.path,inputBrowser.next));
$('inputUseFolder').onclick=()=>{$(inputFolderTarget).value=inputBrowser.path;$('inputBrowser').hidden=true};$('inputCloseBrowser').onclick=()=>{$('inputBrowser').hidden=true};
$('inputMkdir').onclick=()=>guard(async()=>{const r=await api('input-mkdir',{parent:inputBrowser.path,name:$('inputNewFolder').value});$('inputNewFolder').value='';await inputBrowse(r.path)});
$('createDraft').onclick=()=>guard(async()=>{const r=await api('input-create',{request:createRequest,folder:$('inputParent').value,profile:$('inputProfile').value,preset:$('inputPreset').value});createRequest=crypto.randomUUID();draftId=r.id;draftLoaded='';await refreshInputs()});
async function reparseScript(fromFile=false){
 $('scriptRefreshStatus').textContent=fromFile?'Перечитываю файл с сервера…':'Заново определяю разборы по тексту ниже…';
 try{const r=await api(fromFile?'input-script-reload':'input-script',{id:draftId,text:$('inputScript').value,reparse:true});
 draftLoaded='';await refreshInputs();inputStepTo('script');renderInputBlocks(inputState.draft);
 $('scriptRefreshStatus').textContent='Обновлено '+new Date(r.updated*1000).toLocaleTimeString()+' · разборов: '+r.count+(r.previous_project?'. После проверки сводки откройте обновлённый проект. Предыдущий сохранён.':'. Добавлено записей из папок: '+(r.added||0)+'.');
 }catch(error){$('scriptRefreshStatus').textContent='Разборы не обновлены: '+error.message;throw error}
}
$('parseInput').onclick=()=>guard(()=>reparseScript());
$('reloadServerScript').onclick=()=>guard(()=>reparseScript(true));
$('saveTitles').onclick=()=>guard(async()=>{await api('input-settings',{id:draftId,titles:[...$('inputBlocks').querySelectorAll('input')].map(e=>e.value)});await refreshInputs();renderInputBlocks(inputState.draft);inputStepTo('files')});
$('hostMethod').onchange=()=>{$('hostDrive').hidden=$('hostMethod').value!=='drive';$('hostDevice').hidden=$('hostMethod').value!=='device';$('hostServer').hidden=$('hostMethod').value!=='server'};
$('addHostLink').onclick=()=>guard(async()=>{await api('input-host-links',{id:draftId,urls:$('hostUrl').value.split(/\r?\n/).map(x=>x.trim()).filter(Boolean)});$('hostUrl').value='';await refreshInputs()});
function matchData(){return {block:$('inputBlock').value,home:$('matchHome').value,away:$('matchAway').value,fighter:$('matchHome').value}}
$('addMatchLink').onclick=()=>guard(async()=>{await api('input-link',{id:draftId,role:'match',url:$('matchUrl').value,...matchData()});await refreshInputs()});
$('reuseInput').onclick=()=>guard(async()=>{const [from_draft,file]=$('reuseChoice').value.split(':');if(!file)throw Error('Нет ранее добавленных записей.');await api('input-reuse',{id:draftId,from_draft,file,block:$('inputBlock').value});await refreshInputs()});
$('pauseInput').onclick=()=>guard(async()=>{await api('input-pause');notice('Скачивание остановится после текущего запроса.')});
$('saveInputSettings').onclick=()=>guard(async()=>{await api('input-settings',{id:draftId,preset:$('draftPreset').value,asset_folder:$('inputAssets').value});await refreshInputs();notice('Настройки сохранены.')});
$('activateInput').onclick=()=>guard(async()=>{if(!confirm('Сохранить текущий проект редактора и открыть этот выпуск?'))return;await refresh();await api('input-activate',{id:draftId,revision:state.revision});await switchPage('process')});
async function uploadDevice(file,role,extra={}){
 const id=draftId;if(!id)throw Error('Сначала создайте выпуск.');
 const sample=await new Blob([String(file.size)+':'+String(file.lastModified),file.slice(0,262144),file.slice(Math.max(0,file.size-262144))]).arrayBuffer();
 const fingerprint=[...new Uint8Array(await crypto.subtle.digest('SHA-256',sample))].map(x=>x.toString(16).padStart(2,'0')).join('');
 const r=await api('input-upload',{id,role,name:file.name,size:file.size,fingerprint,...extra});let offset=r.offset;
 if(r.ready)return;
 while(offset<file.size){
  const response=await fetch('/api/input-chunk',{method:'POST',headers:{Authorization:'Bearer '+session,'Content-Type':'application/octet-stream','X-Draft':id,'X-File':r.file,'X-Offset':String(offset)},body:file.slice(offset,offset+2*1024*1024)});
  const result=await response.json();if(!response.ok)throw Error(result.error||'Передача прервана. Выберите файл повторно.');offset=result.offset;
  $('deviceProgress').textContent=file.name+' · '+Math.round(offset/file.size*100)+'%';$(role==='host'?'hostStatus':'matchStatus').textContent=$('deviceProgress').textContent;
 }
 await api('input-finish',{id,file:r.file});
 // Complete validation before starting the next part of the presenter.
 for(;;){await new Promise(r=>setTimeout(r,1000));const s=await api('input-status',{id});const item=s.draft.files.find(x=>x.id===r.file);if(item.status==='ready')break;if(['error','paused'].includes(item.status))throw Error(item.message);}
 $('deviceProgress').textContent=file.name+' · готово';
 if(role==='script'){draftLoaded='';await refreshInputs();inputStepTo('script');}
}
async function filesSelected(element,role){
 if(deviceBusy){notice('Дождитесь передачи выбранного файла.');return}deviceBusy=true;
 try{for(const file of element.files)await uploadDevice(file,role,role==='match'?matchData():role==='mic'?{block:$('micHost').value}:{});await refreshInputs();notice('Файлы сохранены на сервере.');}
 catch(error){errorNotice(error.message);}finally{deviceBusy=false;element.value='';}
}
$('hostFile').onchange=()=>filesSelected($('hostFile'),'host');$('matchFile').onchange=()=>filesSelected($('matchFile'),'match');



$('openServerScript').onclick=()=>guard(async()=>{const r=await api('input-script-open',{...serverPayload(),script:$('serverScript').value});serverScriptVersion=r.version;$('serverScriptText').value=r.text;$('serverScriptEditor').hidden=false;$('serverScriptText').scrollIntoView({block:'center'});});
$('saveServerScript').onclick=()=>guard(async()=>{const r=await api('input-script-save',{...serverPayload(),script:$('serverScript').value,version:serverScriptVersion,text:$('serverScriptText').value});serverScriptVersion=r.version;if(![...$('serverScript').options].some(o=>o.value===r.script))$('serverScript').add(new Option(r.script.split(/[\\/]/).pop(),r.script));$('serverScript').value=r.script;$('serverScriptStatus').textContent='Изменённый файл сохранён на сервере. Выполняю повторное определение…';await importServerFresh();});
$('serverScript').onchange=()=>{$('serverScriptEditor').hidden=true;serverScriptVersion=''};
$('inputBlock').onchange=()=>guard(refreshInputs);
$('loadScriptDoc').onclick=()=>guard(async()=>{const r=await api('input-doc-start',{url:$('scriptDocUrl').value});notice('Загружаю текст Google Документа…');for(let i=0;i<90;i++){await new Promise(r=>setTimeout(r,1000));const job=await api('input-doc-status',{job:r.job});if(job.status==='error')throw Error(job.error);if(job.status==='ready'){$('inputScript').value=job.text;await reparseScript();return}}throw Error('Загрузка документа занимает слишком много времени. Повторите позже.');});

$('addHostServer').onclick=()=>guard(async()=>{await api('input-local',{id:draftId,role:'host',path:$('hostServerPath').value});await refreshInputs()});
$('addMatchServer').onclick=()=>guard(async()=>{await api('input-local',{id:draftId,role:'match',path:$('matchServerPath').value,...matchData()});await refreshInputs()});
$('addScriptServer').onclick=()=>guard(async()=>{await api('input-local',{id:draftId,role:'script',path:$('scriptServerPath').value});draftLoaded='';await refreshInputs();inputStepTo('script')});

let materialRole='host', materialState={};
async function browseMaterial(path='',offset=0){
 const data=await api('folders',{path,offset,files:materialRole});materialState=data;
 $('materialBrowser').hidden=false;$('materialPath').textContent=data.path||'Диски сервера';
 if(!offset)$('materialFiles').replaceChildren();
 for(const item of data.folders){
  const b=document.createElement('button');b.className='item';b.textContent=(item.file?'📄 ':'📁 ')+item.name;
  b.onclick=()=>guard(async()=>{if(item.file){$(materialRole+'ServerPath').value=item.path;$('materialBrowser').hidden=true;}else await browseMaterial(item.path)});
  $('materialFiles').append(b);
 }
 $('materialMore').hidden=data.next==null;$('materialUp').disabled=!data.path;
}
for(const role of ['host','match','script','mic'])$('browse'+role[0].toUpperCase()+role.slice(1)+'File').onclick=()=>guard(async()=>{materialRole=role;await browseMaterial()});
$('materialRoots').onclick=()=>guard(()=>browseMaterial());
$('materialUp').onclick=()=>guard(()=>browseMaterial(materialState.parent));
$('materialMore').onclick=()=>guard(()=>browseMaterial(materialState.path,materialState.next));
$('materialClose').onclick=()=>{$('materialBrowser').hidden=true};

$('micFile').onchange=()=>filesSelected($('micFile'),'mic');
$('addMicServer').onclick=()=>guard(async()=>{await api('input-local',{id:draftId,role:'mic',block:$('micHost').value,path:$('micServerPath').value});await refreshInputs()});
