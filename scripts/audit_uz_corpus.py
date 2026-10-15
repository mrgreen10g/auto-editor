"""Audit a private extracted corpus index; never treat scenarios as ASR truth.

Input JSON rows: episode, path, type, sha256 (from archive inventory).
Outputs private JSON with decode checks and episode-level split proposals.
No data is sent to any service. Requires ffmpeg/ffprobe on PATH.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


def audit(rows):
    groups = {}
    for row in rows:
        groups.setdefault(row['episode'], []).append(row)
    result = []
    # Connected components keep duplicate audio OR scripts out of other splits.
    owners = {}; parent = {name: name for name in groups}
    def root(name):
        while parent[name] != name:
            name = parent[name]
        return name
    for name, files in sorted(groups.items()):
        date = re.match(r'^(\d{1,2}\.\d{1,2})(?:\(|$)', name)
        if date:
            date_key = 'date:'+date.group(1)
            if date_key in owners:
                parent[root(name)] = root(owners[date_key])
            owners[date_key] = name
        for item in files:
            key = item['sha256']
            if key in owners:
                parent[root(name)] = root(owners[key])
            owners[key] = name
    eligible = {root(name) for name, files in groups.items()
                if any(x['type'] == '.txt' for x in files) and any(x['type'] != '.txt' for x in files)}
    ordered = sorted(eligible, key=lambda x: hashlib.sha256(('uz-corpus-v1:'+x).encode()).hexdigest())
    holdout = max(1, round(len(ordered)*.1)) if len(ordered) >= 3 else 0
    splits = {name: ('test' if i < holdout else 'validation' if i < 2*holdout else 'train')
              for i, name in enumerate(ordered)}
    for name, files in sorted(groups.items()):
        row = {'episode': name, 'split': splits.get(root(name), 'unpaired'),
               'reference_status': 'scenario_not_verified_transcript', 'training_eligible': False,
               'audio': [], 'scripts': []}
        for item in files:
            if item['type'] == '.txt':
                row['scripts'].append(item); continue
            entry = dict(item)
            p = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                'format=duration:stream=codec_type,sample_rate,channels', '-of', 'json', item['path']],
                capture_output=True, text=True, timeout=60)
            entry['probe_ok'] = p.returncode == 0
            if p.returncode == 0:
                info = json.loads(p.stdout)
                entry['duration'] = float(info.get('format', {}).get('duration', 0))
                entry['streams'] = info.get('streams', [])
            p = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-xerror', '-i', item['path'],
                '-map', '0:a:0', '-f', 'null', '-'], capture_output=True, text=True, timeout=600)
            entry['decode_ok'] = p.returncode == 0
            if p.returncode: entry['decode_error'] = p.stderr[-2000:]
            row['audio'].append(entry)
        row['paired'] = bool(row['audio'] and row['scripts'])
        result.append(row)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('index', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = audit(json.loads(args.index.read_text(encoding='utf-8')))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    paired = [x for x in result if x['paired']]
    print(json.dumps({'paired_episodes': len(paired),
        'hours': round(sum(a.get('duration', 0) for x in paired for a in x['audio'])/3600, 2),
        'decode_failures': sum(not a['decode_ok'] for x in paired for a in x['audio']),
        'split': {k: sum(x['split'] == k for x in paired) for k in ('train','validation','test')}}, indent=2))


if __name__ == '__main__':
    main()
