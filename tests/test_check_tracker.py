from commu_aid.check_tracker import tobii_usb_devices

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
