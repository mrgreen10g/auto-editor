'use strict';
const $=id=>document.getElementById(id),tg=window.Telegram?.WebApp;
let session='',state=null,current=null,detail=null,kind='card',waiting=false,blob=null;
let pageMode='review',exportState=null,folderState=null,exportRequest='';
let processState=null,processRequest='',primaryRoute='';
let resultsState=null,driveInitialized=false,resultSelected='',driveProfile='';
const driveKeys=['ru_long','ru_shorts','uz_long','uz_shorts'];
function driveDefault(profile){return (profile.startsWith('uz_')?'uz':'ru')+(profile.endsWith('_shorts')?'_shorts':'_long')}
function driveFolder(){return $('driveChoice').value==='custom'?$('customDrive').value.trim():resultsState?.drive.folders[$('driveChoice').value]||''}
function destinationLabel(){$('customDriveLabel').hidden=$('driveChoice').value!=='custom';$('driveDestination').textContent=driveFolder()?'Папка: '+driveFolder():'Укажите папку в настройках ниже.'}
function selectedResult(){return resultsState?.results.find(x=>x.id===$('resultChoice').value)}
function showResult(){
 const row=selectedResult();$('finishedPanel').hidden=!row;$('sendDrive').hidden=!row;
 if(!row)return;
 if(resultSelected!==row.id){$('resultVideo').pause();$('resultVideo').removeAttribute('src');$('resultVideo').hidden=true;resultSelected=row.id}
 $('resultMeta').textContent=(row.size/1048576).toFixed(1)+' МБ'+(row.duration?' · '+Math.round(row.duration)+' с':'')+(row.available?'':' · файл недоступен на сервере');
 $('watchResult').disabled=!row.available;
 const upload=row.upload,active=upload?.status==='uploading';
 $('uploadMessage').textContent=upload?(upload.message||'')+(upload.folder_name?' · '+upload.folder_name:''):'Видео готово на сервере.';
 $('uploadProgress').hidden=!upload;$('uploadProgress').value=upload?.progress||0;
 $('pauseUpload').hidden=!active;$('sendDrive').disabled=!row.available||!resultsState.drive.connected||resultsState.upload_busy;
 $('sendDrive').textContent=upload&&['error','paused'].includes(upload.status)?'Продолжить отправку на Диск':'Отправить готовое видео на Диск';
 const link=upload?.status==='completed'&&/^https:\/\/drive\.google\.com\/file\/d\/[A-Za-z0-9_-]+\/view$/.test(upload.url||'');
 $('driveLink').hidden=!link;$('copyDriveLink').hidden=!link;$('copyDriveFallback').hidden=true;if(link)$('driveLink').href=upload.url;
}
async function refreshResults(){
 resultsState=await api('result-status');const old=$('resultChoice').value;
 $('resultChoice').replaceChildren();for(const row of resultsState.results)$('resultChoice').add(new Option((row.title||row.name)+' · '+new Date(row.created*1000).toLocaleString(),row.id));
 if(resultsState.results.some(x=>x.id===old))$('resultChoice').value=old;
 $('driveAccount').textContent=resultsState.drive.connected?'Подключён: '+resultsState.drive.account:'Сначала подключите аккаунт в настройках Google Диска на сервере.';
 if(!driveInitialized){
  for(const key of driveKeys)$('folder_'+key).value=resultsState.drive.folders[key]||'';
  $('driveChoice').value=driveDefault(exportState.profile);$('autoUpload').checked=resultsState.drive.auto;driveInitialized=true;
 }
 if(driveProfile!==exportState.profile){driveProfile=exportState.profile;$('driveChoice').value=driveDefault(driveProfile)}
 destinationLabel();showResult();
}
function notice(text){$('notice').textContent=text}
async function api(route,data={},raw=false){
 const response=await fetch('/api/'+route,{method:'POST',headers:{'Content-Type':'application/json',...(session?{Authorization:'Bearer '+session}:{})},body:JSON.stringify(data),cache:'no-store'});
 if(!response.ok){const result=await response.json();const error=new Error(result.error||'Ошибка сервера');error.status=response.status;throw error}
 return raw?response.blob():response.json();
}
function buttons(){for(const id of ['approve','remove','pending'])$(id).disabled=waiting||!current||state?.locked;$('undo').disabled=waiting||!state?.undo||state?.locked;}
async function refresh(){
 const updated=await api('state');
 if(current&&state&&updated.revision!==state.revision){notice('Проект изменился. Вернитесь к списку и откройте элемент заново.');current=null;$('actions').hidden=true;}
 state=updated;$('title').textContent=state.title+' · '+state.profile;
 const total=state.items.filter(x=>x.status==='pending').length;$('reviewBadge').textContent=total?String(total):'02';
 if(state.locked)notice(state.busy?'Сервер обрабатывает выпуск. Проверка станет доступна после завершения.':'На ПК открыто окно правок. Закройте его перед изменениями с телефона.');
 renderList();buttons();
}

