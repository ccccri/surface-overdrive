# Spike results

Findings on a freshly installed and updated Kinoite 44 (kernel 7.2.8-200.fc44, stock, Secure Boot on) on the Surface Go 1824,
checked on 2026-10-06 against the kernel sources of tag `v7.2.8` and of mainline `master`.
Read-only so far: nothing was changed on the tablet.

## S1: NFC without a kernel patch: **partly answered, a module is very likely needed**
- `NXP3001:00` is enumerated as an i2c client (`i2c-NXP3001:00`) and stays **unbound**.
- `nxp_nci_i2c` only lists the ACPI ids `NXP1001`, `NXP1002` and `NXP7471`.
- The i2c bus has **no `driver_override` attribute** (`/sys/bus/i2c/devices/*/driver_override` does not exist), so the stock driver cannot be forced onto the device.
- Creating a client by hand with `new_device` would produce one without the ACPI companion that supplies the GPIOs (IRQ and enable), so it is expected to fail. Still to confirm with root.
- Mainline `master` still lacks `NXP3001`, so the patch is still needed and still worth sending upstream.
- **Decision**: NFC stays a signed module built in CI (`nxp-nci_i2c` with the id and the read retry; the core poll-period patch is optional, see S3 style measurement).

## S2: which kernel patches are still needed: **partly answered**
| Patch | Result on 7.2.8 and mainline | Verdict |
|---|---|---|
| `ov8865` stale mode (`hw_mode`) | absent in both | **needed** |
| `ov8865` pixel rate | still derived from the MIPI clock (`mipi_pixel_rate`), not the real 72 MHz of the binned mode | **needed** |
| `ov8865` analogue gain step | control still declared with step 128 | **needed** |
| `ov8865` drop 800x600 | not checked yet | to check |
| `ov5693` 30 fps cap | stock still uses `rounddown(PIXEL_RATE / PPL / height, 30)`: the 60 fps default of the binned mode is still there | **needed** (a measurable effect still to confirm) |
| `intel_hid` volume hold | keymap still has `KE_IGNORE` for the release codes `0xC5` and `0xC7` | **needed** |
| `nxp-nci` poll period (`post_setup`) | absent | optional (power versus latency trade-off) |
| `nxp-nci` read retry | to confirm on hardware how often NACKs occur without it | to measure |

The camera graph already works on the stock 7.2.8 kernel: both sensors and the autofocus driver are bound and PipeWire shows
"Built-in Back Camera" and "Built-in Front Camera". The old `dw9719` problem of kernel 6.19 is confirmed gone from 7.2.
The stock modules are Fedora-signed; the project modules will be signed with our own key.

## S5: audio: **partly answered**
- Codec: Realtek **ALC298** on HDA (`HDA Intel PCH`). **No UCM profile** is involved: PipeWire uses its legacy mixer paths.
- **Speaker**: the hardware control `Speaker` is at 100% = 0 dB, and `Master` follows the PipeWire volume (72% at a 50% sink volume). The hardware has **no headroom** above PipeWire's 100%.
  The loudness gap therefore cannot be closed at mixer level: a software gain and equaliser stage is the right tool (the same approach Asahi uses for its speakers).
- **Microphone**: at PipeWire 100% the `Capture` control is +30 dB **and** `Internal Mic Boost` is +30 dB, so +60 dB in total. This **can** be fixed without a virtual device
  by lowering the default source volume or the mixer path, so the noise-suppression filter becomes optional, not a requirement.
- Still to do: decide where the speaker filter chain lives (PipeWire configuration in the image) and how the microphone default is made persistent.

## Still open
- **S3** (value of each libcamera patch), **S4** (own calibration) and **S6** (KCM bridge): need the build and calibration tooling first.
- **Tools on the tablet**: `podman`, `toolbox`, `skopeo`, `bootc`, `rpm-ostree` and `mokutil` are present; `cosign`, `media-ctl`, `v4l2-ctl` and `cam` are not.
  `bootc` being present means the rebase can use `bootc switch` instead of `rpm-ostree rebase`. To decide when writing the bootstrap.
