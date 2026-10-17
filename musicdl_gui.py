# -*- coding: utf-8 -*-
"""
future音频下载器 · 中文图形界面（future chen作品）

功能：
  1. 输入歌名搜索（网易云 / QQ / 酷狗 / 酷我 / 咪咕 五源并发）
  2. 格式筛选：全部 / 只要无损 / 只要 MP3
  3. 选择下载目录（文件统一命名「歌手 - 歌名.扩展名」，不再有乱七八糟的时间戳目录）
  4. 试听：先下到临时目录播放，满意再「保存」，不满意直接「丢弃」——避免下错版本

依赖：musicdl >= 2.14、PyQt5、requests
"""
import os
import sys
import time
import shutil
import traceback

import requests
import threading

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QUrl, QTimer

# ---------------------------------------------------------------------------
# Qt 平台插件路径修复（必须在创建 QApplication 之前执行）
#
# 背景：项目路径含中文时，Qt 内部用 ANSI 接口解析路径，中文会变成 "?"，
# 于是启动时报 “Could not find the Qt platform plugin "windows" in ""” 并闪退。
# 这里改用 PyQt5 的 unicode 接口显式登记插件目录，绕开 ANSI 解析。
# ---------------------------------------------------------------------------
try:
    import PyQt5 as _PyQt5
    from PyQt5.QtCore import QCoreApplication as _QCoreApplication
    _qt_plugins_dir = os.path.join(os.path.dirname(_PyQt5.__file__), 'Qt5', 'plugins')
    if os.path.isdir(_qt_plugins_dir):
        _QCoreApplication.addLibraryPath(_qt_plugins_dir)
        os.environ.setdefault('QT_PLUGIN_PATH', _qt_plugins_dir)
        os.environ.setdefault('QT_QPA_PLATFORM_PLUGIN_PATH',
                              os.path.join(_qt_plugins_dir, 'platforms'))
except Exception:
    pass

from PyQt5.QtGui import QIcon, QColor, QFont
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QLineEdit, QPushButton, QCheckBox,
    QComboBox, QTableWidget, QTableWidgetItem, QAbstractItemView, QHBoxLayout,
    QVBoxLayout, QFileDialog, QProgressBar, QMessageBox, QHeaderView, QSlider,
    QFrame, QSpinBox, QToolButton, QMenu, QWidgetAction, QGraphicsDropShadowEffect,
    QDialog, QTextBrowser,
)

try:
    from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
    HAS_MEDIA = True
except Exception:                                    # 极少数环境缺多媒体模块
    HAS_MEDIA = False

try:
    from pathvalidate import sanitize_filename
except Exception:
    def sanitize_filename(name, **_):
        for ch in '\\/:*?"<>|':
            name = name.replace(ch, '_')
        return name


# ---------------------------------------------------------------- 常量
APP_TITLE = 'future音频下载器'

# 打包成 exe 之后，__file__ 指向的是 exe 内部（_internal 里），不能用来定位用户目录。
# 所以优先取 exe 自身所在目录，这样 _cache 会落在 exe 旁边，既方便查看也便于持久化。
if getattr(sys, 'frozen', False):
    HERE = os.path.dirname(os.path.abspath(sys.executable))
else:
    HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(HERE, '_cache')          # 搜索缓存 + 试听临时文件
PREVIEW_DIR = os.path.join(CACHE_DIR, 'preview')

# 常驻勾选的四个主力源
SOURCES_MAIN = [
    ('NeteaseMusicClient', '网易云'),
    ('QQMusicClient', 'QQ音乐'),
    ('KugouMusicClient', '酷狗'),
    ('KuwoMusicClient', '酷我'),
]

# 「更多音源」下拉的分组结构（默认全部不勾）
SOURCE_GROUPS = [
    ('音乐平台', [
        ('MiguMusicClient', '咪咕'),
        ('QianqianMusicClient', '千千音乐'),
        ('SodaMusicClient', '汽水音乐'),
        ('BilibiliMusicClient', 'B站'),
        ('BodianMusicClient', '波点'),
        ('FiveSingMusicClient', '5SING'),
        ('StreetVoiceMusicClient', '街声'),
        ('MOOVMusicClient', '摩音符'),
    ]),
    ('有声书 / 电台', [
        ('XimalayaMusicClient', '喜马拉雅'),
        ('LRTSMusicClient', '懒人听书'),
        ('LizhiMusicClient', '荔枝FM'),
        ('QingtingMusicClient', '蜻蜓FM'),
        ('ITunesMusicClient', '苹果播客'),
    ]),
    ('不稳定音源', [
        ('JBSouMusicClient', '煎饼搜'),
        ('GDStudioMusicClient', 'GD音乐台'),
        ('TuneHubMusicClient', 'TuneHub音乐'),
        ('XiaoBaiMusicClient', '小白音乐'),
        ('MyFreeMP3MusicClient', 'MyFreeMP3'),
        ('MP3JuiceMusicClient', 'MP3Juice'),
        ('BuguyyMusicClient', '布谷音乐'),
        ('FangpiMusicClient', '放屁音乐'),
        ('FiveSongMusicClient', '5Song无损'),
        ('GequbaoMusicClient', '歌曲宝'),
        ('GequhaiMusicClient', '歌曲海'),
        ('GequkeMusicClient', '歌曲客'),
        ('KKWSMusicClient', '开开无损'),
        ('LeedodoMusicClient', '乐多多轻音乐'),
        ('MituMusicClient', '米兔音乐'),
        ('MGMP3MusicClient', '木瓜音乐'),
        ('SgogoMusicClient', '搜歌网'),
        ('TwoT58MusicClient', '爱听音乐网'),
        ('XiagebaMusicClient', '下歌吧'),
        ('XMFWAVMusicClient', '小蜜蜂音乐网'),
        ('YinyuedaoMusicClient', '音乐岛'),
        ('YinyuekuMusicClient', '音乐库'),
        ('HTQYYMusicClient', '好听轻音乐网'),
        ('HeishanMusicClient', '黑山音乐'),
    ]),
]
# 展平版本，便于遍历
SOURCES_MORE = [item for _g, _items in SOURCE_GROUPS for item in _items]

# 实测耗时备注（2026-10-16 实测，关键字「许嵩 山水之间」每源 2 条）
SOURCE_NOTES = {
    'MiguMusicClient': '约 3 秒',
    'QianqianMusicClient': '约 3 秒',
    'SodaMusicClient': '约 5 秒',
    'BilibiliMusicClient': '约 4 秒',
    'BodianMusicClient': '约 4 秒',
    'FiveSingMusicClient': '约 3 秒',
    'StreetVoiceMusicClient': '约 4 秒',
    'MOOVMusicClient': '3.5 分钟且无结果',
    'XimalayaMusicClient': '约 25 秒',
    'LRTSMusicClient': '无结果',
    'LizhiMusicClient': '约 27 秒',
    'QingtingMusicClient': '约 26 秒',
    'ITunesMusicClient': '5 分钟以上',
}
LOSSLESS_EXTS = {'flac', 'wav', 'alac', 'ape', 'wv', 'tta', 'dsf', 'dff'}

# 内置播放器（Windows Media Foundation）放不了的格式，试听时先转成 MP3 再播
# 实测：mp3 可直接播放（state=Playing）；flac 会报 ResourceError
NEED_CONVERT_EXTS = {'flac', 'ape', 'wv', 'tta', 'dsf', 'dff', 'alac',
                     'ogg', 'aif', 'aiff', 'opus', 'wma', 'mka'}