function rowsForReview(){return (state?.items||[]).filter(x=>x.kind===kind&&(!$('blockFilter').value||x.block===$('blockFilter').value)&&(kind==='clip'||!$('typeFilter').value||x.category===$('typeFilter').value))}
function filteredRows(){return rowsForReview().filter(x=>$('all').checked||x.status==='pending')}
function filterOptions(id,rows,key,label,placeholder){
 const element=$(id),selected=element.value,options=new Map(rows.map(x=>[x[key],x[label]]));element.replaceChildren(new Option(placeholder,''));
 for(const [value,title] of options)if(value)element.add(new Option(title,value));
 if(options.has(selected))element.value=selected;
}
function renderList(){
 if(!state)return;$('items').replaceChildren();let rows=state.items.filter(x=>x.kind===kind);let pending=rows.filter(x=>x.status==='pending').length;
 filterOptions('blockFilter',rows,'block','block_title','Все разборы');filterOptions('typeFilter',rows,'category','category','Все типы');
 $('typeFilterLabel').hidden=kind==='clip';
 $('counts').textContent=`Осталось: ${pending} · показано: ${filteredRows().length}`;
 $('clips').textContent='Видео · '+state.items.filter(x=>x.kind==='clip'&&x.status==='pending').length;
 $('cards').textContent='Плашки · '+state.items.filter(x=>x.kind==='card'&&x.status==='pending').length;
 $('clips').classList.toggle('active',kind==='clip');$('cards').classList.toggle('active',kind==='card');
 for(const item of filteredRows()){
  const button=document.createElement('button');button.className='item';const title=document.createElement('strong'),text=document.createElement('span'),status=document.createElement('small');
  title.textContent=item.title;text.textContent=item.text;status.textContent=({pending:'Нужно решение',confirmed:'Подтверждено',deleted:'Удалено / ведущий'})[item.status];button.append(title,text,status);button.onclick=()=>guard(()=>open(item.id));$('items').append(button);
 }
 if(!$('items').children.length){const p=document.createElement('p');p.textContent='Нет элементов для проверки. Если поиск ещё идёт — обновите список после уведомления.';$('items').append(p)}
}
function clearMedia(){for(const id of ['video','audio']){$(id).pause();$(id).removeAttribute('src');$(id).hidden=true}$('image').hidden=true;$('image').removeAttribute('src');if(blob)URL.revokeObjectURL(blob);blob=null;$('translation').hidden=true;}
function back(){clearMedia();current=null;document.body.classList.remove('reviewing');$('detail').hidden=true;$('actions').hidden=true;$('list').hidden=pageMode!=='review';buttons();}
function payload(){return {id:current,revision:state.revision,text:$('text').value,recognized:$('recognized').value,owner:$('owner').value,choice:$('choice').value,start:Number($('start').value),end:Number($('end').value),time:Number($('eventTime').value)}}
function choice(){const c=detail.options.find(x=>x.key===$('choice').value);if(c){$('start').value=c.start;$('end').value=c.end;$('eventTime').value=c.time}}
async function open(id){
 const result=await api('item',{id,revision:state.revision});clearMedia();detail=result;current=id;
 document.body.classList.add('reviewing');
 const rows=filteredRows(),position=rows.findIndex(x=>x.id===id);
 $('itemPosition').textContent=position>=0?`${position+1} из ${rows.length}`:'';
 $('previousItem').disabled=position<=0;$('nextItem').disabled=position<0||position>=rows.length-1;
 $('list').hidden=true;$('detail').hidden=false;$('actions').hidden=false;$('itemTitle').textContent=result.title;$('where').textContent=result.where||'';$('reason').textContent=result.reason||'';
 for(const field of ['script','recognized','text'])$(field).value=result[field]||'';
 const clip=result.kind==='clip';$('clipFields').hidden=!clip;$('preview').hidden=!clip;$('voice').hidden=!result.voice;$('art').hidden=clip;$('textLabel').hidden=clip;$('ownerLabel').hidden=!result.forecast;
 $('context').hidden=clip;$('contextHint').hidden=clip;$('recognizedLabel').hidden=clip;$('timingDetails').open=clip;
 $('translate').hidden=result.language!=='uz';$('remove').textContent=clip?'Оставить ведущего':'Удалить плашку';
 $('owner').replaceChildren();for(const owner of result.owners||[]){const o=new Option(owner.title,owner.id);$('owner').add(o)}$('owner').value=result.owner||'';
 $('choice').replaceChildren();for(const option of result.options||[])$('choice').add(new Option(option.title,option.key));if(result.choice)$('choice').value=result.choice.key;
 if(clip)choice();else{$('start').value=result.start;$('end').value=result.end}
 $('sourceTime').textContent=clip?'Границы в исходной записи матча.':'В исходной речи: '+result.source_start.toFixed(2)+'–'+result.source_end.toFixed(2)+' с.';
 notice('Решение применяется к открытому проекту и сохраняется на сервере.');buttons();window.scrollTo(0,0);
}
async function decide(decision){
 if(decision==='deleted'&&!confirm(detail.kind==='clip'?'Пропустить вставку и оставить ведущего?':'Удалить эту плашку?'))return;
 const result=await api('action',{...payload(),decision});back();await refresh();notice('Решение сохранено: '+result.saved);
 const next=filteredRows().find(x=>x.status==='pending');if(next&&decision!=='pending')await open(next.id);
}
async function prepare(mode){
 const id=current,revision=state.revision;notice('Готовлю '+(mode==='translation'?'перевод':'предпросмотр')+' на сервере…');
 const result=await api('prepare',{...payload(),mode});
 for(let i=0;i<240;i++){
  await new Promise(r=>setTimeout(r,1500));if(current!==id||state.revision!==revision)return;
  const job=await api('job',{job:result.job});if(job.status==='error')throw new Error(job.error);if(job.status!=='ready')continue;
  if(mode==='translation'){$('translation').textContent=['Сценарий','Распознанная речь','Текст плашки'].map((x,i)=>x+'\n'+job.texts[i]).join('\n\n');$('translation').hidden=false;notice('Перевод готов.');return}
  const file=await api('media',{job:result.job},true);clearMedia();blob=URL.createObjectURL(file);const element=$(mode==='voice'?'audio':mode==='art'?'image':'video');element.src=blob;element.hidden=false;notice('Предпросмотр готов. Нажмите воспроизведение.');return;
 }
 throw new Error('Подготовка занимает больше времени. Обновите список и повторите позже.');
}
async function guard(fn,background=false){if(waiting&&background)return;while(waiting)await new Promise(r=>setTimeout(r,25));waiting=true;document.body.dataset.busy='true';buttons();try{await fn()}catch(error){notice(error.message||'Нет связи с сервером. Проверьте подключение.')}finally{waiting=false;document.body.dataset.busy='false';buttons()}}
$('refresh').onclick=()=>guard(async()=>{back();await refreshPage();notice('Данные обновлены.')});$('back').onclick=()=>guard(async()=>{back();await refresh()});
$('clips').onclick=()=>{kind='clip';renderList()};$('cards').onclick=()=>{kind='card';renderList()};$('all').onchange=renderList;$('choice').onchange=choice;
$('blockFilter').onchange=renderList;$('typeFilter').onchange=renderList;
for(const [id,step] of [['previousItem',-1],['nextItem',1]])$(id).onclick=()=>guard(async()=>{
 const rows=filteredRows(),index=rows.findIndex(x=>x.id===current),next=rows[index+step];
 if(next){if(!confirm('Перейти без сохранения текущих правок?'))return;await open(next.id)}
});
for(const [id,decision] of [['approve','confirmed'],['remove','deleted'],['pending','pending']])$(id).onclick=()=>guard(()=>decide(decision));
for(const [id,mode] of [['preview','clip'],['context','context'],['voice','voice'],['art','art'],['translate','translation']])$(id).onclick=()=>guard(()=>prepare(mode));
$('undo').onclick=()=>guard(async()=>{await api('action',{revision:state.revision,decision:'undo'});back();await refresh();notice('Последнее решение отменено и сохранено.')});
guard(async()=>{tg?.ready();tg?.expand();if(!tg?.initData)throw new Error('Откройте это приложение кнопкой в личном чате со своим Telegram-ботом.');session=(await api('auth',{initData:tg.initData})).session;const page=new URLSearchParams(location.search).get('view');if(page==='clips')kind='clip';if(page==='cards')kind='card';await refresh();await switchPage(['clips','cards','review'].includes(page)?'review':page==='export'?'export':'process');notice('');});
async function refreshPage(){if(pageMode==='input')await refreshInputs();else if(pageMode==='process')await refreshProcess();else if(pageMode==='export')await refreshExport();else await refresh()}
setInterval(()=>{if(session&&!waiting&&!current)guard(refreshPage,true)},3000);

