# Driver Guidance

Current development uses a USB serial converter for the IDT-85 reader, but
field installations may use different converters or native serial hardware.
Do not assume every site needs the same driver.

Windows may require a vendor USB-to-serial driver depending on the selected
converter chipset and industrial PC image.

Linux typically includes common USB serial drivers, but the service account
still needs permission to open the serial device. Many distributions use a
group such as `dialout`; others use a different group or udev policy.

Do not distribute proprietary drivers unless licensing, vendor source, and
redistribution rights are confirmed.
