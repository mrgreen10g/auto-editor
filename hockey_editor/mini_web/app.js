'use strict';
const $=id=>document.getElementById(id),tg=window.Telegram?.WebApp;
let session='',state=null,current=null,detail=null,kind='card',waiting=false,blob=null;
let pageMode='review',exportState=null,folderState=null,exportRequest='';
let processState=null,processRequest='';
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
 state=updated;$('title').textContent=state.title+' · '+state.profile+' · '+state.scope;
 if(state.locked)notice(state.busy?'Сервер обрабатывает выпуск. Проверка станет доступна после завершения.':'На ПК открыто окно правок. Закройте его перед изменениями с телефона.');
 renderList();buttons();
}

function renderList(){
 if(!state)return;$('items').replaceChildren();let rows=state.items.filter(x=>x.kind===kind);let pending=rows.filter(x=>x.status==='pending').length;
 $('counts').textContent=`Нужно проверить: ${pending} · всего: ${rows.length}`;
 $('clips').classList.toggle('active',kind==='clip');$('cards').classList.toggle('active',kind==='card');
 for(const item of rows.filter(x=>$('all').checked||x.status==='pending')){
  const button=document.createElement('button');button.className='item';const title=document.createElement('strong'),text=document.createElement('span'),status=document.createElement('small');
  title.textContent=item.title;text.textContent=item.text;status.textContent=({pending:'Нужно решение',confirmed:'Подтверждено',deleted:'Удалено / ведущий'})[item.status];button.append(title,text,status);button.onclick=()=>guard(()=>open(item.id));$('items').append(button);
 }
 if(!$('items').children.length){const p=document.createElement('p');p.textContent='Нет элементов для проверки. Если поиск ещё идёт — обновите список после уведомления.';$('items').append(p)}
}
function clearMedia(){for(const id of ['video','audio']){$(id).pause();$(id).removeAttribute('src');$(id).hidden=true}$('image').hidden=true;$('image').removeAttribute('src');if(blob)URL.revokeObjectURL(blob);blob=null;$('translation').hidden=true;}
function back(){clearMedia();current=null;$('detail').hidden=true;$('actions').hidden=true;$('list').hidden=pageMode!=='review';buttons();}
function payload(){return {id:current,revision:state.revision,text:$('text').value,recognized:$('recognized').value,owner:$('owner').value,choice:$('choice').value,start:Number($('start').value),end:Number($('end').value),time:Number($('eventTime').value)}}
function choice(){const c=detail.options.find(x=>x.key===$('choice').value);if(c){$('start').value=c.start;$('end').value=c.end;$('eventTime').value=c.time}}
async function open(id){
 const result=await api('item',{id,revision:state.revision});clearMedia();detail=result;current=id;
 $('list').hidden=true;$('detail').hidden=false;$('actions').hidden=false;$('itemTitle').textContent=result.title;$('where').textContent=result.where||'';$('reason').textContent=result.reason||'';
 for(const field of ['script','recognized','text'])$(field).value=result[field]||'';
 const clip=result.kind==='clip';$('clipFields').hidden=!clip;$('preview').hidden=!clip;$('voice').hidden=!result.voice;$('art').hidden=clip;$('textLabel').hidden=clip;$('ownerLabel').hidden=!result.forecast;
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
 const next=state.items.find(x=>x.kind===kind&&x.status==='pending');if(next)await open(next.id);
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
async function guard(fn){if(waiting)return;waiting=true;document.body.dataset.busy='true';buttons();try{await fn()}catch(error){notice(error.message||'Нет связи с сервером. Проверьте подключение.')}finally{waiting=false;document.body.dataset.busy='false';buttons()}}
$('refresh').onclick=()=>guard(async()=>{back();await refreshPage();notice('Данные обновлены.')});$('back').onclick=()=>guard(async()=>{back();await refresh()});
$('clips').onclick=()=>{kind='clip';renderList()};$('cards').onclick=()=>{kind='card';renderList()};$('all').onchange=renderList;$('choice').onchange=choice;
for(const [id,decision] of [['approve','confirmed'],['remove','deleted'],['pending','pending']])$(id).onclick=()=>guard(()=>decide(decision));
for(const [id,mode] of [['preview','clip'],['voice','voice'],['art','art'],['translate','translation']])$(id).onclick=()=>guard(()=>prepare(mode));
$('undo').onclick=()=>guard(async()=>{await api('action',{revision:state.revision,decision:'undo'});back();await refresh();notice('Последнее решение отменено и сохранено.')});
guard(async()=>{tg?.ready();tg?.expand();if(!tg?.initData)throw new Error('Откройте это приложение кнопкой в личном чате со своим Telegram-ботом.');session=(await api('auth',{initData:tg.initData})).session;const page=new URLSearchParams(location.search).get('view');if(page==='clips')kind='clip';if(page==='cards')kind='card';await refresh();if(page==='process'||page==='export')await switchPage(page);notice('Подключено к редактору.');});
async function refreshPage(){if(pageMode==='process')await refreshProcess();else if(pageMode==='export')await refreshExport();else await refresh()}
setInterval(()=>{if(session&&!waiting&&!current)guard(refreshPage)},3000);


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
}
async function switchPage(mode){pageMode=mode;back();$('list').hidden=mode!=='review';$('exportPanel').hidden=mode!=='export';$('processPanel').hidden=mode!=='process';for(const name of ['review','export','process'])$(name+'Tab').classList.toggle('active',mode===name);await refreshPage();window.scrollTo(0,0)}
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
 try{await api('export-start',{revision:exportState.revision,request:exportRequest,folder:$('outputFolder').value,name:$('outputName').value})}catch(error){if(error.status)exportRequest='';throw error}
 exportRequest='';await refreshExport();notice('Рендер запущен на сервере. Telegram можно закрыть.');
});
$('cancelExport').onclick=()=>guard(async()=>{if(!confirm('Остановить текущий рендер?'))return;await api('export-cancel',{job:exportState.job.id});await refreshExport()});

async function refreshProcess(){
 processState=await api('process-status');const s=processState,j=s.job;
 $('processScope').textContent=s.scope;$('processNext').textContent='Следующий шаг: '+s.next;
 $('processSteps').replaceChildren();
 for(const step of s.steps){const row=document.createElement('p'),name=document.createElement('strong'),value=document.createElement('span');name.textContent=step.name;value.textContent=step.state;row.append(name,value);$('processSteps').append(row)}
 $('autoTiming').checked=s.auto_timing;$('findClips').disabled=!s.can_goals;$('findTimings').disabled=!s.can_analyze;$('processRender').disabled=!s.can_render;
 $('cancelProcess').hidden=!s.can_cancel;$('processReview').textContent=`Проверить: видео ${s.clips}, плашки ${s.cards}`;
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
$('processReview').onclick=()=>guard(async()=>{kind=processState.clips?'clip':'card';await switchPage('review')});$('processRender').onclick=()=>guard(()=>switchPage('export'));
$('cancelProcess').onclick=()=>guard(async()=>{if(!confirm('Остановить текущий этап? Автоматическое продолжение будет отменено.'))return;await api('process-cancel',{job:processState.job.id});await refreshProcess()});

