# PyInstaller recipe for the desktop app. Build from apps/desktop:
#   pip install pyinstaller && pyinstaller audiobook_tts.spec --noconfirm
# The result is the folder dist/AudiobookTTS (run dist/AudiobookTTS/AudiobookTTS). It only runs on the operating
# system it was built on, and it still needs the backend: put API_BASE_URL=http://host:5000 in a .env file next to it.
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = collect_data_files("customtkinter")  # its themes and fonts are data files, not Python modules
hidden = collect_submodules("ui") + collect_submodules("player") + ["matplotlib.backends.backend_tkagg"]

a = Analysis(
    ["main.py"],
    pathex=["."],
    datas=datas,
    hiddenimports=hidden,
    excludes=["pytest", "tests", "benchmarks"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="AudiobookTTS", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="AudiobookTTS")