let playbackSpeed=1;
try{const saved=Number(localStorage.getItem('playbackSpeed'));if([1,1.25,1.5,1.75,2].includes(saved))playbackSpeed=saved}catch{}
for(const id of ['reviewSpeed','resultSpeed']){
 $(id).value=String(playbackSpeed);
 $(id).onchange=()=>{playbackSpeed=Number($(id).value);try{localStorage.setItem('playbackSpeed',playbackSpeed)}catch{};for(const other of ['reviewSpeed','resultSpeed'])$(other).value=String(playbackSpeed);for(const media of ['video','audio','resultVideo'])$(media).playbackRate=playbackSpeed;};
}
for(const id of ['video','audio','resultVideo'])$(id).addEventListener('loadedmetadata',()=>{$(id).playbackRate=playbackSpeed;$(id).preservesPitch=true});
$('copyDriveLink').onclick=async()=>{const url=selectedResult()?.upload?.url;if(!/^https:\/\/drive\.google\.com\/file\/d\/[A-Za-z0-9_-]+\/view$/.test(url||''))return;try{await navigator.clipboard.writeText(url);notice('Ссылка скопирована.')}catch{$('copyDriveFallback').hidden=false;$('copyDriveValue').value=url;$('copyDriveValue').focus();$('copyDriveValue').select();notice('Выделите ссылку и нажмите «Скопировать».');}};


