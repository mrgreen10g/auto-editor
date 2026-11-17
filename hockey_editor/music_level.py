"""A real post-normalization amplitude fader, shared by both render paths."""
import math

def percent_from_db(db):
    return min(100.,max(0.,100*10**((float(db)+16)/20)))

def bed_filter(settings,duration):
    value=float(settings.music_volume)
    if not math.isfinite(value) or not 0<=value<=100:raise ValueError('Громкость музыки должна быть от 0 до 100%.')
    return (f'atrim=duration={duration:.6f},asetpts=PTS-STARTPTS,loudnorm=I=-16:TP=-9:LRA=7,'
            f'aresample=48000,volume={value/100:.8f},afade=t=in:d=1,'
            f'afade=t=out:st={max(0,duration-2):.6f}:d=2')
