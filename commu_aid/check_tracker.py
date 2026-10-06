"""Check why the Tobii Pro Spark is or isn't found, without starting the app.

    python -m commu_aid.check_tracker

Prints the Python and SDK versions, what the Tobii SDK finds, and on macOS whether the Mac
itself sees a Tobii device on USB. Then compares the screen size the tracker was set up for
(Display Setup in Tobii Pro Eye Tracker Manager) with the real screen, because a mismatch makes
gaze miss more and more towards the screen edges. Each problem comes with what to try next.
"""

from __future__ import annotations

import platform
import re
import subprocess
import sys
from typing import List, Optional, Tuple

TOBII_USB_VENDOR_ID = 0x2104  # Tobii AB
SIZE_TOLERANCE = 0.08  # display area and screen may differ this much (8%) before we warn


def _mac_usb_registry() -> Optional[str]:
    try:
        return subprocess.run(["ioreg", "-p", "IOUSB", "-l", "-w0"], capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return None


def tobii_usb_devices(registry: str) -> List[str]:
    """Names of the Tobii devices in `ioreg -p IOUSB -l -w0` output."""
    found = []
    name = None
    for line in registry.splitlines():
        m = re.search(r"\+-o (.+?)@", line)
        if m:
            name = m.group(1)
            if "tobii" in name.lower():
                found.append(name)
            continue
        m = re.search(r'"idVendor" = (\d+)', line)
        if m and int(m.group(1)) == TOBII_USB_VENDOR_ID and name and name not in found:
            found.append(name)
    return found


def display_area_problems(area_mm: Tuple[float, float], screen_mm: Optional[Tuple[float, float]]) -> List[str]:
    """Warnings when the tracker's display area does not match the screen it sits on."""
    w, h = area_mm
    if screen_mm is None or min(screen_mm) <= 0:
        return [] if w > 0 and h > 0 else ["the tracker has no display area set up"]
    sw, sh = screen_mm
    off = [abs(a - b) / b for a, b in ((w, sw), (h, sh))]
    if max(off) <= SIZE_TOLERANCE:
        return []
    return [
        f"the tracker is set up for a {w:.0f} x {h:.0f} mm screen, but this screen is {sw:.0f} x {sh:.0f} mm",
    ]


def _screen_size_mm() -> Optional[Tuple[float, float]]:
    """Physical size of the main screen, from Qt (macOS reports it from the display itself)."""
    try:
        from PySide6.QtGui import QGuiApplication

        app = QGuiApplication.instance() or QGuiApplication([])
        size = app.primaryScreen().physicalSize()
        return (size.width(), size.height()) if size.width() > 0 and size.height() > 0 else None
    except Exception:
        return None


def _check_display_area(et) -> bool:
    try:
        area = et.get_display_area()
    except Exception as exc:
        print(f"Display     could not read the display area: {exc}")
        return True
    screen = _screen_size_mm()
    line = f"Display     tracker set up for {area.width:.0f} x {area.height:.0f} mm"
    if screen:
        line += f"; main screen is {screen[0]:.0f} x {screen[1]:.0f} mm"
    print(line)
    problems = display_area_problems((area.width, area.height), screen)
    for problem in problems:
        print(f"  ! {problem}.")
    if problems:
        print("    Gaze will miss more and more towards the screen edges. Open Tobii Pro Eye Tracker")
        print("    Manager > Display Setup, enter this screen's size and where the tracker is mounted,")
        print("    then calibrate again in the app (F2).")
    return not problems


def main() -> int:
    ok = True
    print(f"Python      {platform.python_version()} ({platform.machine()})")
    if sys.version_info[:2] != (3, 10):
        print("  ! tobii-research only works on Python 3.10. Run: conda activate commu-aid")
        ok = False

    if sys.platform == "darwin":
        print(f"macOS       {platform.mac_ver()[0]}")
        registry = _mac_usb_registry()
        if registry is None:
            print("USB         could not run ioreg")
        else:
            devices = tobii_usb_devices(registry)
            if devices:
                print(f"USB         Mac sees: {', '.join(devices)}")
            else:
                ok = False
                print("USB         the Mac does not see a Tobii device on USB")
                print("  ! Plug the tracker's own USB-A cable straight into the Mac (through Tobii's")
                print("    USB-C to USB-A adapter), not through a hub or monitor. Unplug it, wait 5 s,")
                print("    plug it back in. If macOS asks to allow the accessory, choose Allow.")

    try:
        import tobii_research as tr
    except ImportError:
        print("SDK         tobii-research is not installed: pip install -r requirements-tobii.txt")
        return 1
    print(f"SDK         tobii-research {getattr(tr, '__version__', '?')}")

    trackers = tr.find_all_eyetrackers()
    if not trackers:
        print("Trackers    none found")
        print("  ! Open Tobii Pro Eye Tracker Manager. If the Spark is not listed, press + (top right)")
        print("    to install its driver. If Install is greyed out (newer macOS), install the")
        print("    Tobii Pro Spark runtime from https://connect.tobii.com/s/spark-downloads instead.")
        print("    Then unplug and replug the tracker; restart the Mac if it is still not found.")
        return 1
    for et in trackers:
        print(f"Tracker     {et.model}  serial {et.serial_number}  firmware {et.firmware_version}")
        print(f"            {et.address}")
    ok = _check_display_area(trackers[0]) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
