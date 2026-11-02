"""Real optional runtime/model smoke test; does not enable AI in user settings."""
import json,sys,threading,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hockey_editor import local_ai as ai
cancel=threading.Event()
ai.install(cancel,print)
start=time.monotonic();results=[]
with ai.Session(cancel) as session:
    for script,heard in [('Команда не проиграет.','Команда не проиграет.'),('Nasaf g‘alaba qozonadi.','Nasaf mag‘lub bo‘ladi.')]:
        r=session.judge(dict(script=script,recognized=heard,reason='Проверка текста.'));results.append(r)
Path('build').mkdir(exist_ok=True)
Path('build/local-ai-check.json').write_text(json.dumps({'seconds':time.monotonic()-start,'results':results},ensure_ascii=False,indent=2),encoding='utf-8')
assert results[0]['verdict']=='equivalent',results
print(json.dumps(results,ensure_ascii=False))
