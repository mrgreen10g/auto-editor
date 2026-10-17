'use strict';
const $=id=>document.getElementById(id),tg=window.Telegram?.WebApp;
let session='',state=null,current=null,detail=null,kind='card',waiting=false,blob=null;
function notice(text){$('notice').textContent=text}
async function api(route,data={},raw=false){
 const response=await fetch('/api/'+route,{method:'POST',headers:{'Content-Type':'application/json',...(session?{Authorization:'Bearer '+session}:{})},body:JSON.stringify(data),cache:'no-store'});
 if(!response.ok){const result=await response.json();throw new Error(result.error||'Ошибка сервера')}
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
function back(){clearMedia();current=null;$('detail').hidden=true;$('actions').hidden=true;$('list').hidden=false;buttons();}
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
async function guard(fn){if(waiting)return;waiting=true;buttons();try{await fn()}catch(error){notice(error.message||'Нет связи с сервером. Проверьте подключение.')}finally{waiting=false;buttons()}}
$('refresh').onclick=()=>guard(async()=>{back();await refresh();if(!state.locked)notice('Список обновлён.')});$('back').onclick=()=>guard(async()=>{back();await refresh()});
$('clips').onclick=()=>{kind='clip';renderList()};$('cards').onclick=()=>{kind='card';renderList()};$('all').onchange=renderList;$('choice').onchange=choice;
for(const [id,decision] of [['approve','confirmed'],['remove','deleted'],['pending','pending']])$(id).onclick=()=>guard(()=>decide(decision));
for(const [id,mode] of [['preview','clip'],['voice','voice'],['art','art'],['translate','translation']])$(id).onclick=()=>guard(()=>prepare(mode));
$('undo').onclick=()=>guard(async()=>{await api('action',{revision:state.revision,decision:'undo'});back();await refresh();notice('Последнее решение отменено и сохранено.')});
guard(async()=>{tg?.ready();tg?.expand();if(!tg?.initData)throw new Error('Откройте это приложение кнопкой в личном чате со своим Telegram-ботом.');session=(await api('auth',{initData:tg.initData})).session;await refresh();notice('Подключено к редактору.');});
setInterval(()=>{if(session&&!waiting&&!current)guard(refresh)},15000);