FILTER_ALL = '全部格式'
FILTER_LOSSLESS = '只要无损'
FILTER_MP3 = '只要 MP3'

# 使用说明：优先读程序目录下的「使用说明.txt」，读不到才用这段内置文本。
# 这样改 txt 就能立刻生效，不用重新打包。
HELP_TEXT_FALLBACK = """future音频下载器
future chen作品

使用小技巧
1. 想要小体积 → 勾「下载后转成 MP3」，30MB 的无损能压到 10MB 左右
2. 只想要 MP3 → 格式筛成「只要 MP3」，各源提供的格式不同，一筛就出来
3. 想要无损音质 → 格式筛成「只要无损」，FLAC 会标成绿色
4. 想让搜索更快 → 只勾常用源，别碰「不稳定音源」和苹果播客（慢且常失效）
   · 实测最快的源（3～5 秒）：咪咕、千千音乐、汽水音乐、B站、波点、5SING、街声
   · 中等（约 25 秒）：喜马拉雅、荔枝FM、蜻蜓FM
   · 很慢（3 分钟以上）：摩音符、苹果播客
5. 想比较音质 → 看「大小」列，时长相同的情况下体积越大码率越高
6. 要歌词 → 下载前先在「歌词」列把这首打上勾，下载时会自动带上
7. 搜不到想要的歌 → 试着只输歌名不加歌手，或多勾几个音源（同名翻唱版本很多）
8. 文件名太长显示不全 → 鼠标悬停在歌名上可以看完整名称"""

# 设计 token：颜色统一在这里取，改色只改这一处
#   PRIMARY #378ADD / HOVER #4A94E3 / PRESS #2E76BE / SOFT #E6F1FB
#   TEXT_MAIN #22304A   TEXT_BODY #3A4A62   TEXT_MUTED #64748B   TEXT_FAINT #9AA6B6
#   SUCCESS #2E7D5B（无损标记）   DANGER #B03A36
# 间距一律走 8pt 网格：4 / 8 / 12 / 16 / 24
STYLE = """
QWidget {
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 13px;
    color: #2E3A4D;
}
QMainWindow, QWidget#root {
    background: qradialgradient(cx:0.22, cy:0.06, radius:1.15,
                stop:0 #FCFDFF, stop:0.45 #EDF3FB, stop:1 #D5E3F5);
}
QFrame#card {
    background: rgba(255, 255, 255, 160);
    border: 1px solid rgba(255, 255, 255, 205);
    border-radius: 18px;
}
QLabel#hint { color: #64748B; }
QLabel#title { font-size: 15px; font-weight: 500; color: #22304A; }

QLineEdit, QSpinBox, QComboBox {
    background: rgba(255, 255, 255, 215);
    border: 1px solid rgba(178, 199, 224, 130);
    border-radius: 10px;
    padding: 7px 12px;
    min-height: 20px;
    color: #3A4A62;
    selection-background-color: #378ADD;
    selection-color: #ffffff;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid rgba(55, 138, 221, 160);
    background: rgba(255, 255, 255, 245);
}
QComboBox::drop-down { border: none; width: 24px; }
QSpinBox::up-button, QSpinBox::down-button {
    width: 20px;
    border: none;
    background: transparent;
}
QSpinBox::up-arrow { image: url(__ARROW_UP__); }
QSpinBox::down-arrow { image: url(__ARROW_DOWN__); }
QComboBox QAbstractItemView {
    background: #ffffff;
    border: 1px solid rgba(178, 199, 224, 140);
    border-radius: 10px;
    padding: 4px;
    outline: none;
    selection-background-color: #E6F1FB;
    selection-color: #2E3A4D;
}

QPushButton {
    background: rgba(255, 255, 255, 205);
    border: 1px solid rgba(178, 199, 224, 140);
    border-radius: 10px;
    padding: 7px 16px;
    min-height: 20px;
    color: #3A4A62;
}
QPushButton:hover {
    background: rgba(255, 255, 255, 248);
    border: 1px solid rgba(55, 138, 221, 120);
    color: #2E3A4D;
}
QPushButton:pressed { background: rgba(230, 241, 251, 235); }
QPushButton:disabled {
    color: #B6BFCB;
    background: rgba(255, 255, 255, 130);
    border: 1px solid rgba(200, 212, 230, 90);
}
QPushButton#primary {
    background: #378ADD;
    border: 1px solid rgba(55, 138, 221, 210);
    color: #ffffff;
    font-weight: 500;
}
QPushButton#primary:hover { background: #4A94E3; }
QPushButton#primary:pressed { background: #2E76BE; }
QPushButton#primary:disabled {
    background: rgba(55, 138, 221, 95);
    border: 1px solid transparent;
    color: #F2F6FB;
}
QPushButton#danger:hover {
    background: rgba(252, 235, 235, 235);
    border: 1px solid rgba(226, 75, 74, 130);
    color: #A32D2D;
}

QToolButton {
    background: rgba(255, 255, 255, 205);
    border: 1px solid rgba(178, 199, 224, 140);
    border-radius: 10px;
    padding: 7px 12px;
    color: #3A4A62;
}
QToolButton:hover {
    background: rgba(255, 255, 255, 248);
    border: 1px solid rgba(55, 138, 221, 120);
}
QToolButton::menu-indicator { image: none; width: 0px; }

QMenu {
    background: rgba(255, 255, 255, 252);
    border: 1px solid rgba(178, 199, 224, 140);
    border-radius: 12px;
    padding: 6px;
}
QMenu::item { padding: 5px 8px; border-radius: 8px; }
QMenu::item:selected { background: #E6F1FB; }
QMenu::separator { height: 1px; background: rgba(178, 199, 224, 95); margin: 5px 8px; }

QCheckBox { spacing: 6px; color: #3A4A62; background: transparent; }
QCheckBox::indicator {
    width: 15px; height: 15px;
    border: 1px solid rgba(150, 175, 205, 180);
    border-radius: 4px;
    background: rgba(255, 255, 255, 225);
}
QCheckBox::indicator:hover { border: 1px solid rgba(55, 138, 221, 160); }
QCheckBox::indicator:checked {
    background: #378ADD;
    border: 1px solid #378ADD;
    image: url(__CHECK_ICON__);
}

QTableWidget {
    background: #FFFFFF;
    border: 1px solid rgba(255, 255, 255, 205);
    border-radius: 18px;
    gridline-color: transparent;
    outline: none;
}
QTableWidget::item { padding: 10px 8px; border: none; color: #64748B; background: transparent; }
QTableWidget::item:hover { background: rgba(240, 246, 253, 210); }
QTableWidget::item:selected { background: rgba(212, 231, 250, 225); color: #22304A; }
QHeaderView { background: transparent; border: none; }
QHeaderView::section {
    background: rgba(255, 255, 255, 120);
    color: #64748B;
    padding: 11px 8px;
    border: none;
    border-bottom: 1px solid rgba(178, 199, 224, 110);
    font-weight: 400;
}
QHeaderView::section:first { border-top-left-radius: 18px; }
QHeaderView::section:last { border-top-right-radius: 18px; }
QTableCornerButton::section { background: transparent; border: none; }

QProgressBar {
    background: rgba(219, 228, 240, 160);
    border: none;
    border-radius: 7px;
    height: 14px;
    text-align: center;
    color: #6B7A8F;
    font-size: 11px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #63A6E9, stop:1 #378ADD);
    border-radius: 7px;
}

QSlider::groove:horizontal { height: 4px; background: rgba(200, 214, 232, 160); border-radius: 2px; }
QSlider::sub-page:horizontal { background: #7FB3E8; border-radius: 2px; }
QSlider::handle:horizontal { image: url(__DOT__); margin: -6px 0; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 4px 2px 4px 0; }
QScrollBar::handle:vertical { background: rgba(160, 180, 205, 135); border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: rgba(120, 145, 180, 175); }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0 4px 2px 4px; }
QScrollBar::handle:horizontal { background: rgba(160, 180, 205, 135); border-radius: 4px; min-width: 30px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }

QDialog { background: #F5F8FC; }
QTextBrowser {
    background: #FFFFFF;
    border: 1px solid rgba(203, 220, 240, 0.8);
    border-radius: 14px;
    padding: 14px 16px;
}
"""


