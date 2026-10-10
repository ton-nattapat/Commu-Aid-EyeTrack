# PyInstaller recipe for "Communication Aid.app". Run it through build_mac.sh, not directly.
#
# COMMU_AID_TRANSLATE=0 leaves out PyTorch and transformers (several hundred MB smaller); Speak then
# says the typed English instead of Thai. The NLLB model itself is never bundled: the app
# downloads it (about 2.5 GB) on first start and caches it in ~/.cache/huggingface.

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).resolve().parent.parent
APP_NAME = "Communication Aid"
VERSION = os.environ.get("COMMU_AID_VERSION", "0.1.0")
TRANSLATE = os.environ.get("COMMU_AID_TRANSLATE", "1") != "0"

datas = [
    (str(ROOT / "config.yaml"), "."),
    (str(ROOT / "commu_aid" / "data"), "commu_aid/data"),
]
binaries = []
hiddenimports = collect_submodules("commu_aid")

# The Tobii SDK loads its native interop library at import time.
hiddenimports += ["tobii_research"]
for package in ("tobiiresearch",):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h

excludes = ["tkinter", "matplotlib", "IPython", "tensorflow", "jax", "flax", "torchvision", "torchaudio"]
if TRANSLATE:
    # transformers imports model classes by name at run time, so name the ones NLLB needs.
    hiddenimports += collect_submodules("transformers.models.nllb")
    hiddenimports += collect_submodules("transformers.models.m2m_100")
    hiddenimports += ["sentencepiece"]
else:
    excludes += ["torch", "transformers", "tokenizers", "safetensors", "sentencepiece", "huggingface_hub"]

a = Analysis(
    [str(ROOT / "packaging" / "mac" / "launcher.py")],
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
    argv_emulation=False,
    upx=False,
    codesign_identity=os.environ.get("COMMU_AID_SIGN_ID") or None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=APP_NAME)
app = BUNDLE(
    coll,
    name=f"{APP_NAME}.app",
    icon=None,
    bundle_identifier="com.github.ton-nattapat.commu-aid",
    version=VERSION,
    info_plist={
        "CFBundleDisplayName": APP_NAME,
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "12.0",
        "LSApplicationCategoryType": "public.app-category.medical",
    },
)
