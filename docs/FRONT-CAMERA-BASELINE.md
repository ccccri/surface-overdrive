# Front camera baseline (2026-11-04)

The state of the front camera (OV5693, CSI port 1) before the rebuild from scratch. Git tag `front-baseline-2026-11-04`
pins every file; this page lists what makes it up and how good it was, so the rebuild has numbers to beat.

User verdict: in a dim room with the desk lamp on, "decent, not acceptable". Without any light the camera struggles
badly (gain 5.75 at 60 ms, heavy grain). Ghosting at the strongest grain removal: acceptable.

## Pieces

Kernel (`patches/kernel/ov5693/`):
- 0001 cap 30 fps, 0002 pixel rate 160 MHz.

libcamera (`patches/libcamera/`, IPU3 pipeline and IPA), the ones that shape the front camera:
- 0002 AGC, 0003 BLC (+ Bayer noise reduction), 0004 CCM, 0006 LSC, 0009 tone mapping, 0023/0024 AWB locus.
- 0010/0036 offered sizes (front: 1280x960 and 2560x1920 only, full field of view), 0038 colour conversion by size
  (BT.709 from 2000 px wide, BT.601 below).
- 0015/0017/0025 AGC start and memory, 0031/0033/0034/0037 low light: frames up to 60 ms, digital gain up to 3x,
  shortest frame of 30 fps, flicker-safe exposure (multiples of 10 ms).
- 0026 XNR3 chroma (alpha 32, blending 2048), 0039 TNR3 hardware temporal denoise (on in light, off in the dark).
- Software temporal denoise in the pipeline handler: 0008, 0020, 0027, 0028, 0030, 0032, 0033, 0040.
- 0040 (2026-11-04): AGC hold band (changes under 8% made with the digital gain), brightness compensation of the
  previous output, noise remembered from still moments, measured for 8 brightness levels, blocks judged with their
  3x3 neighbourhood (thresholds 1.5x and 3x the level's noise), luma-guided chroma denoise in dim light.

Tuning: `image/rootfs/usr/share/libcamera/ipa/ipu3/ov5693.yaml`, the key values:
- Agc: relativeLuminanceTarget 0.20, maxExposureTime 60000, AeExposureModes 30 ms -> gain 2 -> 60 ms -> gain 4,
  constraint qLo 0.25 qHi 0.55 yTarget 0.09.
- BlackLevelCorrection: black [19, 27, 23, 19], binned [26, 31, 29, 26], bnr [1700, 24, 4, 8, 8, 10].
- ToneMapping: gamma 1.5, contrast 0.7. Lsc: 64 px cells, grid 41x31. Awb: locus of 7 points, one CCM at 5201 K.
- NoiseReduction: xnr3 [32, 32, 32, 0, 0, 0, 0, 0, 0, 0, 2048], tnr3 [1024, 1024, 768, 1280, 256, 0, 0], tnr3Dark 0.

User profile on the tablet (`~/.config/surface-overdrive/camera/ov5693.profile`): `min_width 2560`, `tnr 24 6`
(grain removal "maximum"). Software TNR levels (`src/overdrive/camera.py`): off (0,0), low (128,5), medium (96,5),
high (64,5), stronger (40,5, the front default), maximum (24,6).

## Measurements

Dim room, 60 ms, gain 1.25 (2560x1920, recordings in `build/ft/rec/`, offline harness `build/ft/harness/`):

| filter | still flicker | grain vs clean | chroma error |
|---|---|---|---|
| none | 1.88 | 1.33 | 0.84 |
| image of 2026-11-03 (0039), stronger | 0.86 | 1.16 | 0.66 |
| 0040, stronger | 0.67 | 1.05 | 0.53 |

Very dark (60 ms, gain 5.75): chroma blotches 3.38 -> 0.61 with 0040, flicker on the device 5.02 -> 0.77.
Timing on the Surface Go, 2560x1920 in the dark: sums 2.2, motion map 9.2, filter 16.4, chroma 10.6 ms (38 ms of a
60 ms frame, 16.9 fps, the exposure's limit); 1280x960: 22 ms. Camera service about 50% of one core.

## Known limits

- In the dark the picture is mostly gain: 60 ms at gain 5.75 plus digital gain, so luma grain stays even when the
  chroma is clean.
- The motion test still trades grain against trails; the trail metric of the harness is unreliable (it counts removed
  grain as trail), judge trails by eye (`build/ft/harness`, crops).
- XNR3 alpha 4-32 made no visible difference at gain 5.75.
