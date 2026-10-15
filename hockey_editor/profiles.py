"""Presenter profiles keep speech, footage and channel assets consistent."""
import json,os
from pathlib import Path

PROFILES={'ru':[('ru_hockey','Хоккей · лонг'),('ru_football','Футбол · лонг'),('ru_hockey_shorts','Хоккей · Shorts')],
          'uz':[('uz_football','Футбол · лонг'),('uz_hockey','Хоккей · лонг'),('uz_combat','Бои · лонг'),('uz_football_shorts','Футбол · Shorts'),('uz_hockey_shorts','Хоккей · Shorts')]}


def kit_path(profile='ru_hockey'):
    if profile=='ru_football':return Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.cache')))/'HockeyAutoEditor'/'asset-kit-ru-football.json'
    if profile=='ru_hockey_shorts':return Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.cache')))/'HockeyAutoEditor'/'asset-kit-ru-shorts.json'
    if profile=='uz_hockey_shorts':return Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.cache')))/'HockeyAutoEditor'/'asset-kit-uz-hockey-shorts.json'
    if profile.endswith('_shorts'):return Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.cache')))/'HockeyAutoEditor'/'asset-kit-uz-shorts.json'
    return Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.cache')))/'HockeyAutoEditor'/('asset-kit-uz-hockey.json' if profile.startswith('uz_hockey') else 'asset-kit-uz-combat.json' if profile=='uz_combat' else 'asset-kit-uz-football.json' if profile.startswith('uz_football') else 'asset-kit.json')


def apply_profile(project,profile):
    if profile not in {p for values in PROFILES.values() for p,_ in values}:raise ValueError('Неизвестный шаблон.')
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
        block.sport='combat' if profile=='uz_combat' else 'football' if 'football' in profile else 'hockey';block.forecast='';block.featured_pairs=[]
        block.archive_pool=[]
        block.language=language;block.events=[];block.edit_plan=None;block.edit_key='';block.card_overrides={};block.source_hint=[];block.asr_lines=[];block.speech_key='';block.speech_cards={}
    if profile=='uz_combat' or any(s.sport=='combat' for s in project.matches):
        for block in project.blocks:block.match_ids=[]
    else:
        for source in project.matches:source.sport='football' if 'football' in profile else 'hockey'
    project.assets={}
    project.asset_folder=''
    try:
        from .material_folder import load_kit
        project.asset_folder,project.assets=load_kit(kit_path(profile))
    except (OSError,ValueError):pass

