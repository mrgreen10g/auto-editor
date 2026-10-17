"""Mobile browser -> authenticated HTTP -> editor transaction and real previews."""
import json,sys,tempfile,threading,time
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
        run(['-y','-f','lavfi','-i','color=c=0x248875:s=640x360:r=24:d=8','-f','lavfi','-i','sine=frequency=440:duration=8','-c:v','libx264','-preset','ultrafast','-c:a','aac','-shortest',app.project.host])
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
                browser=p.chromium.launch(headless=True)
                page=browser.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
                def click(selector):
                    page.locator('body[data-busy="false"]').wait_for(timeout=60000)
                    page.locator(selector).click()
                    page.locator('body[data-busy="false"]').wait_for(timeout=60000)
                errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                script='window.Telegram={WebApp:{initData:'+json.dumps(signed())+',ready(){},expand(){}}};'
                page.route('https://telegram.org/js/telegram-web-app.js',lambda r:r.fulfill(content_type='text/javascript',body=script))
                page.goto(base);page.locator('.item').first.wait_for();click('.item >> nth=0')
                page.locator('#approve').wait_for();box=page.locator('#approve').bounding_box();assert box['y']+box['height']<=844
                click('#art');page.locator('#image').wait_for(state='visible',timeout=60000)
                click('#voice');page.locator('#audio').wait_for(state='visible',timeout=60000)
                page.locator('#text').fill('Четыре гола');click('#approve')
                page.locator('#list').wait_for(state='visible');expect(page.locator('#undo')).to_be_enabled()
                assert app.plan.cards[0].text=='Четыре гола';assert app.project_path.is_file()
                click('#undo');page.locator('.item').first.wait_for();click('.item >> nth=0')
                page.locator('#approve').wait_for(state='visible');page.set_viewport_size({'width':844,'height':390});box=page.locator('#approve').bounding_box();assert box['y']+box['height']<=390
                page.set_viewport_size({'width':390,'height':844})
                (ROOT/'build').mkdir(exist_ok=True);page.screenshot(path=str(ROOT/'build/gui-mini-card.jpg'),full_page=True)
                click('#back');click('#clips');click('.item >> nth=0')
                click('#preview');page.locator('#video').wait_for(state='visible',timeout=60000)
                page.screenshot(path=str(ROOT/'build/gui-mini-clip.jpg'),full_page=True)
                click('#approve');page.locator('#list').wait_for(state='visible')
                assert app.project.blocks[0].events[0].selection.accepted
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
                page.on('dialog',lambda dialog:dialog.accept())
                click('#startExport')
                expect(page.locator('#exportState')).to_have_text('Видео готово',timeout=60000)
                assert (root/'Mobile export.mp4').stat().st_size>1000
                page.screenshot(path=str(ROOT/'build/gui-mini-export.jpg'),full_page=True)
                assert not errors,errors
                browser.close()
        finally:stop.set();gateway.close()
    print('Mobile review, clip preview, audio, card image, persistence and undo: OK')

if __name__=='__main__':check()
