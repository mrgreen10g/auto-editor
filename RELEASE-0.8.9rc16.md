# 0.8.9rc16

- Automatically convert HDR HLG/PQ camera footage to SDR BT.709 before compositing, independently of optional creative color correction. Covers single/multiple host sources, desktop playback and mobile previews. SDR inputs bypass tone mapping.
- Select the compatible audio stream when newer iPhone recordings contain unsupported APAC spatial audio before an AAC track.
- Mobile draft settings now expose individual image, insertion, subtitle and sound overrides, applied after the selected preset and persisted with the project. Empty fields inherit the preset. Existing projects retain the montage editor settings panel.
- Validate override types, finite numbers, ranges and output dimensions. Test mobile save-to-project behavior, browser controls, HDR conversion using packaged FFmpeg, SDR tagging and audio selection.
