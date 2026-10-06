"""Check why the Tobii Pro Spark is or isn't found, without starting the app.

    python -m commu_aid.check_tracker

Prints the Python and SDK versions, what the Tobii SDK finds, and on macOS whether the Mac
itself sees a Tobii device on USB. Each problem comes with what to try next.
"""

from __future__ import annotations

import platform
import re
import subprocess
import sys
from typing import List, Optional

TOBII_USB_VENDOR_ID = 0x2104  # Tobii AB


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
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
