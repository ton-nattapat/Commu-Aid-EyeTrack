# PyInstaller recipe for "Communication Aid.exe". Run it through build_windows.ps1, not directly.
#
# COMMU_AID_TRANSLATE=0 leaves out PyTorch and transformers (much smaller); Speak then says the
# typed English instead of Thai. The NLLB model itself is never bundled: the app downloads it
# (about 2.5 GB) on first start and caches it in %USERPROFILE%\.cache\huggingface.

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).resolve().parent.parent
APP_NAME = "Communication Aid"
TRANSLATE = os.environ.get("COMMU_AID_TRANSLATE", "1") != "0"

datas = [
    (str(ROOT / "config.yaml"), "."),
    (str(ROOT / "commu_aid" / "data"), "commu_aid/data"),
]
binaries = []
hiddenimports = collect_submodules("commu_aid")

# The Tobii SDK loads its native interop library (a DLL) at import time.
hiddenimports += ["tobii_research"]
for package in ("tobiiresearch",):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h

# Windows speech goes through SAPI with pywin32.
hiddenimports += ["win32com", "win32com.client", "pythoncom", "pywintypes"]

excludes = ["tkinter", "matplotlib", "IPython", "tensorflow", "jax", "flax", "torchvision", "torchaudio"]
if TRANSLATE:
    # transformers imports model classes by name at run time, so name the ones NLLB needs.
    hiddenimports += collect_submodules("transformers.models.nllb")
    hiddenimports += collect_submodules("transformers.models.m2m_100")
    hiddenimports += ["sentencepiece"]
else:
    excludes += ["torch", "transformers", "tokenizers", "safetensors", "sentencepiece", "huggingface_hub"]

a = Analysis(
    [str(ROOT / "packaging" / "windows" / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=APP_NAME)
