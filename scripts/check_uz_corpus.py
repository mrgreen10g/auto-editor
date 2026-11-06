"""Resumable private-corpus ASR audit. Never commit the corpus or its outputs.

Usage: python scripts/check_uz_corpus.py CORPUS OUTPUT [--recognize]
Without --recognize this inventories every pair and evaluates cached transcripts.
Scripts may be paraphrased/abridged: token coverage is NOT recognition accuracy.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import sys
import threading
import time
import traceback
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hockey_editor.folder_import import parse_episode
from hockey_editor.model import Project
from hockey_editor.processing_cache import write_json
from hockey_editor.uz_speech import MODEL_REV, ASR_RECIPE, recognition_prompt


def inventory(root):
    result=[]
    for script in sorted(root.rglob('*.txt')):
        audio=script.with_suffix('.mp3')
        text=script.read_text(encoding='utf-8-sig')
        low=text.casefold()
        sport=('combat' if any(s in low for s in ('ufc','top dog','jangchi')) else
               'hockey' if any(s in low for s in ('nhl','khl','xokkey')) else 'football')
        relative=str(script.relative_to(root))
        result.append(dict(id=hashlib.sha256(relative.encode()).hexdigest()[:12],
                           name=relative,script=str(script),audio=str(audio),
                           profile='uz_'+sport,profile_inferred=True,
                           status='pending' if audio.is_file() else 'missing_audio'))
    return result


def project_for(row):
    intro,blocks,outro=parse_episode(Path(row['script']).read_text(encoding='utf-8-sig'),row['profile'])
    return Project(host=row['audio'],intro=intro,blocks=blocks,outro=outro,profile=row['profile'])


def pcm(audio,target):
    import av
    temp=target.with_suffix('.partial.wav')
    with av.open(str(audio)) as source, wave.open(str(temp),'wb') as dest:
        dest.setnchannels(1);dest.setsampwidth(2);dest.setframerate(16000)
        resampler=av.AudioResampler(format='s16',layout='mono',rate=16000)
        for frame in source.decode(audio=0):
            for converted in resampler.resample(frame):dest.writeframes(converted.to_ndarray().tobytes())
        for converted in resampler.resample(None):dest.writeframes(converted.to_ndarray().tobytes())
    temp.replace(target)


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda:source.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def evaluate(project,segments,duration):
    from hockey_editor.uz_speech import prepare
    if project.profile.startswith('uz_hockey'):
        from hockey_editor.uz_hockey import prepare
        bounds=prepare(project,segments,duration)
    elif project.profile.startswith('uz_combat'):
        from hockey_editor.combat import prepare
        bounds=prepare(project,segments,duration)
    else:bounds=prepare(project,segments,review=True,duration=duration)
    blocks=[project.intro,*project.blocks,project.outro]
    return dict(bounds=bounds,blocks=[dict(title=b.title,kind=b.kind,
                lines=b.asr_lines,cards=b.speech_cards) for b in blocks],
                review_annotations=sum(bool(c.get('needs_review')) for b in blocks for c in b.speech_cards.values()),
                uncertain_lines=sum(bool(l.get('review_reason')) for b in blocks for l in b.asr_lines))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('corpus',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--recognize',action='store_true')
    parser.add_argument('--manifest',type=Path,help='Reviewed inventory, including explicit profile choices')
    parser.add_argument('--limit',type=int)
    args=parser.parse_args();root=args.corpus.resolve();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    rows=json.loads(args.manifest.read_text()) if args.manifest else inventory(root)
    write_json(out/'inventory.json',rows)
    model=None;cancel=threading.Event();done=0;summary=[]
    try:
        for row in rows:
            record=dict(row);folder=out/row['id'];folder.mkdir(exist_ok=True)
            def log(text):
                with (folder/'run.log').open('a',encoding='utf-8') as f:f.write(text+'\n')
                write_json(out/'progress.json',dict(name=row['name'],stage=text,completed=done,total=len(rows)))
            try:
                project=project_for(row)
                record['parsed_blocks']=[b.title for b in project.blocks]
                write_json(folder/'parsed.json',asdict(project))
                if not Path(row['audio']).is_file():
                    record['status']='missing_audio';continue
                import av
                with av.open(row['audio']) as source:duration=source.duration/1e6
                record['duration']=duration
                identity=hashlib.sha256(json.dumps([digest(Path(row['audio'])),MODEL_REV,ASR_RECIPE,recognition_prompt(project)],ensure_ascii=False).encode()).hexdigest()
                cache=folder/identity;cache.mkdir(exist_ok=True)
                refined=cache/'refined.json'
                if not refined.exists() and args.recognize and (args.limit is None or done<args.limit):
                    from hockey_editor.speech_cache import recognize,cpu_threads
                    from hockey_editor.uz_speech import model_path
                    from hockey_editor.uz_refine import refine
                    from faster_whisper import WhisperModel
                    if model is None:
                        model=WhisperModel(str(model_path(cancel,log)),device='cpu',compute_type='int8',cpu_threads=cpu_threads(),local_files_only=True)
                    wav=cache/'voice.wav'
                    if not wav.exists():pcm(Path(row['audio']),wav)
                    started=time.monotonic()
                    vocabulary=recognition_prompt(project)
                    raw=recognize(model,wav,cache/'raw.json','uz',vocabulary,cancel,log,hotwords=vocabulary)
                    result=refine(model,wav,raw,project,cancel,log)
                    if project.profile.startswith('uz_combat'):
                        from hockey_editor.combat import recover_gaps
                        result=recover_gaps(model,wav,result,cancel,log)
                    write_json(refined,result)
                    write_json(cache/'complete.json',dict(elapsed=time.monotonic()-started,model=MODEL_REV,recipe=ASR_RECIPE))
                    done+=1
                if refined.exists():
                    segments=json.loads(refined.read_text(encoding='utf-8'))
                    record['segments']=str(refined);record['status']='recognized'
                    try:
                        metrics=evaluate(project,segments,duration)
                        write_json(folder/'alignment.json',metrics)
                        record.update({k:metrics[k] for k in ('bounds','review_annotations','uncertain_lines')})
                    except Exception as error:record['alignment_error']=str(error)
                else:record['status']='not_recognized'
            except Exception:
                record['status']='error';record['error']=traceback.format_exc()
            finally:
                summary.append(record);write_json(out/'summary.json',summary)
                print(record['name'],record['status'],record.get('review_annotations',''),flush=True)
    finally:
        del model
    return 1 if any(r['status']=='error' for r in summary) else 0


if __name__=='__main__':raise SystemExit(main())
