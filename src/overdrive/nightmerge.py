"""Night photos: a burst of frames, aligned and merged into one picture with much less grain.

In a dim room the front camera runs at 60 ms and its highest gain: one frame is mostly grain. Holding still for a
second gives a dozen frames of the same scene; averaging N of them lowers the grain by about the square root of N. Two
things stop a plain average: the hand shakes (the frames are shifted against each other) and things move (a plain
average leaves ghosts). So:
  1. every frame is aligned to the middle one: a whole-picture shift, which is what a hand holding a tablet makes. The
     phase correlation of the luma at half size gives a few candidate shifts (a repeating pattern gives several
     peaks); each is checked at full size with its 8 neighbours on a central crop, and the best match wins;
  2. the frames are merged block by block (8x8): a block that differs from the reference by more than the noise does
     moved, and that frame is left out there; elsewhere all frames count.

Frames are NV12 (Y plane then interleaved UV at half size), as numpy uint8 arrays of height * 3 / 2 rows.
"""
import numpy as np

BLOCK = 8


def _split(frame, width, height):
    y = frame[:height * width].reshape(height, width)
    uv = frame[height * width:height * width * 3 // 2].reshape(height // 2, width // 2, 2)
    return y, uv


def _window(h, w):
    return np.outer(np.hanning(h), np.hanning(w)).astype(np.float32)


def shift_candidates(ref_small, img_small, window, count=5):
    """Shifts (dy, dx) that may move img onto ref: the highest peaks of the phase correlation, each with a sub-pixel
    position (parabola fit). A repeating pattern (tiles, cloth) gives several peaks; the full-size check picks."""
    a = np.fft.rfft2((ref_small - ref_small.mean()) * window)
    b = np.fft.rfft2((img_small - img_small.mean()) * window)
    r = a * np.conj(b)
    r /= np.abs(r) + 1e-6
    c = np.fft.irfft2(r, s=ref_small.shape)
    h, w = c.shape

    def refine(m1, m0, p1):
        d = m1 - 2 * m0 + p1
        return 0.0 if abs(d) < 1e-9 else 0.5 * (m1 - p1) / d

    out = []
    work = c.copy()
    for _ in range(count):
        py, px = np.unravel_index(int(np.argmax(work)), work.shape)
        dy = py + refine(c[(py - 1) % h, px], c[py, px], c[(py + 1) % h, px])
        dx = px + refine(c[py, (px - 1) % w], c[py, px], c[py, (px + 1) % w])
        out.append((dy - h if dy > h / 2 else dy, dx - w if dx > w / 2 else dx))
        work[max(py - 2, 0):py + 3, max(px - 2, 0):px + 3] = -np.inf
    return out


def shift_between(ref_small, img_small, window):
    """The strongest peak of the phase correlation (see shift_candidates)."""
    return shift_candidates(ref_small, img_small, window, 1)[0]


def best_shift(ref, img, candidates_half):
    """Of the candidates (in half-size pixels), the full-size shift that matches best (each checked with its 8
    neighbours, see refine_shift)."""
    best, best_err = (0, 0), None
    for dy, dx in candidates_half:
        shift, err = refine_shift(ref, img, int(round(dy * 2)), int(round(dx * 2)), with_error=True)
        if err is not None and (best_err is None or err < best_err):
            best, best_err = shift, err
    return best


def refine_shift(ref, img, dy, dx, size=384, with_error=False):
    """The half-size estimate (dy, dx) checked at full size: of it and its 8 neighbours, the one with the smallest
    difference on a central crop (an error of one pixel left strong edges misaligned, and the merge then saw motion)."""
    h, w = ref.shape
    cy, cx, r = h // 2, w // 2, min(size, h // 2 - 8, w // 2 - 8) // 2
    target = ref[cy - r:cy + r, cx - r:cx + r].astype(np.int16)
    best, best_err = (dy, dx), None
    for ddy in (-1, 0, 1):
        for ddx in (-1, 0, 1):
            sy, sx = dy + ddy, dx + ddx
            y0, x0 = cy - r - sy, cx - r - sx
            if y0 < 0 or x0 < 0 or y0 + 2 * r > h or x0 + 2 * r > w:
                continue
            err = np.abs(img[y0:y0 + 2 * r, x0:x0 + 2 * r].astype(np.int16) - target).mean()
            if best_err is None or err < best_err:
                best, best_err = (sy, sx), err
    return (best, best_err) if with_error else best


def _shift(plane, dy, dx):
    """plane moved by whole pixels (dy, dx), edges repeated."""
    h, w = plane.shape[:2]
    ys = np.clip(np.arange(h) - dy, 0, h - 1)
    xs = np.clip(np.arange(w) - dx, 0, w - 1)
    return plane[ys][:, xs]


def _blocks(plane, b=BLOCK):
    h, w = plane.shape
    hb, wb = h // b, w // b
    return plane[:hb * b, :wb * b].reshape(hb, b, wb, b).mean(axis=(1, 3))


def _expand(weights, h, w, b=BLOCK):
    full = np.repeat(np.repeat(weights, b, axis=0), b, axis=1)
    out = np.ones((h, w), np.float32)
    out[:full.shape[0], :full.shape[1]] = full
    if full.shape[0] < h:
        out[full.shape[0]:, :full.shape[1]] = full[-1:, :]
    if full.shape[1] < w:
        out[:, full.shape[1]:] = out[:, full.shape[1] - 1:full.shape[1]]
    return out


def merge(frames, width, height, max_shift=0.05):
    """The NV12 frames merged into one NV12 frame (uint8 array). Frames shifted by more than max_shift of the picture
    width (a deliberate move, not a shaking hand) are left out."""
    frames = [np.asarray(f, dtype=np.uint8).reshape(-1) for f in frames]
    if len(frames) == 1:
        return frames[0].copy()
    ref_i = len(frames) // 2
    ref_y, ref_uv = _split(frames[ref_i], width, height)
    small = lambda y: y[::2, ::2].astype(np.float32)
    ref_small = small(ref_y)
    window = _window(*ref_small.shape)

    ref_b = _blocks(ref_y.astype(np.float32))
    acc_y = ref_y.astype(np.float32)
    acc_uv = ref_uv.astype(np.float32)
    w_y = np.ones((height, width), np.float32)
    w_uv = np.ones((height // 2, width // 2), np.float32)

    aligned = []
    for i, f in enumerate(frames):
        if i == ref_i:
            continue
        y, uv = _split(f, width, height)
        dy, dx = best_shift(ref_y, y, shift_candidates(ref_small, small(y), window))
        if abs(dx) > max_shift * width or abs(dy) > max_shift * height:
            continue
        aligned.append((_shift(y, dy, dx), _shift(uv, dy // 2, dx // 2)))

    if not aligned:
        return frames[ref_i].copy()

    # how much an 8x8 block of a still scene differs between two frames: the noise, robustly from the median block
    diffs = [np.abs(_blocks(y.astype(np.float32)) - ref_b) for y, _ in aligned]
    noise = float(np.median(np.stack(diffs))) + 0.5
    t1, t2 = 2.5 * noise, 5.0 * noise

    for (y, uv), d in zip(aligned, diffs):
        wb = np.clip((t2 - d) / (t2 - t1), 0.0, 1.0).astype(np.float32)
        wy = _expand(wb, height, width)
        wc = _expand(wb, height // 2, width // 2, BLOCK // 2)
        acc_y += wy * y
        w_y += wy
        acc_uv += wc[..., None] * uv
        w_uv += wc

    out = np.empty(width * height * 3 // 2, np.uint8)
    out[:width * height] = np.clip(acc_y / w_y + 0.5, 0, 255).astype(np.uint8).reshape(-1)
    out[width * height:] = np.clip(acc_uv / w_uv[..., None] + 0.5, 0, 255).astype(np.uint8).reshape(-1)
    return out
