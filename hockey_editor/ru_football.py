"""Russian football uses Russian speech/cards and shared football footage."""
from .model import Block

def parse_script(text):
    from .framing import split_full_script
    intro,blocks,outro=split_full_script(text,sport='football')
    return (Block(title='Начало',uid='intro',kind='intro',script=intro,sport='football'),
            [Block(title=t,script=s,sport='football') for t,s in blocks],
            Block(title='Итоги',uid='outro',kind='outro',script=outro,sport='football'))
