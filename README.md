# future音频下载器

基于开源库 [musicdl](https://github.com/CharlesPikachu/musicdl) 的中文音乐搜索 / 试听 / 下载桌面工具，PyQt5 图形界面。

署名：future chen

## 功能

- **搜索**：聚合 57 个音源（网易云、QQ音乐、酷狗、酷我等），分源并发、谁先返回谁先显示；支持按格式筛选（全部 / 只要无损 / 只要 MP3）
- **试听**：双击结果行即可试听；无损格式（FLAC / APE 等）会自动转成 MP3 后用内置播放器播放
- **下载**：保存试听版本或直接下载；可勾选「下载后转成 MP3」（320kbps）
- **歌词**：勾选「歌词」列，下载时自动生成同名 `.lrc`
- **分类保存**：按 `<音源>\<日期 歌手 歌名>\` 自动归类

## 环境要求

- Windows
- Python 3.10 及以上（本项目开发于 3.13）

## 安装

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

## 启动

```bash
.venv\Scripts\python musicdl_gui.py
```

或直接双击 `start_gui.bat`。

## 打包成 exe（给没有 Python 的电脑用）

exe 只做启动器，业务逻辑仍从同目录的 `musicdl_gui.py` 读取，所以**改功能不用重新打包**。

```bash
pip install pyinstaller
pyinstaller _pack\app.spec
```

> ⚠️ Windows 上打包必须走**纯英文路径**：PyInstaller 的 Qt hook 在中文路径下会把中文解析成 `?` 而失败；目录联接（junction）无效，且必须用 `python -m PyInstaller` 而不是 `pyinstaller.exe`。

改完代码后双击 `更新打包版.bat` 即可同步到打包目录。

## 目录说明

| 路径 | 说明 |
|---|---|
| `musicdl_gui.py` | 主程序（界面 + 业务逻辑） |
| `search.py` / `download.py` / `verify.py` | 命令行小工具 |
| `gui/` | 窗口图标 |
| `_pack/` | 打包配置（app.spec + launcher.py） |
| `项目文档.md` | 完整技术文档（架构、坑位速查、操作流程） |

## 声明

本项目仅为技术学习与个人使用，依赖第三方公开接口。请尊重音乐版权，下载的内容请勿用于商业用途。
