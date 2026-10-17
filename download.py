# -*- coding: utf-8 -*-
"""
按编号下载上一轮搜索结果中的曲目。
用法：python download.py <编号>
依赖：_last_search.pkl（由 search.py 生成）
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


def main():
    if len(sys.argv) < 2:
        print('usage: python download.py <index>')
        return 1
    idx = int(sys.argv[1]) - 1

    with open(os.path.join(HERE, '_last_search.pkl'), 'rb') as f:
        flat = pickle.load(f)

    if idx < 0 or idx >= len(flat):
        print('index out of range: 1..{}'.format(len(flat)))
        return 1

    target = flat[idx]
    src = target.get('source')
    print('target #{}: {} / {} / {} / {} / {}'.format(
        idx + 1, target.get('song_name'), target.get('singers'),
        target.get('ext'), target.get('file_size'), src))

    from musicdl import musicdl
    client = musicdl.MusicClient(
        music_sources=[src],
        init_music_clients_cfg={src: {'work_dir': SAVEDIR}},
    )
    client.download(song_infos=[target])
    print('download finished')

    print('--- files in downloads ---')
    for root, _, files in os.walk(SAVEDIR):
        for fn in files:
            if fn.endswith(('.pkl',)):
                continue
            p = os.path.join(root, fn)
            print('{}  ({} bytes)'.format(fn, os.path.getsize(p)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
