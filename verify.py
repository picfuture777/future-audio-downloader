# -*- coding: utf-8 -*-
"""
musicdl 链路验证脚本
用途：确认本机网络下哪些音源能搜到、能否真正下载成功。
只做验证，不修改任何系统设置。
"""
import os
import sys
import traceback

# 保证控制台能打印中文
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
KEYWORD = '周杰伦 晴天'
SEARCH_SIZE = 2


def main():
    print('=' * 60)
    print('musicdl 链路验证')
    print('保存目录:', SAVEDIR)
    print('音源:', ', '.join(SRCS))
    print('关键字:', KEYWORD)
    print('=' * 60)

    from musicdl import musicdl

    cfg = {
        s: {'work_dir': SAVEDIR, 'search_size_per_source': SEARCH_SIZE}
        for s in SRCS
    }

    client = musicdl.MusicClient(music_sources=SRCS, init_music_clients_cfg=cfg)

    print('\n[1/2] 开始搜索 ...')
    results = client.search(keyword=KEYWORD)

    total = 0
    for src, items in results.items():
        items = items or []
        total += len(items)
        print(f'  [{src}] {len(items)} 条')
        for it in items[:SEARCH_SIZE]:
            print('      -',
                  it.get('song_name'), '|',
                  it.get('singers'), '|',
                  it.get('file_size'), '|',
                  it.get('ext'), '|',
                  it.get('duration'))
    print(f'  合计 {total} 条结果')

    if total == 0:
        print('\n[结论] 所有音源均未搜到结果 —— 可能是接口失效或网络问题。')
        return 1

    print('\n[2/2] 尝试下载第一条 ...')
    flat = [it for items in results.values() for it in (items or [])]
    target = flat[0]
    print('  目标:', target.get('song_name'), '/', target.get('singers'), '/', target.get('source'))
    try:
        client.download(song_infos=[target])
        print('  下载调用完成')
    except Exception:
        traceback.print_exc()
        print('[结论] 搜索可用，但下载失败 —— 需看上面的报错。')
        return 2

    print('\n[下载目录实际内容]')
    for root, _, files in os.walk(SAVEDIR):
        for f in files:
            p = os.path.join(root, f)
            print(f'  {f}  ({os.path.getsize(p)} bytes)')

    print('\n[结论] 搜索 + 下载链路可用。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
