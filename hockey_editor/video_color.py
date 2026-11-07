"""Convert HDR camera frames before SDR compositing; leave SDR untouched."""
from .media import probe

def sdr_filter(path):
    transfer=probe(path).get('color_transfer','')
    if transfer not in ('arib-std-b67','smpte2084'):return ''
    return ('zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,'
            'tonemap=tonemap=hable:desat=2:peak=10,'
            'zscale=t=bt709:m=bt709:r=limited,format=yuv420p,')