async function refreshExport(){
 exportState=await api('export-status');
 $('exportScope').textContent=exportState.scope+' · '+exportState.profile;
 $('exportChecks').textContent=`Нужно проверить: плашки — ${exportState.cards}, видео — ${exportState.clips}. `+(exportState.has_plan?'Дорожка подготовлена.':'Перед рендером будет выполнен анализ таймингов.');
 if(!$('outputFolder').value)$('outputFolder').value=exportState.folder;
 const job=exportState.job,active=job&&['starting','running','cancelling'].includes(job.status);
 $('startExport').disabled=exportState.locked||exportState.cards>0||exportState.clips>0;
 $('cancelExport').hidden=!active;$('cancelExport').disabled=job?.status==='cancelling';
 $('exportJob').hidden=!job;
 if(job){
  $('exportState').textContent=({starting:'Запуск',running:'Идёт обработка',cancelling:'Отмена',cancelled:'Отменено',completed:'Видео готово',error:'Ошибка',review:'Нужна проверка'})[job.status]||job.status;
  $('exportMessage').textContent=job.message;$('exportError').textContent=job.error||'';$('exportTarget').textContent=job.target;
  $('exportElapsed').textContent='Прошло: '+Math.floor(job.elapsed/60)+' мин '+job.elapsed%60+' с';
  if(job.progress===null)$('exportProgress').removeAttribute('value');else $('exportProgress').value=job.progress;
 }
 await refreshResults();
}
async function switchPage(mode){pageMode=mode;if(mode!=='export')$('resultVideo').pause();back();notice('');$('pageTitle').textContent=({input:'Создание выпуска',review:'Проверка',export:'Результат',process:'Процесс'})[mode];$('inputPanel').hidden=mode!=='input';$('list').hidden=mode!=='review';$('exportPanel').hidden=mode!=='export';$('processPanel').hidden=mode!=='process';for(const name of ['input','review','export','process']){$(name+'Tab').classList.toggle('active',mode===name);$(name+'Tab').setAttribute('aria-current',mode===name?'page':'false')}await refreshPage();window.scrollTo(0,0)}
async function browse(path='',offset=0){
 const data=await api('folders',{path,offset});folderState=data;$('folderBrowser').hidden=false;$('folderPath').textContent=data.path||'Диски сервера';if(!offset)$('folders').replaceChildren();
 for(const item of data.folders){const b=document.createElement('button');b.className='item';b.textContent='📁 '+item.name;b.onclick=()=>guard(()=>browse(item.path));$('folders').append(b)}
 $('folderMore').hidden=data.next===null||data.next===undefined;$('useFolder').disabled=!data.path;$('folderUp').disabled=!data.path;
 $('folderFree').textContent=data.free===null?'':'Свободно: '+(data.free/1073741824).toFixed(1)+' ГБ';
}
$('reviewTab').onclick=()=>guard(()=>switchPage('review'));$('exportTab').onclick=()=>guard(()=>switchPage('export'));
$('folderRoots').onclick=()=>guard(()=>browse());
$('browseFolder').onclick=()=>guard(async()=>{try{await browse($('outputFolder').value)}catch(error){if(error.status===400)await browse();else throw error}});$('folderUp').onclick=()=>guard(()=>browse(folderState.parent));$('folderMore').onclick=()=>guard(()=>browse(folderState.path,folderState.next));
$('useFolder').onclick=()=>{$('outputFolder').value=folderState.path;$('folderBrowser').hidden=true;exportRequest=''};$('closeFolders').onclick=()=>{$('folderBrowser').hidden=true};
$('outputName').oninput=()=>{exportRequest=''};
$('startExport').onclick=()=>guard(async()=>{
 await refreshExport();if(exportState.locked||exportState.cards||exportState.clips)throw new Error('Сначала завершите обработку и проверку.');
 if(!confirm('Запустить рендер: '+exportState.scope+'?\n'+$('outputFolder').value+'\n'+$('outputName').value))return;
 if(!exportRequest)exportRequest=crypto.randomUUID();
 try{await api('export-start',{revision:exportState.revision,request:exportRequest,folder:$('outputFolder').value,name:$('outputName').value,drive_upload:$('autoUpload').checked,drive_folder:driveFolder()})}catch(error){if(error.status)exportRequest='';throw error}
 exportRequest='';await refreshExport();notice('Рендер запущен на сервере. Telegram можно закрыть.');
});
$('cancelExport').onclick=()=>guard(async()=>{if(!confirm('Остановить текущий рендер?'))return;await api('export-cancel',{job:exportState.job.id});await refreshExport()});
$('driveChoice').onchange=()=>{destinationLabel();exportRequest=''};$('customDrive').oninput=destinationLabel;
$('autoUpload').onchange=()=>{exportRequest=''};
$('resultChoice').onchange=()=>{const row=selectedResult();if(row)$('driveChoice').value=driveDefault(row.profile);destinationLabel();showResult()};
$('watchResult').onclick=()=>guard(async()=>{const row=selectedResult();if(!row)return;const result=await api('result-stream',{id:row.id});$('resultVideo').src=result.url;$('resultVideo').hidden=false;notice('Видео готово к просмотру. Нажмите воспроизведение.')});
$('resultVideo').onerror=()=>notice('Не удалось воспроизвести видео. Нажмите «Посмотреть полное видео» для обновления ссылки; при истечении сессии откройте Mini App заново.');
$('saveDriveFolders').onclick=()=>guard(async()=>{const folders={};for(const key of driveKeys)folders[key]=$('folder_'+key).value;await api('drive-config',{folders,auto:$('autoUpload').checked});await refreshResults();notice('Папки Google Диска сохранены.')});
$('sendDrive').onclick=()=>guard(async()=>{const row=selectedResult();if(!row)return;await api('drive-start',{id:row.id,folder:driveFolder()});await refreshResults();notice('Отправка выполняется на сервере. Telegram можно закрыть.')});
$('pauseUpload').onclick=()=>guard(async()=>{await api('drive-pause',{id:selectedResult().id});notice('Останавливаем отправку после текущего запроса…');await refreshResults()});

