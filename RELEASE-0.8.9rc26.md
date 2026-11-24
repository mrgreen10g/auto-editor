# 0.8.9rc26
- Fight panels use the dark red/blue diagonal styling of pair transitions, including numeric information tiles in portrait Shorts.
- “Без вставок” disables every gameplay insert, including explicit and manual clips, without reducing information cards; footage search/review is no longer required in this mode.
- Landscape presenter recordings in Shorts receive a face-guided 9:16 crop without stretching. Existing SDR conversion remains before composition for iPhone HDR input.
- Desktop preflight dialog and Mini App portrait review provide horizontal/vertical position, zoom, reset, per-source selection and persistent settings. Vertical movement is bounded by source edges; zoom creates room for adjustment.
- Microphone-prepared sources retain the original camera's framing settings. Preview caches change when framing changes.
- Reference IMG_1887.MOV: 1920×1080 HLG, 166.89 seconds. Five sampled frames locate the presenter around normalized x=0.517. Both single-source and multipart render paths tested on a four-second excerpt, retaining sound and duration.
- A missing or uncertain face detection requests manual confirmation instead of asserting a reliable speaker location.