# ---------------------------------------------------------------- 音频转码
def convert_to_mp3(src_path, dst_path, bitrate='320k'):
    """用 imageio-ffmpeg 自带的 ffmpeg 把任意音频转成 MP3（不依赖系统安装 ffmpeg）"""
    import subprocess
    import imageio_ffmpeg
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [exe, '-y', '-hide_banner', '-loglevel', 'error',
           '-i', src_path, '-b:a', bitrate, dst_path]
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          encoding='utf-8', errors='replace', timeout=900)
    if proc.returncode != 0 or not os.path.exists(dst_path) or os.path.getsize(dst_path) < 1024:
        raise RuntimeError('ffmpeg 转码失败：%s' % (proc.stderr or '')[:200])
    return dst_path


# ---------------------------------------------------------------- 界面小图标
def build_ui_icons():
    """
    用代码画出界面需要的小图标（对勾 / 上下箭头 / 圆点），存到临时目录。
    QSS 画不出这些形状（Qt 既不支持 CSS 的 border 三角技巧，也没有对勾字符），
    只能给 image: url(...) 提供真实图片。存临时目录是因为项目路径含中文时
    QSS 解析中文 url 有失败风险，临时目录是纯 ASCII 路径。
    返回 {样式表占位符: 图片路径}。
    """
    import tempfile
    from PyQt5.QtGui import QImage, QPainter, QPen, QColor
    from PyQt5.QtCore import Qt, QPointF, QRectF

    out = {}
    try:
        d = os.path.join(tempfile.gettempdir(), 'future_audio_ui')
        os.makedirs(d, exist_ok=True)
    except Exception:
        return out

    def paint(name, w, h, draw):
        """画一张透明底 PNG；无论成败都保证 QPainter 正确收尾"""
        try:
            img = QImage(w, h, QImage.Format_ARGB32)
            img.fill(Qt.transparent)
            pa = QPainter(img)
            try:
                pa.setRenderHint(QPainter.Antialiasing)
                draw(pa)
            finally:
                pa.end()
            path = os.path.join(d, name)
            img.save(path)
            return path.replace('\\', '/')
        except Exception:
            return None

    def draw_check(pa):
        pen = QPen(QColor(255, 255, 255), 2.2)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        pa.setPen(pen)
        pa.drawLine(QPointF(3.6, 8.4), QPointF(6.6, 11.4))
        pa.drawLine(QPointF(6.6, 11.4), QPointF(12.4, 4.8))

    def draw_up(pa):
        pen = QPen(QColor(120, 140, 165), 1.8)
        pen.setCapStyle(Qt.RoundCap)
        pa.setPen(pen)
        pa.drawLine(QPointF(1.2, 4.8), QPointF(4.5, 1.2))
        pa.drawLine(QPointF(4.5, 1.2), QPointF(7.8, 4.8))

    def draw_down(pa):
        pen = QPen(QColor(120, 140, 165), 1.8)
        pen.setCapStyle(Qt.RoundCap)
        pa.setPen(pen)
        pa.drawLine(QPointF(1.2, 1.2), QPointF(4.5, 4.8))
        pa.drawLine(QPointF(4.5, 4.8), QPointF(7.8, 1.2))

    def draw_dot(pa):
        pa.setPen(Qt.NoPen)
        pa.setBrush(QColor(55, 138, 221))
        pa.drawEllipse(QRectF(1.0, 1.0, 12.0, 12.0))

    for placeholder, fn, size, filename in [
        ('__CHECK_ICON__', draw_check, (16, 16), 'check.png'),
        ('__ARROW_UP__', draw_up, (9, 6), 'arrow_up.png'),
        ('__ARROW_DOWN__', draw_down, (9, 6), 'arrow_down.png'),
        ('__DOT__', draw_dot, (14, 14), 'dot.png'),
    ]:
        p = paint(filename, size[0], size[1], fn)
        if p:
            out[placeholder] = p

    return out


# ---------------------------------------------------------------- 工作线程
class ConvertThread(QThread):
    """后台把音频转成 MP3（试听与保存共用）。gen 用于丢弃过期任务的信号。"""
    ok = pyqtSignal(str)
    fail = pyqtSignal(str)

    def __init__(self, src, dst, gen=0, bitrate='192k'):
        super().__init__()
        self.src = src
        self.dst = dst
        self.gen = gen
        self.bitrate = bitrate

    def run(self):
        try:
            convert_to_mp3(self.src, self.dst, self.bitrate)
            self.ok.emit(self.dst)
        except Exception as err:
            self.fail.emit(str(err))


class SearchThread(QThread):
    """后台搜索：每个源独立并发，谁先返回就先报给界面；超时的源直接跳过不再等"""
    TIMEOUT = 45.0                                    # 单轮搜索最长等待（秒）
    partial = pyqtSignal(str, object, object, str)    # (源名, [SongInfo], client, 备注)
    done = pyqtSignal(float)                          # 总耗时（秒）
    fail = pyqtSignal(str)

    def __init__(self, keyword, sources, per_source, cache_dir):
        super().__init__()
        self.keyword = keyword
        self.sources = sources
        self.per_source = per_source
        self.cache_dir = cache_dir
        self._stop = False

    def abort(self):
        self._stop = True

    def run(self):
        t0 = time.time()
        try:
            from musicdl import musicdl
        except Exception as err:
            self.fail.emit('依赖加载失败：%s' % err)
            return

        cfg = {s: {'work_dir': self.cache_dir,
                   'search_size_per_source': self.per_source,
                   'disable_print': True} for s in self.sources}

        def one(src):
            if self._stop:
                return src, [], None, ''
            try:
                client = musicdl.MusicClient(music_sources=[src],
                                             init_music_clients_cfg=cfg)
                results = client.search(keyword=self.keyword)
                items = []
                for lst in (results or {}).values():
                    items.extend(lst or [])
                return src, items, client, ''
            except Exception as err:
                return src, [], None, 'error: %s' % err

        # 用 daemon 线程并发：某个源卡死也不会拖住进程退出
        # （ThreadPoolExecutor 的工作线程是非 daemon，会在退出时被 join，反被慢源拖住）
        lock = threading.Lock()
        finished = {}                     # src -> (items, client, note)

        def worker(src):
            try:
                _s, items, client, note = one(src)
            except Exception as err:
                items, client, note = [], None, 'error: %s' % err
            with lock:
                finished[src] = (items, client, note)

        for s in self.sources:
            threading.Thread(target=worker, args=(s,), daemon=True).start()

        reported = set()
        deadline = time.time() + self.TIMEOUT
        while len(reported) < len(self.sources) and not self._stop:
            if time.time() >= deadline:
                break
            time.sleep(0.15)
            with lock:
                ready = [s for s in self.sources
                         if s in finished and s not in reported]
                for src in ready:
                    items, client, note = finished.pop(src)
                    reported.add(src)
                    self.partial.emit(src, items, client, note)

        # 到点还没回来的 → 判定超时，直接跳过（后台线程仍在跑，但界面不再等它）
        if not self._stop:
            for src in self.sources:
                if src not in reported:
                    self.partial.emit(src, [], None, 'timeout')
            self.done.emit(time.time() - t0)


