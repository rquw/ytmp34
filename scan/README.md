# PRISMO scan

PRISMO's camera reads QR codes and barcodes (zbar, no AI) and the computer you used last opens them:
links and text in Chrome, pictures in Preview / the photo viewer. Computer off or asleep: nothing happens.

Pi (`prismo-scan.py`) -> Oracle (`server.py`, `/scan/*`) -> Mac menu bar app or Windows tray app.

1. Pi: run `install-pi.sh` again. It prints the scan key at the end. Oracle picks the key up from the Pi by itself.
2. Mac: `bash scan/mac/install.sh` (needs the Xcode command line tools)
3. Windows: double-click `scan\windows\install.cmd`

Test without the camera, on the Pi: `python3 ~/prismo/prismo-scan.py test https://example.com`

Idle cost: one HTTPS request every 25 s per computer, no timers, no camera traffic while the window is closed.
