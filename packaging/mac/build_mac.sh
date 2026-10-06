#!/usr/bin/env bash
# Build "Communication Aid.app" and a .dmg installer to copy to other Macs.
#
#   conda activate commu-aid
#   packaging/mac/build_mac.sh                  # full app, with offline translation
#   packaging/mac/build_mac.sh --no-translate   # several hundred MB smaller; Speak says the English
#   packaging/mac/build_mac.sh --version 0.2.0
#
# Output: dist/CommunicationAid-<version>-<arm64|x86_64>.dmg
# The app runs on Macs with the same chip type as the Mac that built it (Apple silicon: arm64).
# The Tobii Pro Spark runtime is NOT included: install it on each Mac from Tobii Connect
# (docs/install-mac.md, step 4).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

APP_NAME="Communication Aid"
VERSION="0.1.0"
TRANSLATE=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-translate) TRANSLATE=0 ;;
    --version) VERSION="$2"; shift ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

if [[ "$(uname)" != "Darwin" ]]; then
  echo "Build the Mac app on a Mac." >&2
  exit 1
fi

PYTHON="${PYTHON:-python}"
if ! "$PYTHON" -c 'import sys; sys.exit(sys.version_info[:2] != (3, 10))'; then
  echo "Needs Python 3.10 (tobii-research only works there). Run: conda activate commu-aid" >&2
  exit 1
fi
MODULES="PySide6 yaml tobii_research"
[[ $TRANSLATE == 1 ]] && MODULES="$MODULES torch transformers sentencepiece"
for module in $MODULES; do
  if ! "$PYTHON" -c "import $module" 2>/dev/null; then
    echo "Python module '$module' is missing. Run: conda env update -f environment.yml --prune" >&2
    exit 1
  fi
done

echo "==> Installing PyInstaller"
"$PYTHON" -m pip install --quiet -r requirements-build.txt

echo "==> Building $APP_NAME.app (version $VERSION, translation $([[ $TRANSLATE == 1 ]] && echo on || echo off))"
rm -rf "dist/$APP_NAME" "dist/$APP_NAME.app"
COMMU_AID_VERSION="$VERSION" COMMU_AID_TRANSLATE="$TRANSLATE" \
  "$PYTHON" -m PyInstaller --noconfirm --clean --distpath dist --workpath build/pyinstaller \
  packaging/mac/commu_aid.spec

APP="dist/$APP_NAME.app"
echo "==> Signing (ad hoc: no Apple Developer ID, so other Macs ask once before opening it)"
codesign --force --deep --sign "${COMMU_AID_SIGN_ID:--}" "$APP"
codesign --verify --deep --strict "$APP"

echo "==> Making the installer disk image"
ARCH="$(uname -m)"
DMG="dist/CommunicationAid-$VERSION-$ARCH.dmg"
STAGE="build/dmg"
rm -rf "$STAGE" "$DMG"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
cp "packaging/mac/Read Me First.txt" "$STAGE/"
hdiutil create -quiet -volname "$APP_NAME" -srcfolder "$STAGE" -fs HFS+ -format ULFO -ov "$DMG"
rm -rf "$STAGE"

echo
echo "Done: $DMG ($(du -h "$DMG" | cut -f1))"
echo "Send it to the other Mac and follow docs/install-mac.md (also on the disk as Read Me First.txt)."
