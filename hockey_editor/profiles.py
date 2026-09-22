"""Presenter profiles keep speech, footage and channel assets consistent."""
import json,os
from pathlib import Path


def kit_path(profile='ru_hockey'):
    return Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.cache')))/'HockeyAutoEditor'/('asset-kit-uz-combat.json' if profile=='uz_combat' else 'asset-kit-uz-football.json' if profile=='uz_football' else 'asset-kit.json')


def apply_profile(project,profile):
    if profile not in ('ru_hockey','uz_football','uz_combat'):raise ValueError('Неизвестный шаблон.')
    if project.profile==profile:return
    project.profile=profile;project.episode_plan=None;project.episode_key='';project.recording_times=''
    language='uz' if profile.startswith('uz_') else 'ru'
    for block in [project.intro,*project.blocks,project.outro]:
        block.sport='combat' if profile=='uz_combat' else '';block.forecast='';block.featured_pairs=[]
        block.language=language;block.events=[];block.edit_plan=None;block.edit_key='';block.card_overrides={};block.source_hint=[];block.asr_lines=[];block.speech_key='';block.speech_cards={}
    if profile=='uz_combat' or any(s.sport=='combat' for s in project.matches):
        for block in project.blocks:block.match_ids=[]
    else:
        for source in project.matches:source.sport='football' if language=='uz' else 'hockey'
    project.assets={}
    try:project.assets={k:v for k,v in json.loads(kit_path(profile).read_text(encoding='utf-8')).items() if Path(v).is_file()}
    except (OSError,ValueError):pass

