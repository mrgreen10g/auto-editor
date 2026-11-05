"""Reject strongly evidenced wrong-sport recordings, never low ASR confidence alone."""
import re
from collections import defaultdict


def check_combat_recording(project, segments):
    if not project.profile.startswith('uz_combat') or not segments:
        return
    if segments[-1]['end'] - segments[0]['start'] < 60:
        return
    from .graphics import block_teams
    from .combat import name_position
    from .team_names import football_names
    from .uzbek import norm
    names = [n for b in project.blocks for n in block_teams(b.title)]
    if not names:
        return
    # Even a single expected fighter or explicit combat discussion makes this
    # narrow guard inconclusive. Missing/poorly recognized names are not proof.
    clubs = defaultdict(list)
    football_context = 0
    for s in segments:
        text = s.get('text', '')
        if any(name_position(n, text) is not None for n in names):
            return
        t = norm(text)
        if re.search(r'\b(?:ufc|top\s*dog|jang\w*|raund\w*|nokaut\w*|oktagon\w*)\b', t):
            return
        if re.search(r'\b(?:futbol\w*|gol\w*|penalti\w*|taym\w*)\b', t):
            football_context += 1
        for club in football_names(text):
            clubs[club].append(s['start'])
    repeated = sorted(club for club, times in clubs.items()
                      if len(times) >= 3 and max(times) - min(times) >= 45)
    if len(repeated) >= 3 and football_context >= 4:
        raise ValueError(
            'Похоже, запись и сценарий относятся к разным выпускам: '
            'выбран сценарий боёв, а в речи многократно обсуждаются футбольные команды: '
            + ', '.join(repeated) + '. Проверьте запись ведущего и сценарий. '
            'Совпадение названий файлов не подтверждает совпадение их содержания.')
