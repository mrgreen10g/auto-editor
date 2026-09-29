"""Per-project player and coach names from authored scripts; no sports facts."""
import re
from .script_input import clean_script

def script_names(project):
    text=clean_script('\n'.join(b.script for b in [project.intro,*project.blocks,project.outro]))
    # Two or three capitalized words, never whole narrative or numeric claims.
    values=re.findall(r'\b[A-ZÀ-Þ][a-zà-ÿ]+(?:[ -][A-ZÀ-Þ][a-zà-ÿ]+){1,2}\b',text)
    if project.profile=='uz_football':
        from .football_players import mentioned_names
        values=mentioned_names(text)+values
    return '; '.join(dict.fromkeys(values))
