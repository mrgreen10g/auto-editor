"""Spoken Uzbek NHL/KHL Shorts structure using the shared portrait renderer."""
def parse_script(text):
    from .shorts import parse_script as shared
    from .uz_hockey import classify,bet
    from .alignment import split_script
    intro,blocks,outro=shared(text,sport='hockey')
    for block in [intro,*blocks,outro]:
        block.language='uz';block.sport='hockey'
        if block.kind=='analysis':
            picks=[bet(row) for row in block.script.splitlines() if any(classify(part)[0]=='ПРОГНОЗ' for part in split_script(row))]
            block.forecast=next((v for v in reversed(picks) if v),'')
    intro.featured_pairs=[]
    return intro,blocks,outro