async function refreshProcess(){
 processState=await api('process-status');const s=processState,j=s.job;
 $('processScope').textContent=s.scope;$('processNext').textContent=s.next;
 $('processSteps').replaceChildren();
 for(const step of s.steps){const row=document.createElement('p'),name=document.createElement('strong'),value=document.createElement('span');name.textContent=step.name;value.textContent=step.state;row.append(name,value);$('processSteps').append(row)}
 $('autoTiming').checked=s.auto_timing;$('findClips').disabled=!s.can_goals;$('findTimings').disabled=!s.can_analyze;
 primaryRoute=s.busy?'':s.clips?'clips':s.cards?'cards':s.can_render?'export':s.can_analyze?'analyze':s.can_goals?'goals':'';
 $('primaryAction').textContent=({clips:`Проверить видео · ${s.clips}`,cards:`Проверить плашки · ${s.cards}`,export:'Настроить рендер',analyze:'Найти тайминги и плашки',goals:'Найти фрагменты'})[primaryRoute]||(s.busy?'Сервер работает…':'Ожидание материалов');
 $('primaryAction').disabled=!primaryRoute||s.locked;
 $('primaryHint').textContent=s.busy?'Можно закрыть Telegram — обработка продолжится на сервере.':s.clips||s.cards?'Решения сохраняются сразу в проекте на сервере.':'Все этапы используют текущий проект и настройки редактора.';
 $('cancelProcess').hidden=!s.can_cancel;$('processJob').hidden=!j;
 $('processState').textContent=j?({running:'Идёт обработка',cancelling:'Остановка',completed:'Этап завершён',cancelled:'Отменено',error:'Нужен повторный запуск',review:'Нужна проверка'})[j.status]:'';
 $('processMessage').textContent=j?.message||s.message;$('processError').textContent=j?.error||'';
 $('processElapsed').textContent=j?'Прошло: '+Math.floor(j.elapsed/60)+' мин '+j.elapsed%60+' с':'';
 $('processProgress').hidden=!s.busy;if(j?.progress===null||!j)$('processProgress').removeAttribute('value');else $('processProgress').value=j.progress;
 $('processLog').textContent=s.log.join('\n');
}
async function startProcess(stage){
 await refreshProcess();if(!processState['can_'+stage])throw new Error('Этап пока недоступен. Завершите проверку или текущую обработку.');
 const prompt=stage==='goals'?'Запустить поиск фрагментов? При повторном подборе существующие вставки и правки дорожки могут быть заменены.':'Запустить поиск таймингов и плашек?';
 if(!confirm(prompt+'\n'+processState.scope))return;
 if(!processRequest)processRequest=crypto.randomUUID();
 try{await api('process-start',{stage,revision:processState.revision,request:processRequest,replace:stage==='goals'})}catch(error){if(error.status)processRequest='';throw error}
 processRequest='';await refreshProcess();notice('Этап запущен на сервере. Telegram можно закрыть.');
}
$('processTab').onclick=()=>guard(()=>switchPage('process'));
$('findClips').onclick=()=>guard(()=>startProcess('goals'));$('findTimings').onclick=()=>guard(()=>startProcess('analyze'));
$('autoTiming').onchange=()=>guard(async()=>{const value=$('autoTiming').checked;try{await api('process-config',{revision:processState.revision,auto_timing:value})}finally{await refreshProcess()}});
$('primaryAction').onclick=()=>guard(async()=>{
 const route=primaryRoute;
 if(route==='clips'||route==='cards'){kind=route==='clips'?'clip':'card';$('blockFilter').value='';$('typeFilter').value='';$('all').checked=false;await switchPage('review')}
 else if(route==='export')await switchPage('export');
 else if(route)await startProcess(route);
});
$('cancelProcess').onclick=()=>guard(async()=>{if(!confirm('Остановить текущий этап? Автоматическое продолжение будет отменено.'))return;await api('process-cancel',{job:processState.job.id});await refreshProcess()});





