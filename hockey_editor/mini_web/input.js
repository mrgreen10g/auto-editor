'use strict';
let inputState=null,draftId='',draftLoaded='',inputStep='setup',inputBrowser=null,inputFolderTarget='inputParent',deviceBusy=false,uploadStop=false;
let createRequest=crypto.randomUUID(),serverScriptVersion='';
function inputStepTo(step){
 if(step!=='setup'&&!draftId){errorNotice('Сначала выберите папку выпуска или сохранённый черновик.');return}
 if(step==='files'&&inputState?.draft&&!inputState.draft.blocks.length){errorNotice('Сначала сохраните сценарий и определите разборы.');return}
 inputStep=step;$('inputCommon').hidden=step!=='setup';for(const s of ['setup','script','files','summary'])$('input_'+s).hidden=s!==step;
 $('serverImportPanel').hidden=step!=='setup';
 $('presenterControls')&&$(step==='setup'?'serverMediaSlot':'hostMediaSlot').append($('presenterControls'));
 for(const b of $('inputSteps').querySelectorAll('button'))b.classList.toggle('active',b.dataset.step===step);
}
function inputProfiles(){
 $('inputProfile').replaceChildren();for(const [id,label] of inputState.profiles[$('inputSpeaker').value.split('_')[0]])if(id.endsWith('_shorts')===$('inputSpeaker').value.endsWith('_shorts'))$('inputProfile').add(new Option(label,id));
}
function line(parent,text,tag='p'){const e=document.createElement(tag);e.textContent=text;parent.append(e);return e}
function fileAction(parent,label,action){const b=document.createElement('button');b.textContent=label;b.onclick=()=>guard(action);parent.append(b);return b}
async function refreshInputs(){
 inputState=await api('input-status',{id:draftId});const d=inputState.draft;if(d)draftId=d.id;
 $('draftChoice').replaceChildren(new Option('Новый выпуск…',''));for(const r of inputState.drafts.slice().reverse())$('draftChoice').add(new Option(r.name+' · '+r.profile,r.id));$('draftChoice').value=draftId;
 if(!$('inputProfile').options.length)inputProfiles();
 for(const p of inputState.presets)if(![...$('inputPreset').options].some(o=>o.value===p))$('inputPreset').add(new Option(p,p));
 if(!d){$('draftFolder').textContent='';inputStepTo('setup');return}
 renderPresenter(d);
 $('draftFolder').textContent=d.folder;$('scriptSourceHint').textContent=d.script_source?'Файл для повторного чтения: '+d.script_source:'Сценарий ещё не сохранён.';
 const reuse=$('reuseChoice').value;$('reuseChoice').replaceChildren();for(const r of inputState.reusable)$('reuseChoice').add(new Option(r.label,r.draft+':'+r.file));if([...$('reuseChoice').options].some(x=>x.value===reuse))$('reuseChoice').value=reuse;
 if(draftLoaded!==d.id){
  draftLoaded=d.id;$('inputSpeaker').value=(d.profile.startsWith('uz_')?'uz':'ru')+(d.profile.endsWith('_shorts')?'_shorts':'_long');inputProfiles();$('inputProfile').value=d.profile;$('inputScript').value=d.script;$('inputAssets').value=d.asset_folder||inputState.kits[d.profile]||'';
  for(const id of ['inputPreset','draftPreset']){$(id).replaceChildren(new Option('Стандартные',''));for(const p of inputState.presets)$(id).add(new Option(p,p));} $('draftPreset').value=d.preset;
  renderDraftSettings(d);renderInputBlocks(d);inputStepTo(d.project?'summary':d.blocks.length?'files':'script');
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
  if(r.role==='mic')line(card,r.block==='*'?'Общая запись для всех частей':'Для части: '+(hosts.find(h=>h.id===r.block)?.name||'удалена'),'small');
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
 line($('inputSummary'),'Частей ведущего: '+summary.hosts.length+' · Микрофон: '+(summary.microphone||'звук камеры'));
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
 $(inputFolderTarget).closest('label').after($('inputBrowser'));
 $('inputBrowser').scrollIntoView({block:'nearest'});
}
$('inputTab').onclick=()=>guard(()=>switchPage('input'));
function serverPayload(){return {folder:$('serverFolder').value,profile:$('inputProfile').value,preset:$('inputPreset').value}}
$('chooseServerFolder').onclick=()=>guard(async()=>{inputFolderTarget='serverFolder';await inputBrowse($('serverFolder').value)});
let serverMicFiles=[];
$('scanServerFolder').onclick=()=>guard(scanPresenterFolder);
async function importServerFresh(attach=false){
 if(attach&&!draftId)throw Error('Сначала создайте или выберите черновик.');
 $('serverScriptStatus').textContent='Читаю сохранённый файл и заново определяю разборы…';
 const r=await api('input-server-import',{...serverPayload(),id:attach?draftId:undefined,hosts:presenterHosts.filter(Boolean),microphone:presenterMic,script:$('serverScript').value,refresh:true});
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
$('inputUseFolder').onclick=()=>guard(async()=>{$(inputFolderTarget).value=inputBrowser.path;$('inputBrowser').hidden=true;if(inputFolderTarget==='serverFolder')await scanPresenterFolder()});$('inputCloseBrowser').onclick=()=>{$('inputBrowser').hidden=true};
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
$('saveInputSettings').onclick=()=>guard(async()=>{await api('input-settings',{id:draftId,settings:readDraftSettings(),preset:$('draftPreset').value,asset_folder:$('inputAssets').value});await refreshInputs();notice('Настройки сохранены.')});
$('activateInput').onclick=()=>guard(async()=>{if(!confirm('Сохранить текущий проект редактора и открыть этот выпуск?'))return;await refresh();await api('input-activate',{id:draftId,revision:state.revision});await switchPage('process')});
async function uploadDevice(file,role,extra={}){
 const id=draftId;if(!id)throw Error('Сначала создайте выпуск.');
 const sample=await new Blob([String(file.size)+':'+String(file.lastModified),file.slice(0,262144),file.slice(Math.max(0,file.size-262144))]).arrayBuffer();
 const fingerprint=[...new Uint8Array(await crypto.subtle.digest('SHA-256',sample))].map(x=>x.toString(16).padStart(2,'0')).join('');
 const r=await api('input-upload',{id,role,name:file.name,size:file.size,fingerprint,...extra});let offset=r.offset;
 if(r.ready)return r.file;
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
 return r.file;
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

let materialRole='host', materialState={},materialCallback=null;
async function browseMaterial(path='',offset=0){
 const data=await api('folders',{path,offset,files:materialRole});materialState=data;
 $('materialBrowser').hidden=false;$('materialPath').textContent=data.path||'Диски сервера';
 if(!offset)$('materialFiles').replaceChildren();
 for(const item of data.folders){
  const b=document.createElement('button');b.className='item';b.textContent=(item.file?'📄 ':'📁 ')+item.name;
  b.onclick=()=>guard(async()=>{if(item.file){$('materialBrowser').hidden=true;if(materialCallback){const cb=materialCallback;materialCallback=null;await cb(item.path)}else $(materialRole+'ServerPath').value=item.path;}else await browseMaterial(item.path)});
  $('materialFiles').append(b);
 }
 $('materialMore').hidden=data.next==null;$('materialUp').disabled=!data.path;
}
for(const role of ['host','match','script','mic'])$('browse'+role[0].toUpperCase()+role.slice(1)+'File').onclick=()=>guard(async()=>{materialRole=role;materialCallback=null;$('browse'+role[0].toUpperCase()+role.slice(1)+'File').closest('label,details').append($('materialBrowser'));await browseMaterial()});
$('materialRoots').onclick=()=>guard(()=>browseMaterial());
$('materialUp').onclick=()=>guard(()=>browseMaterial(materialState.parent));
$('materialMore').onclick=()=>guard(()=>browseMaterial(materialState.path,materialState.next));
$('materialClose').onclick=()=>{$('materialBrowser').hidden=true};

$('micFile').onchange=()=>filesSelected($('micFile'),'mic');
$('addMicServer').onclick=()=>guard(async()=>{await api('input-local',{id:draftId,role:'mic',block:$('micHost').value,path:$('micServerPath').value});await refreshInputs()});

function renderDraftSettings(d){
 const box=$('draftSettings');box.replaceChildren();
 const bools=['auto_rotate','mirror_host','use_manual_clips','allow_other_matches','zoom','transitions','animate_cards','informative_cards','subtitles','wobble','denoise','cut_pauses','color'];
 for(const key of Object.keys(settingLabels)){
  const label=line(box,settingLabels[key],'label');let e;
  const choices=bools.includes(key)?[['true','Включено'],['false','Выключено']]:key==='insert_frequency'?[['none','Без вставок'],['low','Реже'],['normal','Обычно'],['high','Чаще']]:key==='rotate'?[[0,'0°'],[90,'90°'],[180,'180°'],[270,'270°']]:null;
  e=document.createElement(choices?'select':'input');e.dataset.draftSetting=key;
  if(['music_volume','card_sound_volume'].includes(key)){e.type='range';e.min=0;e.max=100;e.step=1;const enabled=document.createElement('input');enabled.type='checkbox';enabled.checked=d.settings?.[key]!=null;e.disabled=!enabled.checked;const out=document.createElement('output');out.textContent=enabled.checked?Math.round(d.settings[key])+'%':'Из набора';enabled.onchange=()=>{e.disabled=!enabled.checked;out.textContent=enabled.checked?e.value+'%':'Из набора'};e.oninput=()=>out.textContent=e.value+'%';label.append(enabled,out);e.value=d.settings?.[key]??(key==='music_volume'?25:20);label.append(e);continue;}
  if(choices){e.add(new Option('Из набора',''));for(const [v,t] of choices)e.add(new Option(t,v));}else{e.type='number';e.step='any';e.placeholder='Из набора';}
  e.value=d.settings?.[key]??'';label.append(e);
 }
}
function readDraftSettings(){const result={};for(const e of $('draftSettings').querySelectorAll('[data-draft-setting]')){if(e.value===''||e.disabled)continue;result[e.dataset.draftSetting]=e.value==='true'?true:e.value==='false'?false:e.dataset.draftSetting==='insert_frequency'?e.value:Number(e.value);}return result;}

// Compact presenter selector. One component moves with the current creation step.
let presenterHosts=[''],presenterMic='',presenterFiles=[],presenterMicFiles=[],presenterDraft='',presenterRoot='',presenterReadyKey='',presenterNames={},presenterRenderKey='';
function basename(path){if(presenterNames[path])return presenterNames[path];return path.split(/[\\/]/).pop()}
function presenterOptions(select,paths,value,empty){
 select.replaceChildren(new Option(empty,''));for(const path of [...new Set([...paths,...(value?[value]:[])])])select.add(new Option(basename(path),path));
 select.add(new Option('↑ Загрузить с телефона…','@device'));select.add(new Option('📁 Выбрать на сервере…','@server'));select.value=value;
}
function renderPresenter(d){
 if(d)for(const r of d.files)if(r.path&&r.name)presenterNames[r.path]=r.name;
 const readyKey=d?d.files.filter(r=>['host','mic'].includes(r.role)&&r.status==='ready').map(r=>r.id).join(','):'';
 if(d&&presenterDraft===d.id&&inputStep!=='setup'&&!deviceBusy&&readyKey!==presenterReadyKey){presenterHosts=d.files.filter(r=>r.role==='host'&&r.status==='ready').map(r=>r.path);if(!presenterHosts.length)presenterHosts=[''];presenterMic=d.files.filter(r=>r.role==='mic'&&r.status==='ready').at(-1)?.path||'';}
 if(d)presenterReadyKey=readyKey;
 if(d&&presenterDraft!==d.id){
  presenterDraft=d.id;presenterRoot=d.folder;
  presenterHosts=d.files.filter(r=>r.role==='host'&&r.status==='ready').map(r=>r.path);if(!presenterHosts.length)presenterHosts=[''];
  presenterMic=d.files.filter(r=>r.role==='mic'&&r.status==='ready').at(-1)?.path||'';
  // Fetch the folder inventory once, including after reopening a saved draft.
  api('input-server-files',{folder:d.folder,profile:d.profile}).then(r=>{if(presenterDraft!==d.id||presenterRoot!==d.folder)return;presenterFiles=r.hosts;presenterMicFiles=r.microphones;drawPresenter()}).catch(()=>{});
 }
 drawPresenter();
}
function drawPresenter(force=false){
 const key=JSON.stringify([presenterHosts,presenterMic,presenterFiles,presenterMicFiles,presenterNames]);if(!force&&key===presenterRenderKey)return;presenterRenderKey=key;
 const box=$('presenterRows');box.replaceChildren();
 presenterHosts.forEach((path,i)=>{
  const row=document.createElement('div');row.className='presenter-row';box.append(row);
  const label=document.createElement('label');label.textContent='Часть '+(i+1);row.append(label);
  const select=document.createElement('select');select.dataset.part=String(i);label.append(select);
  presenterOptions(select,presenterFiles.filter(p=>p!==presenterMic&&!presenterHosts.some((h,j)=>j!==i&&h===p)),path,'Выбрать запись…');
  select.onchange=()=>guard(()=>presenterChoose('host',i,select.value,row));
  if(i>0)fileAction(row,'↑',async()=>{[presenterHosts[i-1],presenterHosts[i]]=[presenterHosts[i],presenterHosts[i-1]];await savePresenter()}).setAttribute('aria-label','Передвинуть часть выше');
  if(presenterHosts.length>1)fileAction(row,'×',async()=>{presenterHosts.splice(i,1);await savePresenter()}).setAttribute('aria-label','Убрать часть');
 });
 presenterOptions($('presenterMicrophone'),presenterMicFiles.filter(p=>!presenterHosts.includes(p)),presenterMic,'Оставить звук камеры');
 $('presenterSummary').textContent='Выбрано частей: '+presenterHosts.filter(Boolean).length+' · Микрофон: '+(presenterMic?basename(presenterMic):'звук камеры');
}
async function scanPresenterFolder(){
 const r=await api('input-server-files',serverPayload());presenterRoot=r.target;presenterFiles=r.hosts;presenterMicFiles=r.microphones||[];
 const same=inputState?.draft?.folder===r.target;
 presenterHosts=same?inputState.draft.files.filter(x=>x.role==='host'&&x.status==='ready').map(x=>x.path):[r.hosts[0]||''];if(!presenterHosts.length)presenterHosts=[''];
 presenterMic=same?inputState.draft.files.filter(x=>x.role==='mic'&&x.status==='ready').at(-1)?.path||'':'';
 $('serverScript').replaceChildren(new Option('Добавлю позже / сохранить выбранное',''));for(const p of r.scripts)$('serverScript').add(new Option(basename(p),p));if(r.scripts.length===1)$('serverScript').value=r.scripts[0];
 drawPresenter();$('serverMediaSlot').append($('presenterControls'));
}
async function savePresenter(){
 drawPresenter();
 if(draftId&&inputStep!=='setup'){
  await api('input-presenter',{id:draftId,hosts:presenterHosts.filter(Boolean),microphone:presenterMic});await refreshInputs();
 }
}
async function ensurePresenterDraft(){
 const desired=inputStep==='setup'?presenterRoot||$('serverFolder').value||$('inputParent').value:inputState?.draft?.folder;
 if(draftId&&(!desired||inputState?.draft?.folder===desired))return;
 if(!desired)throw Error('Сначала выберите папку выпуска.');
 const hosts=[...presenterHosts],mic=presenterMic,step=inputStep;
 const r=await api('input-create',{request:crypto.randomUUID(),folder:desired,profile:$('inputProfile').value,preset:$('inputPreset').value});
 draftId=r.id;draftLoaded='';await refreshInputs();presenterHosts=hosts;presenterMic=mic;inputStepTo(step);drawPresenter();
}
async function presenterChoose(role,index,value,row){
 if(value==='@server'){
  drawPresenter(true);materialRole=role;
  const anchor=role==='mic'?$('presenterMicrophone').closest('label'):$('presenterRows');
  anchor.after($('materialBrowser'));
  materialCallback=async path=>{if(role==='mic')presenterMic=path;else presenterHosts[index]=path;await savePresenter()};
  await browseMaterial(presenterRoot||inputState?.draft?.folder||'');return;
 }
 if(value==='@device'){
  drawPresenter(true);const input=$('presenterUpload');input.accept=role==='mic'?'video/*,audio/*,.wav,.mp3,.mkv':'video/*,.mov,.mp4';
  input.onchange=()=>guard(async()=>{
   const file=input.files[0];if(!file)return;if(deviceBusy)throw Error('Дождитесь текущей загрузки.');deviceBusy=true;
   try{await ensurePresenterDraft();const id=await uploadDevice(file,role,role==='mic'?{block:'*'}:{});const state=await api('input-status',{id:draftId});const found=state.draft.files.find(r=>r.id===id);if(!found)throw Error('Загруженный файл не найден.');presenterNames[found.path]=found.name;if(role==='mic')presenterMic=found.path;else presenterHosts[index]=found.path;await savePresenter();drawPresenter();}
   finally{deviceBusy=false;input.value=''}
  });input.click();return;
 }
 if(role==='mic')presenterMic=value;else presenterHosts[index]=value;await savePresenter();
}
$('addPresenterPart').onclick=()=>{presenterHosts.push('');drawPresenter()};
$('presenterMicrophone').onchange=()=>guard(()=>presenterChoose('mic',0,$('presenterMicrophone').value,$('presenterMicrophone').closest('label')));
$('presenterDriveAdd').onclick=()=>guard(async()=>{await ensurePresenterDraft();await api('input-host-links',{id:draftId,urls:$('presenterDriveLinks').value.split(/\r?\n/).map(x=>x.trim()).filter(Boolean)});$('presenterDriveLinks').value='';presenterDraft='';await refreshInputs()});
