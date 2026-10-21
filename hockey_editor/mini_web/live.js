'use strict';
// Text/logo composition over a reusable video bed. All artwork comes from the
// export renderer; only geometry, scheduling and animation run in the browser.
let liveActive=false,liveScene=null,liveKey='',liveEpoch=0,liveImages=new Map(),livePending=new Set(),liveRetry=new Map(),liveDrag=null,liveHits=[],liveTextTimer;
const liveCanvas=$('liveCanvas');
function clearLiveImages(){for(const a of liveImages.values())URL.revokeObjectURL(a.url);liveImages.clear();livePending.clear();liveRetry.clear();}
function stopLive(){liveActive=false;liveScene=null;liveEpoch++;clearLiveImages();liveCanvas.hidden=true;$('liveMove').hidden=true;liveCanvas.classList.remove('moving');$('liveMove').textContent='Двигать плашки на видео';}
async function fetchLiveArt(card,text){
 const epoch=liveEpoch,revision=editorState.revision,k=card.id;
 if(livePending.has(k)||(liveRetry.get(k)||0)>Date.now())return;livePending.add(k);
 try{const r=await api('live-art',{revision,id:k,...(text===undefined?{}:{text})});if(epoch!==liveEpoch||revision!==editorState.revision)return;
 const bytes=Uint8Array.from(atob(r.image),c=>c.charCodeAt(0)),url=URL.createObjectURL(new Blob([bytes],{type:'image/png'}));
 const image=new Image();image.src=url;await image.decode();if(epoch!==liveEpoch){URL.revokeObjectURL(url);return}
 const old=liveImages.get(k);if(old)URL.revokeObjectURL(old.url);liveImages.set(k,{...r,image,url});while(liveImages.size>64){const oldest=liveImages.keys().next().value;URL.revokeObjectURL(liveImages.get(oldest).url);liveImages.delete(oldest)}drawLive();
 }catch(error){liveRetry.set(k,Date.now()+5000);if(epoch===liveEpoch)$('liveStatus').textContent='Плашка не загружена: '+error.message;}
 finally{if(epoch===liveEpoch)livePending.delete(k)}
}
async function refreshLive(){
 const scene=await api('live-scene',{revision:editorState.revision});
 if(!liveActive)return;
 if(scene.key!==liveKey){stopLive();$('editVideo').pause();$('editVideo').hidden=true;previewRevision='';$('previewStatus').textContent='Изменился видеослой. Подготовьте живой предпросмотр заново. Плашки пересборки видео не требуют.';return}
 liveScene=scene;liveEpoch++;clearLiveImages();previewRevision=editorState.revision;drawLive();
}
async function startLive(){
 if(previewPreparing)throw Error('Дождитесь подготовки предпросмотра.');
 previewPreparing=true;$('livePreview').disabled=true;
 try{
 const scene=await api('live-scene',{revision:editorState.revision});
 if(liveActive&&liveKey===scene.key){await refreshLive();return}
 stopLive();$('editVideo').pause();$('editVideo').hidden=true;
 $('previewStatus').textContent='Один раз готовлю видеослой. Дальнейшие правки плашек не потребуют пересборки видео.';
 const r=await api('prepare',{mode:'live',revision:editorState.revision});let j;
 for(;;){j=await api('job',{job:r.job});if(j.status==='error')throw Error(j.error);if(j.status==='ready')break;await new Promise(r=>setTimeout(r,1500));}
 const stream=await api('preview-stream',{job:r.job});liveScene=scene;liveKey=scene.key;liveActive=true;liveEpoch++;
 previewOffset=0;previewEnd=scene.duration;previewRevision=editorState.revision;playhead=0;
 const video=$('editVideo');video.src=stream.url;video.hidden=false;liveCanvas.hidden=false;$('liveMove').hidden=false;
 $('previewStatus').textContent='Живой предпросмотр · плашки и логотипы обновляются без пересборки видео.';
 $('liveStatus').textContent='Изменения текста и логотипов получают точное оформление с сервера. Перемещение и размер отображаются сразу. Сохраните правки кнопкой «Сохранить».';updatePlayhead();drawLive();
 }finally{previewPreparing=false;$('livePreview').disabled=false}
}
$('livePreview').onclick=()=>guard(startLive);
$('liveMove').onclick=()=>{liveCanvas.classList.toggle('moving');$('liveMove').textContent=liveCanvas.classList.contains('moving')?'Закончить перемещение':'Двигать плашки на видео'};
function liveCardDraft(card){
 let c={...card};if(dragPreview?.id===c.id)c={...c,start:dragPreview.start,end:dragPreview.end};
 if(editingItem?.id===c.id&&!$('editInspector').hidden){
  for(const [field,id] of [['offset_x','cardX'],['offset_y','cardY'],['scale','cardScale']]){const v=Number($(id).value);if(Number.isFinite(v))c[field]=v;}
  const a=optionalTime($('editStart').value),b=optionalTime($('editEnd').value);if(Number.isFinite(a)&&Number.isFinite(b)&&b>a){c.start=a;c.end=b}
 }
 return c;
}
function drawLive(){
 if(!liveActive||!liveScene||$('editorPanel').hidden)return;
 const video=$('editVideo'),t=video.currentTime||0,s=liveScene.settings;
 const w=liveScene.width,h=liveScene.height;liveCanvas.width=w;liveCanvas.height=h;const ctx=liveCanvas.getContext('2d');liveHits=[];
 for(const row of liveScene.cards){const c=liveCardDraft(row);if(!(c.start<=t&&t<c.end))continue;
 if(c.title==='РАЗБОР МАТЧА'&&liveScene.games.some(([a,b])=>a<=t&&t<=b))continue;
 const art=liveImages.get(c.id);if(!art){if(livePending.size<3)fetchLiveArt(row);continue}
 const scale=Math.max(.25,Math.min(2,c.scale||1));let x=art.x+(c.offset_x||0),y=art.y+(c.offset_y||0);const iw=Math.round(art.width*scale),ih=Math.round(art.height*scale);
 const elapsed=t-c.start,left=c.end-t,edge=Math.min(.25,(c.end-c.start)/3),divider=['СМЕНА МАТЧА','ИТОГИ ВЫПУСКА'].includes(c.title),animate=(divider?s.transitions:s.animate_cards)&&c.title!=='ПОДПИСКА';
 if(h>w&&c.title!=='РАЗБОР МАТЧА'){for(const [a,b] of liveScene.panels){if(a<=t&&t<b){const e=Math.min(.35,(b-a)/3),amount=s.transitions?(1-Math.cos(Math.PI*Math.min(1,(t-a)/e,(b-t)/e)))/2:1;y+=(Math.min(1130-ih,y+70)-y)*amount;break}}}
 let rotation=0;if(s.wobble&&!divider&&c.title!=='ПОДПИСКА'){rotation=.00349*Math.sin(2*Math.PI*elapsed/4+c.index);x+=3*Math.sin(2*Math.PI*elapsed/3.7+c.index);y+=2*Math.sin(2*Math.PI*elapsed/4.3+c.index)}
 if(animate){ctx.globalAlpha=Math.max(0,Math.min(1,elapsed/edge,left/edge));if(divider)x+=1280*Math.max(0,1-elapsed/edge)**2;else y+=16*Math.max(0,1-elapsed/edge)**2+16*Math.max(0,1-left/edge)**2;}
 ctx.save();ctx.translate(x+iw/2,y+ih/2);ctx.rotate(rotation);ctx.drawImage(art.image,-iw/2,-ih/2,iw,ih);ctx.restore();ctx.globalAlpha=1;
 liveHits.push({card:c,x,y,w:iw,h:ih});if(editingItem?.id===c.id){ctx.strokeStyle='#55e1bc';ctx.lineWidth=3;ctx.strokeRect(x,y,iw,ih)}
 }
 // Fetch imminent artwork before its first frame, without an unbounded queue.
 for(const c of liveScene.cards){if(c.end>t&&c.start<t+3&&!liveImages.has(c.id)&&!livePending.has(c.id)&&livePending.size<3)fetchLiveArt(c);}
}
let lastLiveTime=-1;function liveTick(){const t=$('editVideo').currentTime;if(liveActive&&t!==lastLiveTime){lastLiveTime=t;drawLive()}requestAnimationFrame(liveTick)}requestAnimationFrame(liveTick);
for(const id of ['cardX','cardY','cardScale','editStart','editEnd'])$(id).addEventListener('input',drawLive);
$('editText').addEventListener('input',()=>{clearTimeout(liveTextTimer);const id=editingItem?.id,text=$('editText').value;liveTextTimer=setTimeout(async()=>{if(!liveActive||editingItem?.id!==id)return;const c=liveScene.cards.find(c=>c.id===id);if(!c||!text.trim())return;while(livePending.has(id)){await new Promise(r=>setTimeout(r,100));if(editingItem?.id!==id||$('editText').value!==text)return}if($('editText').value===text)await fetchLiveArt(c,text);},350)});
function livePoint(e){const r=liveCanvas.getBoundingClientRect();return {x:(e.clientX-r.left)*liveScene.width/r.width,y:(e.clientY-r.top)*liveScene.height/r.height}}
liveCanvas.onpointerdown=e=>{if(!liveActive)return;const p=livePoint(e),hit=[...liveHits].reverse().find(a=>p.x>=a.x&&p.x<=a.x+a.w&&p.y>=a.y&&p.y<=a.y+a.h);if(!hit)return;const row=editorState.items.find(c=>c.id===hit.card.id);if(!row)return;$('editVideo').pause();selectEdit(row,false);liveDrag={pointer:e.pointerId,...p,offset_x:hit.card.offset_x||0,offset_y:hit.card.offset_y||0};liveCanvas.setPointerCapture(e.pointerId);e.preventDefault()};
liveCanvas.onpointermove=e=>{if(!liveDrag||liveDrag.pointer!==e.pointerId)return;const p=livePoint(e);$('cardX').value=Math.round(Math.max(-1280,Math.min(1280,liveDrag.offset_x+p.x-liveDrag.x)));$('cardY').value=Math.round(Math.max(-1280,Math.min(1280,liveDrag.offset_y+p.y-liveDrag.y)));drawLive()};
liveCanvas.onpointerup=()=>{liveDrag=null};liveCanvas.onpointercancel=()=>{liveDrag=null};
