"""The night merge (src/overdrive/nightmerge.py): shaken noisy frames come back aligned and cleaner."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    import numpy as np
except ImportError:          # the image has it; a developer machine may not
    np = None


@unittest.skipIf(np is None, "numpy not installed")
class NightMergeTest(unittest.TestCase):
    W, H = 320, 240

    def scene(self):
        y, x = np.mgrid[0:self.H, 0:self.W]
        luma = 100 + 60 * np.sin(x / 9.0) * np.cos(y / 13.0) + (x > 160) * 40
        return luma.astype(np.float32)

    def frame(self, luma, rng, dy=0, dx=0, noise=12):
        y = np.roll(np.roll(luma, dy, 0), dx, 1) + rng.normal(0, noise, luma.shape)
        uv = np.full((self.H // 2, self.W // 2, 2), 128.0) + rng.normal(0, noise / 2, (self.H // 2, self.W // 2, 2))
        return np.concatenate([np.clip(y, 0, 255).astype(np.uint8).reshape(-1),
                               np.clip(uv, 0, 255).astype(np.uint8).reshape(-1)])

    def test_aligns_and_cleans(self):
        from overdrive.nightmerge import merge
        rng = np.random.default_rng(3)
        luma = self.scene()
        shifts = [(3, -2), (-4, 5), (2, 2), (0, 0), (-1, -3), (5, 1), (-2, 4)]
        frames = [self.frame(luma, rng, dy, dx) for dy, dx in shifts]
        out = merge(frames, self.W, self.H)
        ref = frames[len(frames) // 2][:self.W * self.H].reshape(self.H, self.W).astype(np.float32)
        merged = out[:self.W * self.H].reshape(self.H, self.W).astype(np.float32)
        inner = (slice(16, -16), slice(16, -16))
        err_single = np.abs(ref - luma)[inner].mean()
        err_merged = np.abs(merged - luma)[inner].mean()
        self.assertLess(err_merged, err_single * 0.6)

    def test_moving_thing_leaves_no_ghost(self):
        from overdrive.nightmerge import merge
        rng = np.random.default_rng(4)
        luma = self.scene()
        frames = []
        for i in range(7):
            f = luma.copy()
            if i != 3:
                f[60:120, 20 + i * 10:60 + i * 10] = 250      # a bright thing crossing, not in the reference
            frames.append(self.frame(f, rng, noise=4))
        out = merge(frames, self.W, self.H)
        merged = out[:self.W * self.H].reshape(self.H, self.W).astype(np.float32)
        # where the thing passed but the reference has none, the merge keeps the reference
        self.assertLess(np.abs(merged[70:110, 100:130] - luma[70:110, 100:130]).mean(), 15)

    def test_single_frame(self):
        from overdrive.nightmerge import merge
        rng = np.random.default_rng(5)
        f = self.frame(self.scene(), rng)
        self.assertTrue((merge([f], self.W, self.H) == f).all())


if __name__ == "__main__":
    unittest.main()