class DownloadThread(QThread):
    """流式下载，带进度；可随时中止"""
    tick = pyqtSignal(int, int)              # (已下载字节, 总字节)
    ok = pyqtSignal(str, str)                # (保存路径, 提示信息)
    fail = pyqtSignal(str)

    def __init__(self, url, headers, dest_path, label='', to_mp3=False):
        super().__init__()
        self.url = url
        self.headers = headers or {}
        self.dest_path = dest_path
        self.label = label
        self.to_mp3 = to_mp3
        self._abort = False

    def abort(self):
        self._abort = True

    def run(self):
        tmp = self.dest_path + '.part'
        try:
            os.makedirs(os.path.dirname(self.dest_path), exist_ok=True)
            total, done = 0, 0
            with requests.get(self.url, headers=self.headers, stream=True,
                              verify=False, timeout=(15, 60)) as resp:
                resp.raise_for_status()
                try:
                    total = int(resp.headers.get('content-length') or 0)
                except Exception:
                    total = 0
                with open(tmp, 'wb') as fp:
                    for chunk in resp.iter_content(chunk_size=64 * 1024):
                        if self._abort:
                            raise RuntimeError('已取消')
                        if not chunk:
                            continue
                        fp.write(chunk)
                        done += len(chunk)
                        self.tick.emit(done, total)
            if self._abort:
                raise RuntimeError('已取消')
            os.replace(tmp, self.dest_path)
            # 需要转 MP3 且原文件不是 mp3 时，下载完成后就地转码
            final, note = self.dest_path, ''
            if self.to_mp3 and not final.lower().endswith('.mp3'):
                try:
                    mp3_path = os.path.splitext(final)[0] + '.mp3'
                    convert_to_mp3(final, mp3_path)
                    os.remove(final)
                    final, note = mp3_path, '（已转为 MP3）'
                except Exception as err:
                    note = '（转 MP3 失败，已保留原文件：%s）' % err
            self.ok.emit(final, self.label + note)
        except Exception as err:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass
            self.fail.emit(str(err))


