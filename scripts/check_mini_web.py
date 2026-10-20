"""Mobile browser -> authenticated HTTP -> editor transaction and real previews."""
import copy,json,sys,tempfile,threading,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from test_mini_app import app_fixture,signed,TOKEN,OWNER
from hockey_editor.mini_bridge import Bridge
from hockey_editor.mini_server import Gateway
from hockey_editor.media import run
from hockey_editor.model import MatchSource,EventRequest,EventSelection
from hockey_editor.goals import source_signature
from playwright.sync_api import sync_playwright,expect

def check():
    with tempfile.TemporaryDirectory() as d:
        root=Path(d);app=app_fixture(root)
        app.project.blocks[0].script+=' В этом матче команда уверенно сыграла в атаке.'
        from hockey_editor.timeline import Insert
        app.plan.inserts=[Insert(app.project.host,2,3,0,'Тестовый игровой фрагмент')]
        run(['-y','-f','lavfi','-i','color=c=0x248875:s=640x360:r=24:d=8','-f','lavfi','-i','sine=frequency=440:duration=8','-c:v','libx264','-preset','ultrafast','-c:a','aac','-shortest',app.project.host])
        # Exercise the vertical compositor too, without changing the live project.
        from hockey_editor.mini_preview import snapshot,render
        from hockey_editor.media import probe
        portrait=copy.deepcopy(app.project);portrait.profile='uz_hockey_shorts'
        portrait.settings.width=720;portrait.settings.height=1280;portrait.blocks[0].language='uz'
        spec=snapshot(portrait,app.plan,0,app.plan.review_items[0],app.plan.cards[0],{})
        info=probe(render(spec,root,'portrait-context')['file'])
        assert (info['width'],info['height'])==(360,640) and info['audio']
        source=MatchSource(app.project.host,'СКА','Лада');app.project.matches=[source];block=app.project.blocks[0];block.match_ids=[source.id]
        block.events=[EventRequest(source.id,'Команда забила три гола.',selection=EventSelection('test',1,4,2,source_signature(source),False))]
        bridge=Bridge(app);gateway=Gateway(bridge,dict(token=TOKEN,chat_id=OWNER,mini_url='https://test.ts.net'),port=0)
        base='http://127.0.0.1:'+str(gateway.server.server_address[1]);gateway.config['mini_url']=base
        stop=threading.Event()
        def pump():
            while not stop.wait(.01):bridge.drain()
        thread=threading.Thread(target=pump,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                # Windows' bundled test Chromium lacks H.264/AAC. The runner's
                # stock Chrome exercises the same MP4 codecs used by phones.
                browser=p.chromium.launch(headless=True,**({'channel':'chrome'} if sys.platform=='win32' else {}))
                page=browser.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
                def click(selector):
                    page.locator('body[data-busy="false"]').wait_for(timeout=60000)
                    page.locator(selector).click()
                    page.locator('body[data-busy="false"]').wait_for(timeout=60000)
                errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                script='window.Telegram={WebApp:{initData:'+json.dumps(signed())+',ready(){},expand(){},isVersionAtLeast(){return true},disableVerticalSwipes(){window.swipesDisabled=true},requestFullscreen(){window.fullscreenRequested=true},onEvent(){}}};'
                page.route('https://telegram.org/js/telegram-web-app.js',lambda r:r.fulfill(content_type='text/javascript',body=script))
                page.goto(base+'?view=cards');page.locator('.item').first.wait_for();assert page.evaluate('swipesDisabled && fullscreenRequested')
                page.locator('#blockFilter').select_option(block.uid)
                page.locator('#typeFilter').select_option(label='Статистика')
                assert page.locator('#items .item').count()==1
                click('.item >> nth=0')
                page.locator('#approve').wait_for();box=page.locator('#approve').bounding_box();assert box['y']+box['height']<=844
                click('#context');page.locator('#video').wait_for(state='visible',timeout=60000)
                context_files=list((root/'mobile-previews').glob('*.mp4'));assert context_files
                from hockey_editor.media import probe
                info=probe(context_files[0]);assert info['video'] and info['audio'] and 4.8<info['duration']<5.2
                assert app.plan.cards[0].start==1 and app.plan.duration==8
                click('#timingDetails summary');click('#art');page.locator('#image').wait_for(state='visible',timeout=60000)
                click('#voice');page.locator('#audio').wait_for(state='visible',timeout=60000)
                page.locator('#text').fill('Четыре гола');click('#approve')
                page.locator('#list').wait_for(state='visible');expect(page.locator('#undo')).to_be_enabled()
                assert app.plan.cards[0].text=='Четыре гола';assert app.project_path.is_file()
                click('#undo');page.locator('.item').first.wait_for();click('.item >> nth=0')
                page.locator('#approve').wait_for(state='visible');page.set_viewport_size({'width':844,'height':390});box=page.locator('#approve').bounding_box();assert box['y']+box['height']<=390
                page.set_viewport_size({'width':390,'height':844})
                (ROOT/'build').mkdir(exist_ok=True);page.screenshot(path=str(ROOT/'build/gui-mini-card.jpg'),full_page=True)
                click('#back');click('#clips');expect(page.locator('#clips')).to_have_class('active');click('#items .item >> nth=0')
                expect(page.locator('#clipFields')).to_be_visible()
                click('#preview');page.locator('#video').wait_for(state='visible',timeout=60000)
                page.screenshot(path=str(ROOT/'build/gui-mini-clip.jpg'),full_page=True)
                click('#approve');page.locator('#list').wait_for(state='visible')
                assert app.project.blocks[0].events[0].selection.accepted
                # A separate timing launch must work without an output filename/dialog.
                page.on('dialog',lambda dialog:dialog.accept())
                timing_calls=[]
                def timing_start(render,remote=False):
                    assert not render and remote;timing_calls.append(True);app.stage='analyze'
                    from hockey_editor.timeline import Plan
                    app.plan=Plan(0,8,[(0,8)],[],[],[],[],8)
                    bridge.process.begin('analyze');bridge.process.event('plan',None);bridge.process.event('done',None)
                app.start=timing_start
                click('#processTab');expect(page.locator('#findTimings')).to_be_enabled()
                expect(page.locator('#primaryAction')).to_have_text('Найти тайминги и плашки')
                click('#primaryAction');assert timing_calls==[True]
                expect(page.locator('#processState')).to_have_text('Этап завершён')
                page.screenshot(path=str(ROOT/'build/gui-mini-process.jpg'),full_page=True)
                # Browser output-folder picker -> authenticated start -> real MP4 -> status.
                app.cancel=threading.Event()
                def render_start(render,target=None,remote=False):
                    assert render and remote
                    app.busy=True
                    def worker():
                        try:
                            run(['-y','-i',app.project.host,'-t','1','-c:v','libx264','-preset','ultrafast','-c:a','aac',target],app.cancel)
                            bridge.export.event('result',target)
                        except Exception as error:bridge.export.event('error',str(error))
                        finally:app.busy=False
                    threading.Thread(target=worker,daemon=True).start()
                app.start=render_start
                click('#exportTab');page.locator('#outputFolder').wait_for()
                click('#browseFolder');page.locator('#useFolder').wait_for()
                click('#useFolder');page.locator('#outputName').fill('Mobile export.mp4')
                click('#startExport')
                expect(page.locator('#exportState')).to_have_text('Видео готово',timeout=60000)
                assert (root/'Mobile export.mp4').stat().st_size>1000
                click('#watchResult');page.locator('#resultVideo').wait_for(state='visible')
                # Real authenticated range playback, without fetching the whole MP4 into a blob.
                video=page.locator('#resultVideo')
                # Mobile browsers may defer preload until playback is requested.
                video.evaluate('(v) => { v.play().catch(() => {}); }')
                deadline=time.monotonic()+30
                while time.monotonic()<deadline:
                    media=video.evaluate('(v) => ({ready:v.readyState,error:v.error?.message,network:v.networkState})')
                    if media['ready']>=1 or media.get('error'):break
                    page.wait_for_timeout(100)
                assert media['ready']>=1,media
                duration=video.evaluate('(v) => v.duration');assert .8<duration<1.2
                page.locator('#resultSpeed').select_option('1.5');assert video.evaluate('(v)=>v.playbackRate')==1.5
                video.evaluate('(v) => {v.currentTime=0.5}')
                expect(page.locator('#driveChoice')).to_have_value('ru_long')
                assert len(bridge.results.records())==1
                page.screenshot(path=str(ROOT/'build/gui-mini-export.jpg'),full_page=True)
                # Create a release entirely through the mobile UI and upload a real MP4.
                from hockey_editor.mobile_inputs import Inputs
                bridge.inputs=Inputs(bridge,root/'draft-index.json')
                app.restore_plan=lambda:None;app.status.set=lambda value:None
                original_host=app.project.host
                click('#inputTab');click('#chooseInputParent')
                # Navigate via the authenticated picker to the fixture's parent.
                mobile_folder=root/'Телефон выпуск';mobile_folder.mkdir();page.locator('#inputParent').evaluate('(e,p)=>{e.value=p}',str(mobile_folder))
                click('#inputCloseBrowser');click('#chooseInputParent');click('#inputUseFolder')
                click('#createDraft')
                from test_folder_import import SCRIPT
                page.locator('#inputScript').fill(SCRIPT);click('#parseInput')
                assert page.locator('#inputBlocks input').count()==2
                click('#saveTitles');page.locator('#hostMethod').select_option('device')
                page.locator('#hostFile').set_input_files(original_host)
                expect(page.locator('#deviceProgress')).to_contain_text('готово',timeout=60000)
                click('[data-step="summary"]');expect(page.locator('#activateInput')).to_be_enabled()
                page.screenshot(path=str(ROOT/'build/gui-mini-create.jpg'),full_page=True)
                click('#activateInput');expect(page.locator('#processPanel')).to_be_visible()
                assert Path(app.project_path).name=='Выпуск.hockeyproj'
                assert len(app.project.blocks)==2 and Path(app.project.host).is_file()
                assert app.project.full_video and app.project.whole_episode
                # Mobile montage: readable times, edit type, persisted undo/redo.
                app.plan=copy.deepcopy(bridge.editor.app.plan) if bridge.editor.app.plan else None
                from hockey_editor.timeline import Plan,Card,Line
                app.plan=Plan(0,8,[(0,8)],[Line('Тестовая речь',0,8)],[],[Card(1,4,'СТАТИСТИКА','Три гола')],[],8)
                click('#editTab');expect(page.locator('#editRows .item')).to_have_count(1)
                click('#elementList summary');click('#editRows .item');page.locator('#editType').select_option('ВОПРОС ЗРИТЕЛЮ');page.locator('#editText').fill('Кто победит?');page.locator('#editStart').fill('00:01.50');click('#saveEdit')
                assert app.plan.cards[0].title=='ВОПРОС ЗРИТЕЛЮ' and app.plan.cards[0].start==1.5
                click('#editUndo');assert app.plan.cards[0].title=='СТАТИСТИКА'
                click('#editRedo');assert app.plan.cards[0].title=='ВОПРОС ЗРИТЕЛЮ'
                page.locator('#rangeStart').fill('00:02.00');page.locator('#rangeEnd').fill('00:03.00');click('#cutRange');assert app.plan.duration==7
                click('#rangePreview');page.locator('#editVideo').wait_for(state='visible',timeout=60000)
                page.wait_for_function("document.getElementById('editVideo').readyState>=2")
                assert page.evaluate('previewOffset')==2
                page.evaluate('seekTimeline(2.5)');click('#markStart');expect(page.locator('#rangeStart')).to_have_value('00:02.50')
                click('#fullPreview');page.wait_for_function("previewOffset===0 && previewEnd===7 && !previewPreparing",timeout=90000)
                page.wait_for_function("document.getElementById('editVideo').readyState>=2")
                page.evaluate('seekTimeline(4)');click('#frameForward');click('#markEnd');expect(page.locator('#rangeEnd')).to_have_value('00:04.03')
                expect(page.locator('#editKind')).to_have_count(0)
                page.locator('#rangeStart').fill('x');page.locator('#rangeStart').fill('00:02.50')
                page.locator('#elementList').evaluate('(e)=>e.open=false')
                page.locator('#timelineZoom').fill('8');page.locator('#timelineZoom').dispatch_event('input')
                assert page.evaluate('timelineWidth')>390
                page.locator('#rangeStart').focus();page.locator('#editDuration').click();assert page.evaluate("document.activeElement.id")!='rangeStart'
                page.screenshot(path=str(ROOT/'build/gui-mini-editor.jpg'),full_page=True)
                # Errors stay in view even when the page is scrolled down.
                page.locator('#rangeEnd').fill('99:00.00');click('#cutRange');expect(page.locator('#errorDialog')).to_be_visible();click('#closeError')
                # The alternate path imports existing server files without uploading.
                from test_folder_import import setup
                existing=root/'existing';existing.mkdir();setup(existing)
                click('#inputTab');page.locator('#draftChoice').select_option('');click('#inputSteps [data-step="setup"]')
                click('#serverImportPanel summary');page.locator('#serverFolder').evaluate('(e,p)=>{e.value=p}',str(existing))
                click('#scanServerFolder');click('#openServerScript');expect(page.locator('#serverScriptText')).to_have_value(SCRIPT);click('#saveServerScript');click('#importServerFolder')
                expect(page.locator('#inputSummary')).to_contain_text('АМУР')
                expect(page.locator('#activateInput')).to_be_enabled()
                assert not errors,errors
                browser.close()
        finally:stop.set();gateway.close()
    print('Mobile review, clip preview, audio, card image, persistence and undo: OK')

if __name__=='__main__':check()
