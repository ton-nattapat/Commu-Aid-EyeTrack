from commu_aid.check_tracker import tobii_usb_devices, windows_tobii_devices

IOREG = """\
+-o Root  <class IORegistryEntry, id 0x100000100, retain 30>
  +-o AppleT8112USBXHCI@00000000  <class AppleT8112USBXHCI, id 0x1000002c1, registered>
    +-o Tobii Pro Spark@00100000  <class IOUSBHostDevice, id 0x100000a11, registered>
    |   {
    |     "USB Product Name" = "Tobii Pro Spark"
    |     "idVendor" = 8452
    |   }
    +-o USB Receiver@00200000  <class IOUSBHostDevice, id 0x100000a22, registered>
    |   {
    |     "idVendor" = 1133
    |   }
"""


def test_finds_tobii_by_name():
    assert tobii_usb_devices(IOREG) == ["Tobii Pro Spark"]


def test_finds_tobii_by_vendor_id():
    assert tobii_usb_devices(IOREG.replace("Tobii Pro Spark@", "Eye Tracker@")) == ["Eye Tracker"]


def test_no_tobii():
    assert tobii_usb_devices(IOREG.replace("Tobii Pro Spark@", "Keyboard@").replace("8452", "1452")) == []


PNP = """\
USB\\ROOT_HUB30\\4&1B2C3D&0&0|USB Root Hub (USB 3.0)
USB\\VID_2104&PID_0313\\TPE01-100205130364|Tobii Pro Spark
USB\\VID_2104&PID_0313&MI_00\\6&2A&0&0000|USB Input Device
USB\\VID_046D&PID_C52B\\5&1A&0&3|USB Composite Device
"""


def test_windows_finds_tobii_by_vendor_id():
    assert windows_tobii_devices(PNP) == ["Tobii Pro Spark", "USB Input Device"]
    assert windows_tobii_devices(PNP.replace("2104", "1234")) == ["Tobii Pro Spark"]  # by name
    assert windows_tobii_devices(PNP.replace("2104", "1234").replace("Tobii", "Eye")) == []


def test_display_area_matches_screen():
    from commu_aid.check_tracker import display_area_problems

    assert display_area_problems((301, 196), (302, 197)) == []


def test_display_area_for_another_screen_is_reported():
    from commu_aid.check_tracker import display_area_problems

    problems = display_area_problems((527, 296), (302, 197))  # set up for a 24" monitor, used on a 13" MacBook
    assert len(problems) == 1 and "527 x 296" in problems[0]


def test_display_area_without_screen_size():
    from commu_aid.check_tracker import display_area_problems

    assert display_area_problems((301, 196), None) == []