# ---------------------------------------------------------------- 主窗口
class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1220, 760)
        icon_path = os.path.join(HERE, 'gui', 'icon.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        os.makedirs(PREVIEW_DIR, exist_ok=True)

        # 状态
        self.client = None
        self.clients = {}              # 每个源各自的 client（用于取下载请求头）
        self.all_items = []            # 全部 SongInfo
        self._pending = set()          # 本轮尚未返回的源
        self.lyric_checked = set()     # 勾选了「下载歌词」的结果下标
        self._dl_idx = -1              # 当前下载对应的结果下标
        self.search_thread = None
        self.dl_thread = None
        self.preview_path = None       # 试听用的临时文件
        self.preview_idx = -1          # 试听文件对应的结果下标
        self.player = None
        self._media_warned = False
        self._preview_gen = 0          # 试听请求代次：用来丢弃上一次试听的迟到信号
        self.preview_orig = None       # 试听时下载的原始文件（保存时以它为准）
        self.preview_mp3 = None        # 试听时为兼容播放器转出来的 MP3
        self.cv_thread = None          # 转码线程
        self._t0 = 0.0

        # 启动时清掉上次会话残留的试听缓存文件
        try:
            os.makedirs(PREVIEW_DIR, exist_ok=True)
            for _fn in os.listdir(PREVIEW_DIR):
                try:
                    os.remove(os.path.join(PREVIEW_DIR, _fn))
                except Exception:
                    pass
        except Exception:
            pass

        # 搜索计时器：让用户看到程序确实在跑，而不是卡死
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._tick_search)

        self._build_ui()

    # ------------------------------------------------------------ UI
    @staticmethod
    def _apply_shadow(widget, blur=36, dy=9, alpha=55):
        """给卡片挂一层柔和的弥散阴影。
        Qt 样式表不支持 box-shadow，只能用图形效果替代；只给卡片用，
        结果表绝对不能挂（会强制离屏渲染，滚动明显卡顿）。"""
        try:
            eff = QGraphicsDropShadowEffect(widget)
            eff.setBlurRadius(blur)
            eff.setOffset(0, dy)
            eff.setColor(QColor(52, 120, 200, alpha))
            widget.setGraphicsEffect(eff)
        except Exception:
            pass

    def _build_ui(self):
        root = QWidget()
        root.setObjectName('root')
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        # ---- 左上角标题行
        title_row = QHBoxLayout()
        title_row.setContentsMargins(2, 0, 0, 0)
        title_row.setSpacing(8)
        lbl_title = QLabel('future音频下载器')
        lbl_title.setObjectName('title')
        title_row.addWidget(lbl_title, 0, Qt.AlignBottom)
        lbl_sub = QLabel('future chen作品')
        lbl_sub.setStyleSheet('color: #9aa0a6; font-size: 11px;')
        title_row.addWidget(lbl_sub, 0, Qt.AlignBottom)
        title_row.addStretch(1)
        outer.addLayout(title_row)

        # ---- 搜索卡片
        card = QFrame(); card.setObjectName('card')
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(16, 12, 16, 12)
        card_lay.setSpacing(12)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel('歌名 / 歌手：'))
        self.edit_keyword = QLineEdit()
        self.edit_keyword.setPlaceholderText('例如：许嵩 山水之间     ——  回车即可搜索')
        self.edit_keyword.returnPressed.connect(self.do_search)
        row1.addWidget(self.edit_keyword, 1)
        self.btn_search = QPushButton('搜索')
        self.btn_search.setObjectName('primary')
        self.btn_search.setMinimumWidth(90)
        self.btn_search.clicked.connect(self.do_search)
        row1.addWidget(self.btn_search)
        card_lay.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel('音源：'))
        self.src_boxes = []
        for cls, cn in SOURCES_MAIN:
            cb = QCheckBox(cn)
            cb.setChecked(True)                       # 默认只勾这四个
            cb.setProperty('cls', cls)
            self.src_boxes.append(cb)
            row2.addWidget(cb)

        # 「更多音源」下拉：按分组的子菜单，每项自带复选框，可多选，点选后菜单不关闭
        self.more_boxes = []
        self.btn_more = QToolButton()
        self.btn_more.setText('更多音源 ▾')
        self.btn_more.setPopupMode(QToolButton.InstantPopup)
        more_menu = QMenu(self.btn_more)
        for group_name, items in SOURCE_GROUPS:
            sub = more_menu.addMenu('%s（%d）' % (group_name, len(items)))
            for cls, cn in items:
                cb = QCheckBox(cn)
                cb.setProperty('cls', cls)
                cb.setToolTip(SOURCE_NOTES.get(cls, ''))
                cb.stateChanged.connect(self._update_more_text)
                holder = QWidget()
                hl = QHBoxLayout(holder)
                hl.setContentsMargins(12, 2, 22, 2)
                hl.addWidget(cb)
                hl.addStretch(1)
                note = QLabel(SOURCE_NOTES.get(cls, ''))
                note.setStyleSheet('color:#9aa0a6; font-size:11px;')
                hl.addWidget(note)
                act = QWidgetAction(sub)
                act.setDefaultWidget(holder)
                sub.addAction(act)
                self.more_boxes.append(cb)
        self.btn_more.setMenu(more_menu)
        row2.addSpacing(8)
        row2.addWidget(self.btn_more)

        row2.addSpacing(16)
        row2.addWidget(QLabel('格式：'))
        self.combo_filter = QComboBox()
        self.combo_filter.addItems([FILTER_ALL, FILTER_LOSSLESS, FILTER_MP3])
        self.combo_filter.setFixedWidth(110)
        self.combo_filter.currentIndexChanged.connect(self.render_table)
        row2.addWidget(self.combo_filter)

        row2.addSpacing(16)
        row2.addWidget(QLabel('每源条数：'))
        self.spin_size = QSpinBox()
        self.spin_size.setRange(1, 20)
        self.spin_size.setValue(3)
        self.spin_size.setFixedWidth(60)
        row2.addWidget(self.spin_size)

        btn_help = QPushButton('使用说明')
        btn_help.setToolTip('查看使用小技巧')
        btn_help.setCursor(Qt.PointingHandCursor)
        btn_help.clicked.connect(self.show_help)
        row2.addSpacing(8)
        row2.addWidget(btn_help)

        row2.addStretch(1)
        card_lay.addLayout(row2)
        self._apply_shadow(card)
        outer.addWidget(card)

        # ---- 结果表
        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels(
            ['歌名', '歌手', '格式', '大小', '时长', '专辑', '来源', '歌词', '', ''])
        # 歌名列表头跟随内容左对齐，其余列表头居中
        self.table.horizontalHeaderItem(0).setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.doubleClicked.connect(lambda _i: self.do_preview())   # 双击歌曲行 = 直接试听
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(False)
        self.table.verticalHeader().setVisible(False)
        self.table.itemDoubleClicked.connect(lambda _: self.do_preview())
        hdr = self.table.horizontalHeader()
        # 歌名固定 250px（可拖动）；数据列按内容自适应；
        # 第 8 列是一列"空列"，专门用来吸收剩余宽度 —— 这样表格铺满不露白，
        # 又不会像让某一数据列 Stretch 那样把它拉得难看。
        hdr.setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.setColumnWidth(0, 250)
        for c in [1, 2, 3, 4, 5, 6, 7]:
            hdr.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(8, QHeaderView.Stretch)
        self.table.setColumnHidden(9, True)      # 占位列，仅用于挂数据
        outer.addWidget(self.table, 1)

        # ---- 目录 + 操作
        card2 = QFrame(); card2.setObjectName('card')
        lay2 = QVBoxLayout(card2)
        lay2.setContentsMargins(16, 12, 16, 12)
        lay2.setSpacing(12)

        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel('保存到：'))
        self.edit_dir = QLineEdit(os.path.join(os.path.expanduser('~'), 'Music'))
        dir_row.addWidget(self.edit_dir, 1)
        btn_pick = QPushButton('选择目录…')
        btn_pick.clicked.connect(self.pick_dir)
        dir_row.addWidget(btn_pick)
        btn_open = QPushButton('打开目录')
        btn_open.clicked.connect(self.open_dir)
        dir_row.addWidget(btn_open)
        lay2.addLayout(dir_row)

        btn_row = QHBoxLayout()
        self.btn_play = QPushButton('▶ 试听')
        self.btn_play.setMinimumWidth(110)
        self.btn_play.setToolTip('先在上方列表点一下选中歌曲再点这里；也可以直接双击歌曲行')
        self.btn_play.clicked.connect(self.do_preview)
        btn_row.addWidget(self.btn_play)

        self.btn_stop = QPushButton('⏹ 停止')
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_play)
        btn_row.addWidget(self.btn_stop)

        btn_row.addSpacing(10)
        self.btn_save = QPushButton('💾 保存试听版本')
        self.btn_save.setObjectName('primary')
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self.save_preview)
        btn_row.addWidget(self.btn_save)

        self.btn_discard = QPushButton('🗑 丢弃')
        self.btn_discard.setObjectName('danger')
        self.btn_discard.setEnabled(False)
        self.btn_discard.clicked.connect(self.discard_preview)
        btn_row.addWidget(self.btn_discard)

        btn_row.addSpacing(16)
        self.btn_download = QPushButton('⬇ 直接下载')
        self.btn_download.clicked.connect(self.do_download)
        btn_row.addWidget(self.btn_download)

        btn_row.addSpacing(16)
        self.chk_mp3 = QCheckBox('下载后转成 MP3')
        self.chk_mp3.setToolTip('勾选后，无损 / 其他格式会在下载完成后自动转成 320kbps MP3，原文件不再保留')
        btn_row.addWidget(self.chk_mp3)

        btn_row.addStretch(1)
        lay2.addLayout(btn_row)

        # 播放控制
        play_row = QHBoxLayout()
        self.lbl_now = QLabel('试听：未开始')
        self.lbl_now.setObjectName('hint')
        self.lbl_now.setMinimumWidth(260)
        play_row.addWidget(self.lbl_now)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.setEnabled(False)
        self.slider.sliderReleased.connect(self.seek)
        play_row.addWidget(self.slider, 1)
        self.lbl_time = QLabel('00:00 / 00:00')
        self.lbl_time.setObjectName('hint')
        play_row.addWidget(self.lbl_time)
        lay2.addLayout(play_row)

        # 进度 / 状态
        prog_row = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        prog_row.addWidget(self.progress, 1)
        self.lbl_status = QLabel('就绪')
        self.lbl_status.setObjectName('hint')
        self.lbl_status.setMinimumWidth(300)
        prog_row.addWidget(self.lbl_status)
        lay2.addLayout(prog_row)

        self._apply_shadow(card2)
        outer.addWidget(card2)

        # 播放器
        if HAS_MEDIA:
            self.player = QMediaPlayer()
            self.player.setVolume(80)
            self.player.positionChanged.connect(self.on_pos)
            self.player.durationChanged.connect(self.on_dur)
            self.player.stateChanged.connect(self.on_state)
            self.player.error.connect(self.on_media_error)

    # ------------------------------------------------------------ 工具
    def current_sources(self):
        """主力四个 + 下拉里勾选的，一起作为本次搜索的音源"""
        srcs = [cb.property('cls') for cb in self.src_boxes if cb.isChecked()]
        srcs += [cb.property('cls') for cb in self.more_boxes if cb.isChecked()]
        return srcs

    def _update_more_text(self):
        n = sum(1 for cb in self.more_boxes if cb.isChecked())
        self.btn_more.setText('更多音源（已选 %d）▾' % n if n else '更多音源 ▾')

    def selected_item(self):
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return None, -1
        row = rows[0].row()
        it = self.table.item(row, 9)
        if it is None:
            return None, -1
        idx = it.data(Qt.UserRole)
        if idx is None or idx < 0 or idx >= len(self.all_items):
            return None, -1
        return self.all_items[idx], idx

    @staticmethod
    def attr(obj, name, default=''):
        val = getattr(obj, name, None)
        if val is None:
            try:
                val = obj.todict().get(name)
            except Exception:
                val = None
        return default if val is None else val

    @staticmethod
    def fmt_size(n):
        try:
            n = float(n)
        except Exception:
            return str(n)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if n < 1024 or unit == 'GB':
                return '%.2f %s' % (n, unit) if unit != 'B' else '%d B' % n
            n /= 1024

    def set_status(self, text):
        self.lbl_status.setText(text)

    def _tick_search(self):
        el = time.time() - self._t0
        self.set_status('正在搜索… 已用 %.0f 秒（源越多、条数越多越慢，通常 20–60 秒，请稍候）' % el)

    def spec(self, item):
        """返回 (格式, 是否无损, 大小文本)"""
        ext = str(self.attr(item, 'ext', '')).lower()
        lossless = ext in LOSSLESS_EXTS
        size = self.attr(item, 'file_size', '')
        if size and not isinstance(size, str):
            size = self.fmt_size(size)
        size = str(size)
        if size and not size.lower().endswith(('b', 'kb', 'mb', 'gb')) and size.replace('.', '').isdigit():
            size = self.fmt_size(float(size) * 1024 * 1024)
        return ext.upper() or '?', lossless, size

    # ------------------------------------------------------------ 搜索
    def do_search(self):
        if self.search_thread and self.search_thread.isRunning():
            return
        keyword = self.edit_keyword.text().strip()
        if not keyword:
            QMessageBox.information(self, '提示', '请先输入歌名或歌手')
            return
        sources = self.current_sources()
        if not sources:
            QMessageBox.information(self, '提示', '至少选择一个音源')
            return

        self.stop_play()
        self.clear_preview()
        self.table.setRowCount(0)
        self.all_items = []
        self.clients = {}
        self._pending = set(sources)
        self._timeout_srcs = []
        self.btn_search.setEnabled(False)
        self.progress.setRange(0, 0)          # 不确定进度
        self._t0 = time.time()
        self._timer.start()
        self.set_status('正在搜索「%s」… 已用 0 秒（各源结果会陆续出现）' % keyword)

        self.search_thread = SearchThread(keyword, sources, self.spin_size.value(), CACHE_DIR)
        self.search_thread.partial.connect(self.on_search_partial)
        self.search_thread.done.connect(self.on_search_done)
        self.search_thread.fail.connect(self.on_search_fail)
        self.search_thread.start()

    def on_search_partial(self, src, items, client, note=''):
        """某个源返回了：立刻把它的结果并进表格"""
        if client is not None:
            self.clients[src] = client
        self._pending.discard(src)
        name = str(src).replace('MusicClient', '')

        if note == 'timeout':
            self._timeout_srcs.append(name)
            self.set_status('「%s」响应太慢，已跳过（超过 %.0f 秒）｜累计 %d 条｜待返回 %d 个源'
                            % (name, SearchThread.TIMEOUT,
                               len(self.all_items), len(self._pending)))
            return

        if items:
            self.all_items.extend(items)
        self.render_table()
        tag = '（出错）' if note.startswith('error') else ''
        self.set_status('已返回 %s%s（%d 条）｜累计 %d 条｜待返回 %d 个源'
                        % (name, tag, len(items or []), len(self.all_items), len(self._pending)))

    def on_search_done(self, elapsed):
        """全部源都回来了（或超时被跳过）"""
        self._timer.stop()
        self.btn_search.setEnabled(True)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        lossless = sum(1 for i in self.all_items if self.spec(i)[1])
        tail = ''
        if self._timeout_srcs:
            tail = '；已跳过超时源：%s' % '、'.join(self._timeout_srcs)
        self.set_status('搜索完成：共 %d 条（其中无损 %d 条），耗时 %.1f 秒%s'
                        % (len(self.all_items), lossless, elapsed, tail))
        # 自动选中第一条：否则用户直接点「试听」会没反应（必须先手动选中一行）
        if self.table.rowCount() > 0:
            self.table.selectRow(0)

    def on_search_fail(self, msg):
        self._timer.stop()
        self.btn_search.setEnabled(True)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.set_status('搜索失败')
        QMessageBox.warning(self, '搜索失败', msg[:900])

    # ------------------------------------------------------------ 渲染
    def render_table(self):
        mode = self.combo_filter.currentText()
        rows = []
        for idx, item in enumerate(self.all_items):
            ext, lossless, size = self.spec(item)
            if mode == FILTER_LOSSLESS and not lossless:
                continue
            if mode == FILTER_MP3 and ext not in {'MP3'}:
                continue
            rows.append((idx, item, ext, lossless, size))

        self.table.setRowCount(len(rows))
        for r, (idx, item, ext, lossless, size) in enumerate(rows):
            vals = [
                str(self.attr(item, 'song_name', '')),
                str(self.attr(item, 'singers', '')),
                ext,
                size,
                str(self.attr(item, 'duration', '')),
                str(self.attr(item, 'album', '')),
                str(self.attr(item, 'source', '')).replace('MusicClient', ''),
                '',
                '',
                '',
            ]
            for c, v in enumerate(vals):
                cell = QTableWidgetItem(v)
                if c != 0:
                    cell.setTextAlignment(Qt.AlignCenter)
                if c == 9:
                    cell.setData(Qt.UserRole, idx)
                if c == 8:
                    cell.setBackground(QColor(255, 255, 255))   # 空白列统一成白色，避免出现色差块
                if c == 0:
                    cell.setToolTip(v)          # 歌名被截断时可悬停看全
                    cell.setForeground(QColor('#22304A'))
                    _f = cell.font()
                    _f.setWeight(QFont.Medium)
                    cell.setFont(_f)
                elif c == 2 and lossless:
                    cell.setForeground(QColor('#2E7D5B'))   # 无损格式用绿色标出
                else:
                    cell.setForeground(QColor('#64748B'))
                self.table.setItem(r, c, cell)
            # 「歌词」列放复选框（默认不勾）
            self.table.setCellWidget(r, 7, self._make_lyric_box(idx))
        self.table.resizeRowsToContents()

    def _make_lyric_box(self, idx):
        """「歌词」列的复选框，默认不勾；状态记在 lyric_checked 里，重绘后不丢"""
        cb = QCheckBox()
        cb.setChecked(idx in self.lyric_checked)
        cb.setToolTip('勾选后，下载 / 保存这首歌时同时写入 .lrc 歌词文件')
        cb.stateChanged.connect(lambda _s, i=idx, b=cb: self._on_lyric_toggle(i, b))
        holder = QWidget()
        lay = QHBoxLayout(holder)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setAlignment(Qt.AlignCenter)
        lay.addWidget(cb)
        return holder

    def _on_lyric_toggle(self, idx, box):
        if box.isChecked():
            self.lyric_checked.add(idx)
        else:
            self.lyric_checked.discard(idx)

    def save_lyric(self, item, audio_path):
        """把搜索结果里自带的歌词写成同名 .lrc；没有歌词则返回 None"""
        lyric = self.attr(item, 'lyric', '')
        txt = str(lyric or '').strip()
        if not txt or txt.lower() in ('none', 'null', 'nan'):
            return None
        lrc_path = os.path.splitext(audio_path)[0] + '.lrc'
        try:
            with open(lrc_path, 'w', encoding='utf-8') as f:
                f.write(txt.replace('\r\n', '\n').rstrip() + '\n')
            return lrc_path
        except Exception:
            return None

    # ------------------------------------------------------------ 使用说明
    def show_help(self):
        """弹出使用说明。内容优先取程序目录的「使用说明.txt」，改 txt 即可生效、不必重打包。"""
        text = ''
        try:
            p = os.path.join(HERE, '使用说明.txt')
            if os.path.exists(p):
                with open(p, encoding='utf-8') as f:
                    text = f.read().strip()
        except Exception:
            text = ''
        if not text:
            text = HELP_TEXT_FALLBACK.strip()

        dlg = QDialog(self)
        dlg.setWindowTitle('使用说明')
        dlg.resize(620, 580)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        tb = QTextBrowser(dlg)
        tb.setHtml(self._help_html(text))
        lay.addWidget(tb)

        row = QHBoxLayout()
        row.addStretch(1)
        btn = QPushButton('知道了')
        btn.setObjectName('primary')
        btn.setMinimumWidth(100)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(dlg.accept)
        row.addWidget(btn)
        lay.addLayout(row)

        dlg.exec_()

    @staticmethod
    def _help_html(text):
        """纯文本说明 → 带样式的 HTML：首行标题、次行署名、分节标题走主色"""
        import html as _html
        blocks = []
        for i, raw in enumerate(text.split('\n')):
            line = raw.rstrip()
            esc = _html.escape(line)
            if not line.strip():
                blocks.append('<div style="height:6px;"></div>')
            elif i == 0:
                blocks.append('<div style="font-size:16px;font-weight:600;color:#22304A;">%s</div>' % esc)
            elif i == 1:
                blocks.append('<div style="font-size:12px;color:#9AA6B6;margin-top:2px;">%s</div>' % esc)
            elif line.strip().startswith(('【', '使用小技巧', '使用说明')):
                blocks.append('<div style="font-size:14px;font-weight:600;color:#378ADD;'
                              'margin:14px 0 8px 0;">%s</div>' % esc)
            elif line.lstrip().startswith(('·', '-', '•')):
                blocks.append('<div style="margin:4px 0 4px 20px;color:#64748B;">%s</div>' % esc)
            else:
                blocks.append('<div style="margin:5px 0;line-height:1.8;">%s</div>' % esc)
        return ('<div style="font-family:\'Microsoft YaHei UI\',\'Microsoft YaHei\',sans-serif;'
                'font-size:13px;color:#3A4A62;">' + ''.join(blocks) + '</div>')

    # ------------------------------------------------------------ 目录
    def pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, '选择保存目录', self.edit_dir.text() or os.path.expanduser('~'))
        if d:
            self.edit_dir.setText(os.path.normpath(d))

    def open_dir(self):
        d = self.edit_dir.text().strip()
        if d and os.path.isdir(d):
            os.startfile(d)                                  # noqa: Windows
        else:
            QMessageBox.information(self, '提示', '目录不存在：%s' % d)

    def target_path(self, item):
        ext = self.spec(item)[0].lower() or 'mp3'
        name = '%s - %s.%s' % (self.attr(item, 'singers', '未知歌手'),
                               self.attr(item, 'song_name', '未知歌曲'), ext)
        return os.path.join(self.edit_dir.text().strip(), sanitize_filename(name))

    # ------------------------------------------------------------ 下载
    def _headers_for(self, item):
        hdr = getattr(item, 'default_download_headers', None)
        if not hdr:
            try:
                src = getattr(item, 'source')
                cli = self.clients.get(src) or self.client
                if cli is not None:
                    hdr = cli.music_clients[src].default_download_headers
            except Exception:
                hdr = None
        return hdr or {}

    def do_download(self):
        item, idx = self.selected_item()
        if item is None:
            QMessageBox.information(self, '提示', '请先在列表里选中一首歌')
            return
        if self.dl_thread and self.dl_thread.isRunning():
            QMessageBox.information(self, '提示', '已有下载任务在进行')
            return
        url = self.attr(item, 'download_url', '')
        if not url:
            QMessageBox.warning(self, '无法下载', '这首歌没有可用的下载地址（可能是会员专享）。')
            return
        dest = self.target_path(item)
        if os.path.exists(dest):
            if QMessageBox.question(self, '已存在', '%s\n已存在，要覆盖吗？' % dest) != QMessageBox.Yes:
                return
        # 正式下载前先把试听缓存清掉，不让它白占硬盘
        self.stop_play()
        self.clear_preview()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.set_status('正在下载：%s' % os.path.basename(dest))
        self._dl_idx = idx
        self.dl_thread = DownloadThread(url, self._headers_for(item), dest,
                                        label='歌曲',
                                        to_mp3=self.chk_mp3.isChecked())
        self.dl_thread.tick.connect(self.on_tick)
        self.dl_thread.ok.connect(self.on_download_ok)
        self.dl_thread.fail.connect(self.on_download_fail)
        self.dl_thread.start()

    def on_tick(self, done, total):
        if total:
            self.progress.setValue(int(done * 100 / total))
            self.set_status('已下载 %.1f / %.1f MB' % (done / 1048576, total / 1048576))
        else:
            self.set_status('已下载 %.1f MB' % (done / 1048576,))

    def on_download_ok(self, path, label):
        self.progress.setValue(100)
        extra = ''
        item = self.all_items[self._dl_idx] if 0 <= self._dl_idx < len(self.all_items) else None
        if item is not None and self._dl_idx in self.lyric_checked:
            lrc = self.save_lyric(item, path)
            extra = '\n歌词：%s' % (os.path.basename(lrc) if lrc else '该曲目没有可用歌词')
        self.set_status('下载完成：%s' % os.path.basename(path))
        QMessageBox.information(self, '完成', '已保存到：\n%s%s' % (path, extra))

    def on_download_fail(self, msg):
        self.set_status('下载失败：%s' % msg[:80])
        QMessageBox.warning(self, '下载失败', msg[:900])

    # ------------------------------------------------------------ 试听
    def do_preview(self):
        item, idx = self.selected_item()
        if item is None:
            QMessageBox.information(self, '提示', '请先在列表里选中一首歌')
            return
        # 已有同一首的试听文件 → 直接播
        if self.preview_path and os.path.exists(self.preview_path) and self.preview_idx == idx:
            self.start_play()
            return
        if self.dl_thread and self.dl_thread.isRunning():
            # 上一首还在缓冲？直接中止，改成试听这一首（比弹「正在下载」更顺手）
            self._preview_gen += 1
            self.dl_thread.abort()
            self.dl_thread.wait(3000)
        url = self.attr(item, 'download_url', '')
        if not url:
            QMessageBox.warning(self, '无法试听', '这首歌没有可用地址（可能是会员专享）。')
            return

        self._preview_gen += 1
        gen = self._preview_gen
        self.stop_play()
        self.clear_preview()
        ext = self.spec(item)[0].lower() or 'mp3'
        # 文件名带时间戳：绝不覆盖上一次的试听文件。
        # Windows 上被播放器占用的文件删不掉也覆盖不了，同名会直接报「拒绝访问」。
        tmp = os.path.join(PREVIEW_DIR, 'preview_%d.%s' % (int(time.time() * 1000), ext))
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.set_status('准备试听，正在缓冲…')
        self.btn_play.setEnabled(False)

        self.preview_idx = idx
        self.preview_orig = None
        self.preview_mp3 = None
        th = DownloadThread(url, self._headers_for(item), tmp, label='试听')
        th.gen = gen
        th.tick.connect(self.on_tick)
        th.ok.connect(self.on_preview_ready)
        th.fail.connect(self.on_preview_fail)
        self.dl_thread = th
        th.start()

    def on_preview_ready(self, path, _label):
        if getattr(self.sender(), 'gen', -1) != self._preview_gen:
            return                      # 上一次试听的迟到信号，丢掉，否则会把新歌挤掉
        self.preview_orig = path
        self.progress.setValue(100)
        self.btn_save.setEnabled(True)
        self.btn_discard.setEnabled(True)

        ext = os.path.splitext(path)[1].lower().lstrip('.')
        if ext in NEED_CONVERT_EXTS:
            # 内置播放器放不了这种格式 → 先转成 MP3 再播，不跳外部播放器
            self.set_status('缓冲完成，正在转成 MP3 以便内置播放…')
            dst = os.path.splitext(path)[0] + '.mp3'
            th = ConvertThread(path, dst, self._preview_gen)
            th.ok.connect(self.on_convert_ok)
            th.fail.connect(self.on_convert_fail)
            self.cv_thread = th
            th.start()
            return

        self.preview_path = path
        self.btn_play.setEnabled(True)
        self.set_status('缓冲完成，开始播放')
        self.start_play()

    def on_convert_ok(self, path):
        if getattr(self.sender(), 'gen', -1) != self._preview_gen:
            return
        self.preview_mp3 = path
        self.preview_path = path
        self.btn_play.setEnabled(True)
        self.set_status('已转成 MP3，开始播放')
        self.start_play()

    def on_convert_fail(self, msg):
        if getattr(self.sender(), 'gen', -1) != self._preview_gen:
            return
        self.btn_play.setEnabled(True)
        # 转码失败就退回原始文件试听（Qt 放不了时仍会自动交给系统播放器）
        if self.preview_orig and os.path.exists(self.preview_orig):
            self.preview_path = self.preview_orig
            self.set_status('转 MP3 失败，改用原始文件试听')
            self.start_play()
        else:
            self.set_status('试听失败：%s' % msg[:80])

    def on_preview_fail(self, msg):
        if getattr(self.sender(), 'gen', -1) != self._preview_gen:
            return                      # 被主动中止的旧任务，不算失败，别弹窗
        self.btn_play.setEnabled(True)
        self.set_status('试听失败：%s' % msg[:80])
        QMessageBox.warning(self, '试听失败', msg[:900])

    def start_play(self):
        if not self.preview_path or not os.path.exists(self.preview_path):
            return
        self.lbl_now.setText('试听：%s' % os.path.basename(self.preview_path))
        if self.player is not None:
            self.player.setMedia(QMediaContent(QUrl.fromLocalFile(self.preview_path)))
            self.player.play()
            self.btn_stop.setEnabled(True)
            self.slider.setEnabled(True)
        else:
            os.startfile(self.preview_path)                  # noqa: Windows

    def stop_play(self):
        if self.player is not None:
            self.player.stop()
            self.player.setMedia(QMediaContent())     # 断开对旧文件的引用，避免文件被删后报错
        self.btn_stop.setEnabled(False)
        self.slider.setValue(0)
        self.lbl_time.setText('00:00 / 00:00')

    def on_state(self, state):
        if state == QMediaPlayer.StoppedState:
            self.btn_stop.setEnabled(False)

    @staticmethod
    def ms2str(ms):
        s = max(0, int(ms // 1000))
        return '%02d:%02d' % (s // 60, s % 60)

    def on_pos(self, ms):
        if self.player is not None:
            dur = self.player.duration()
            if dur > 0:
                self.slider.setValue(int(ms * 1000 / dur))
            self.lbl_time.setText('%s / %s' % (self.ms2str(ms), self.ms2str(dur)))

    def on_dur(self, _ms):
        pass

    def seek(self):
        if self.player is not None and self.player.duration() > 0:
            self.player.setPosition(int(self.slider.value() * self.player.duration() / 1000))

    def on_media_error(self):
        """Qt 播不了就交给系统默认播放器"""
        if self._media_warned or not self.preview_path:
            return
        if not os.path.exists(self.preview_path):
            return                                    # 文件已被清掉，不是真错误
        if self.player is not None and self.player.media().isNull():
            return                                    # 正在切歌，媒体已清空，忽略残留错误
        self._media_warned = True
        self.set_status('内置播放器不支持该格式，已用系统播放器打开')
        try:
            os.startfile(self.preview_path)
        except Exception as err:
            QMessageBox.warning(self, '播放失败', '无法播放：%s' % err)

    def save_preview(self):
        # 保存以「原始下载文件」为准 —— 试听时转出来的 mp3 只是为了让内置播放器能放，
        # 用户要保存的应该是源文件（是否转 MP3 由下面那个勾选框决定）
        src = self.preview_orig if (self.preview_orig and os.path.exists(self.preview_orig)) else self.preview_path
        if not src or not os.path.exists(src):
            return
        item = self.all_items[self.preview_idx] if 0 <= self.preview_idx < len(self.all_items) else None
        if item is None:
            return
        self.stop_play()
        dest = self.target_path(item)
        try:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            if os.path.exists(dest):
                if QMessageBox.question(self, '已存在', '%s\n已存在，要覆盖吗？' % dest) != QMessageBox.Yes:
                    return
                os.remove(dest)
            shutil.move(src, dest)
            # 勾了「转成 MP3」就在保存时转码
            if self.chk_mp3.isChecked() and not dest.lower().endswith('.mp3'):
                mp3_path = os.path.splitext(dest)[0] + '.mp3'
                if self.preview_mp3 and os.path.exists(self.preview_mp3):
                    # 试听时已经转好了，直接拿来用，省一次转码
                    shutil.copy2(self.preview_mp3, mp3_path)
                    os.remove(dest)
                else:
                    self.set_status('正在转成 MP3…')
                    QApplication.setOverrideCursor(Qt.WaitCursor)
                    try:
                        convert_to_mp3(dest, mp3_path)
                        os.remove(dest)
                    finally:
                        QApplication.restoreOverrideCursor()
                dest = mp3_path
            # 勾了「歌词」就写 .lrc
            extra = ''
            if self.preview_idx in self.lyric_checked:
                lrc = self.save_lyric(item, dest)
                extra = '\n歌词：%s' % (os.path.basename(lrc) if lrc else '该曲目没有可用歌词')
            self.set_status('已保存：%s' % os.path.basename(dest))
            QMessageBox.information(self, '已保存', '已保存到：\n%s%s' % (dest, extra))
            self.clear_preview()
        except Exception as err:
            QMessageBox.warning(self, '保存失败', str(err))

    def discard_preview(self):
        self.stop_play()
        self.clear_preview()
        self.set_status('已丢弃试听文件')

    def clear_preview(self):
        # 清空整个试听缓存目录（不只当前文件）：上次会话的残留、
        # 以及被播放器短暂占用而删不掉的文件，都不该留给下一次试听添麻烦
        try:
            for fn in os.listdir(PREVIEW_DIR):
                try:
                    os.remove(os.path.join(PREVIEW_DIR, fn))
                except Exception:
                    pass
        except Exception:
            pass
        self.preview_path = None
        self.preview_orig = None
        self.preview_mp3 = None
        self.preview_idx = -1
        self.btn_save.setEnabled(False)
        self.btn_discard.setEnabled(False)
        self.lbl_now.setText('试听：未开始')
        self.btn_play.setEnabled(True)

    # ------------------------------------------------------------ 关闭
    def closeEvent(self, event):
        try:
            if self.search_thread and self.search_thread.isRunning():
                self.search_thread.abort()
                self.search_thread.wait(2000)
            if self.dl_thread and self.dl_thread.isRunning():
                self.dl_thread.abort()
                self.dl_thread.wait(2000)
            self.stop_play()
            self.clear_preview()
        except Exception:
            pass
        event.accept()
        # musicdl 内部并发搜索用的是非 daemon 线程，正常退出会被慢源拖住（实测可拖几分钟），
        # 所以这里延迟一拍强制结束进程，保证「关窗即退」。
        QTimer.singleShot(80, lambda: os._exit(0))


def main():
    if sys.platform.startswith('win'):
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    app = QApplication(sys.argv)
    css = STYLE
    for _ph, _path in build_ui_icons().items():
        css = css.replace(_ph, _path)
    app.setStyleSheet(css)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
