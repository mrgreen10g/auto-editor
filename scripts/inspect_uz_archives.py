"""Read private RAR corpus headers and TXT scripts without extracting audio.

Run locally; output contains filenames and structural counts, never transcripts.
Requires system libarchive. Does not upload data or invoke speech recognition.
"""
import argparse
import ctypes as c
import ctypes.util
import json
from pathlib import PurePosixPath


def entries(path):
    lib = c.CDLL(ctypes.util.find_library('archive'))
    for name, restype, args in [
        ('archive_read_new', c.c_void_p, []),
        ('archive_read_support_filter_all', c.c_int, [c.c_void_p]),
        ('archive_read_support_format_all', c.c_int, [c.c_void_p]),
        ('archive_read_open_filename', c.c_int, [c.c_void_p,c.c_char_p,c.c_size_t]),
        ('archive_read_next_header', c.c_int, [c.c_void_p,c.POINTER(c.c_void_p)]),
        ('archive_entry_pathname', c.c_char_p, [c.c_void_p]),
        ('archive_read_data', c.c_ssize_t, [c.c_void_p,c.c_void_p,c.c_size_t]),
        ('archive_read_free', c.c_int, [c.c_void_p]),
    ]:
        fn = getattr(lib, name); fn.restype = restype; fn.argtypes = args
    archive = lib.archive_read_new()
    try:
        lib.archive_read_support_filter_all(archive)
        lib.archive_read_support_format_all(archive)
        if lib.archive_read_open_filename(archive, str(path).encode(), 65536) != 0:
            raise ValueError('Cannot open archive: '+str(path))
        entry = c.c_void_p()
        while True:
            status = lib.archive_read_next_header(archive, c.byref(entry))
            if status == 1: break
            if status < 0: raise ValueError('Corrupt archive: '+str(path))
            name = lib.archive_entry_pathname(entry).decode('utf-8')
            data = bytearray()
            if name.lower().endswith('.txt'):
                buf = c.create_string_buffer(65536)
                while True:
                    n = lib.archive_read_data(archive, buf, len(buf))
                    if n < 0: raise ValueError('Cannot read script: '+name)
                    if not n: break
                    data.extend(buf.raw[:n])
                    if len(data) > 4_000_000: raise ValueError('Oversized script')
            yield name, bytes(data)
    finally:
        lib.archive_read_free(archive)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('archives', nargs='+')
    args = parser.parse_args()
    from hockey_editor.uz_structure import parse
    scripts = {}; audio = set()
    for path in args.archives:
        for name, data in entries(path):
            p = PurePosixPath(name.replace('\\', '/'))
            if p.suffix.lower() in ('.mp3', '.wav', '.m4a', '.flac'): audio.add(p.stem)
            if p.suffix.lower() == '.txt': scripts[p.stem] = data.decode('utf-8-sig')
    result = []
    for stem in sorted(audio):
        text = scripts.get(stem)
        if text is None:
            result.append({'episode':stem, 'error':'missing script'}); continue
        # Structure is sport independent; no inferred sport label is ground truth.
        try:
            a, b, z = parse(text, 'football')
            result.append({'episode':stem, 'blocks':len(b), 'intro':bool(a.script), 'outro':bool(z.script)})
        except ValueError as e: result.append({'episode':stem, 'error':str(e)})
    print(json.dumps({'audio_count':len(audio), 'script_count':len(scripts), 'episodes':result}, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
