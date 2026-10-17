# -*- mode: python ; coding: utf-8 -*-
"""
future音频下载器 打包配置（PyInstaller 6.x）

要点：
- onedir 模式（生成文件夹，不是单文件）—— 启动快、误报低
- exe 只当启动器，业务逻辑从 exe 旁边的 musicdl_gui.py 读取
- nodejs_wheel / imageio_ffmpeg / av 带二进制，必须 collect_all
"""
import os

from PyInstaller.utils.hooks import collect_all

# SPECPATH 由 PyInstaller 注入，指向本 spec 文件所在目录。
# 用相对推导而不是写死绝对路径 —— 这样从英文 junction（D:\fa_build）打包时也能正确解析。
_HERE = SPECPATH
_ROOT = os.path.dirname(_HERE)
print('[spec] SPECPATH = %s' % _HERE)
print('[spec] ROOT     = %s' % _ROOT)

datas = []
binaries = []
hiddenimports = [
    'PyQt5.QtMultimedia',
    'PyQt5.QtMultimediaWidgets',
]

# 这些包内含可执行文件或动态库，静态分析抓不到，必须整包收
for pkg in ['imageio_ffmpeg', 'nodejs_wheel', 'nodejs_wheel_binaries', 'musicdl', 'av']:
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
        print('[spec] collected %s: datas=%d binaries=%d hidden=%d'
              % (pkg, len(d), len(b), len(h)))
    except Exception as exc:
        print('[spec] collect_all 跳过 %s: %r' % (pkg, exc))

a = Analysis(
    [os.path.join(_HERE, 'launcher.py')],
    pathex=[_ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy', 'PyQt5.QtWebEngineWidgets'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='future音频下载器',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='future音频下载器',
)
