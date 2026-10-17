r"""
future音频下载器 —— 打包启动器

用途：这个文件被打包成 exe，它本身不包含业务逻辑，
     而是去加载同目录下的 musicdl_gui.py。
好处：以后改功能只改 musicdl_gui.py，不用重新打包 exe。
"""
import os
import sys
import runpy
import traceback


def base_dir():
    """exe 所在目录（打包后）；源码运行时则是本文件所在目录"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def fatal(msg):
    """没有控制台的时候也要让用户看到错误"""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, msg, 'future音频下载器 · 启动失败', 0x10)
    except Exception:
        try:
            print(msg)
        except Exception:
            pass
    sys.exit(1)


BASE = base_dir()
TARGET = os.path.join(BASE, 'musicdl_gui.py')

if not os.path.exists(TARGET):
    fatal('找不到主程序文件：\n\n%s\n\n'
          '请确认 musicdl_gui.py 与 exe 放在同一个文件夹里（不要在 _internal 里找）。' % TARGET)

sys.path.insert(0, BASE)

try:
    runpy.run_path(TARGET, run_name='__main__')
except SystemExit:
    raise
except Exception:
    fatal('程序启动出错：\n\n' + traceback.format_exc()[-1600:])
