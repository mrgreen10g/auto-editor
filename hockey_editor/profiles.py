"""Presenter profiles keep speech, footage and channel assets consistent."""
import json,os
from pathlib import Path


def kit_path(profile='ru_hockey'):
    if profile=='ru_hockey_shorts':return Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.cache')))/'HockeyAutoEditor'/'asset-kit-ru-shorts.json'
    if profile.endswith('_shorts'):return Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.cache')))/'HockeyAutoEditor'/'asset-kit-uz-shorts.json'
    return Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.cache')))/'HockeyAutoEditor'/('asset-kit-uz-hockey.json' if profile=='uz_hockey' else 'asset-kit-uz-combat.json' if profile=='uz_combat' else 'asset-kit-uz-football.json' if profile.startswith('uz_football') else 'asset-kit.json')


def apply_profile(project,profile):
    if profile not in ('ru_hockey','uz_football','uz_combat','uz_hockey','uz_football_shorts','ru_hockey_shorts'):raise ValueError('Неизвестный шаблон.')
    if project.profile==profile:return
    was_short=project.profile.endswith('_shorts')
    if profile.endswith('_shorts'):
        project.settings.width,project.settings.height=1080,1920
        project.settings.wobble=False;project.settings.insert_frequency='high'
        project.full_video=True;project.whole_episode=True
    elif was_short:
        project.settings.width,project.settings.height=1920,1080
    project.profile=profile;project.episode_plan=None;project.episode_key='';project.recording_times=''
    language='uz' if profile.startswith('uz_') else 'ru'
    for block in [project.intro,*project.blocks,project.outro]:
        block.sport='combat' if profile=='uz_combat' else 'hockey' if profile=='uz_hockey' else '';block.forecast='';block.featured_pairs=[]
        block.archive_pool=[]
        block.language=language;block.events=[];block.edit_plan=None;block.edit_key='';block.card_overrides={};block.source_hint=[];block.asr_lines=[];block.speech_key='';block.speech_cards={}
    if profile=='uz_combat' or any(s.sport=='combat' for s in project.matches):
        for block in project.blocks:block.match_ids=[]
    else:
        for source in project.matches:source.sport='football' if profile.startswith('uz_football') else 'hockey'
    project.assets={}
    try:project.assets={k:v for k,v in json.loads(kit_path(profile).read_text(encoding='utf-8')).items() if Path(v).is_file()}
    except (OSError,ValueError):pass

