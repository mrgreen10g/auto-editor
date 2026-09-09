# Third-party components

The application bundle includes third-party software with its own license terms. Its build script copies installed distribution license files into `licenses/`.

- Python / tkinter — https://www.python.org/ — PSF and Tcl/Tk licenses.
- NumPy — https://github.com/numpy/numpy — BSD-3-Clause.
- SciPy — https://github.com/scipy/scipy — BSD-3-Clause, with bundled library notices.
- Pillow — https://github.com/python-pillow/Pillow — HPND.
- eSpeak NG — https://github.com/espeak-ng/espeak-ng — GPL-3.0-or-later; Russian voice data are included. Source and build instructions are available upstream.
- espeakng-loader — https://github.com/thewh1teagle/espeakng-loader — loader MIT; bundled eSpeak NG retains its own license.
- FFmpeg / imageio-ffmpeg — https://github.com/imageio/imageio-ffmpeg — wrapper BSD-2-Clause; bundled FFmpeg and codecs retain their upstream licenses. See the bundled FFmpeg license and `ffmpeg -version` build configuration.
- num2words — https://github.com/savoirfairelinux/num2words — LGPL-2.1.
- PyInstaller — https://github.com/pyinstaller/pyinstaller — GPL-2.0-or-later with its bootloader exception.

No user recordings, scripts, media files or local project files are included in the source repository or generic application bundle.

## Added in 0.2

- RapidOCR ONNX Runtime 1.4.4 (Apache-2.0), including distributed PaddleOCR detection/recognition model files and their upstream notices.
- ONNX Runtime 1.22.1 (MIT): local CPU inference; telemetry disabled before inference-session creation.
- OpenCV Python 4.11 (Apache-2.0; packaged third-party notices also apply).
- Shapely (BSD-3-Clause) and its GEOS components (LGPL-2.1); pyclipper (MIT / Clipper notices); PyYAML (MIT), protobuf (BSD-3-Clause).

Dependency license files are copied into the Windows bundle's licenses directory. Models are included in the package; user media is not sent to a recognition service.

## Added in 0.3

OpenCV's packaged Haar cascade data is included for local presenter orientation checks. The original notices embedded in the cascade XML files remain intact. Team logos are supplied by the user; the application fits and resizes them without generating brand details.
