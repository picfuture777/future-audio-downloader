# -*- coding: utf-8 -*-
"""
musicdl 搜索脚本（单次）
用法：python search.py "关键字"
产出：
  - _last_search.pkl  本次全部 song_info（供后续按编号下载）
  - _results.md       给用户看的表格
"""
import os
import sys
import pickle

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
SAVEDIR = os.path.join(HERE, 'downloads')
os.makedirs(SAVEDIR, exist_ok=True)

SRCS = [
    'NeteaseMusicClient',
    'QQMusicClient',
    'KugouMusicClient',
    'KuwoMusicClient',
    'MiguMusicClient',
]
PER_SOURCE = 4
KEYWORD = sys.argv[1] if len(sys.argv) > 1 else '许嵩 山水之间'


def main():
    from musicdl import musicdl

    cfg = {s: {'work_dir': SAVEDIR, 'search_size_per_source': PER_SOURCE} for s in SRCS}
    client = musicdl.MusicClient(music_sources=SRCS, init_music_clients_cfg=cfg)
    results = client.search(keyword=KEYWORD)

    flat = []
    for src, items in results.items():
        for it in (items or []):
            flat.append(it)

    with open(os.path.join(HERE, '_last_search.pkl'), 'wb') as f:
        pickle.dump(flat, f)

    lines = []
    lines.append(f'关键字: {KEYWORD}   共 {len(flat)} 条')
    lines.append('')
    lines.append('| 编号 | 歌名 | 歌手 | 格式 | 大小 | 时长 | 来源 |')
    lines.append('|---|---|---|---|---|---|---|')
    for i, it in enumerate(flat, 1):
        lines.append('| {} | {} | {} | {} | {} | {} | {} |'.format(
            i,
            it.get('song_name', ''),
            it.get('singers', ''),
            (it.get('ext') or '').upper(),
            it.get('file_size', ''),
            it.get('duration', ''),
            (it.get('source') or '').replace('MusicClient', ''),
        ))

    with open(os.path.join(HERE, '_results.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print('OK total={}'.format(len(flat)))


if __name__ == '__main__':
    main()
