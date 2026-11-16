// The sharpening of the camera pictures (libcamera patch 0049, colourGrade() of the IPU3 pipeline), outside libcamera:
// the plain loop it had first, the row kernel and the bands it has now. Says whether the two give the same bytes
// (sizes with odd widths and strides, every strength, flat and extreme pictures) and how long a 2560x1920 frame takes.
//
//   g++ -O2 -std=c++17 -pthread tools/dev/sharpen_bench.cpp -o /tmp/sharpen_bench && /tmp/sharpen_bench
//
// Ends with status 1 when a byte differs. sharpenRow() and banded() here are the code of the patch: change both.
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <thread>
#include <vector>

static void serial(uint8_t *y, unsigned width, unsigned height, unsigned stride, int amount)
{
	std::vector<uint8_t> prevRow(y, y + width), curRow(width);
	for (unsigned int r = 1; r + 1 < height; r++) {
		uint8_t *row = y + static_cast<size_t>(r) * stride;
		const uint8_t *next = row + stride;
		std::copy(row, row + width, curRow.begin());
		for (unsigned int x = 1; x + 1 < width; x++) {
			const int c = curRow[x];
			const int blur = (prevRow[x] + next[x] + curRow[x - 1] + curRow[x + 1] + 4 * c) / 8;
			int d = c - blur;
			d = d > 1 ? d - 1 : (d < -1 ? d + 1 : 0);
			const int v = c + (d * amount) / 16;
			row[x] = static_cast<uint8_t>(v < 0 ? 0 : (v > 255 ? 255 : v));
		}
		prevRow.swap(curRow);
	}
}


#if defined(__SSE2__)
#include <emmintrin.h>
#endif

/* One row of the unsharp mask: out[1..width-2] from the rows above, at and below it (all three unmodified). The same
 * numbers as the plain loop: the blur is a sum of non-negative values (a shift), the cored difference is taken as a
 * magnitude and a sign, so that its scaling rounds towards zero as the division did. */
static void sharpenRow(uint8_t *out, const uint8_t *above, const uint8_t *cur, const uint8_t *below, unsigned width, int amount)
{
	unsigned x = 1;
#if defined(__SSE2__)
	const __m128i zero = _mm_setzero_si128();
	const __m128i one = _mm_set1_epi16(1);
	const __m128i gain = _mm_set1_epi16(static_cast<short>(amount));
	for (; x + 16 < width; x += 16) {
		const __m128i c8 = _mm_loadu_si128(reinterpret_cast<const __m128i *>(cur + x));
		const __m128i a8 = _mm_loadu_si128(reinterpret_cast<const __m128i *>(above + x));
		const __m128i b8 = _mm_loadu_si128(reinterpret_cast<const __m128i *>(below + x));
		const __m128i l8 = _mm_loadu_si128(reinterpret_cast<const __m128i *>(cur + x - 1));
		const __m128i r8 = _mm_loadu_si128(reinterpret_cast<const __m128i *>(cur + x + 1));
		__m128i res[2];
		for (int half = 0; half < 2; half++) {
			auto widen = [&](const __m128i &v) { return half ? _mm_unpackhi_epi8(v, zero) : _mm_unpacklo_epi8(v, zero); };
			const __m128i c = widen(c8);
			__m128i sum = _mm_add_epi16(_mm_add_epi16(widen(a8), widen(b8)), _mm_add_epi16(widen(l8), widen(r8)));
			sum = _mm_add_epi16(sum, _mm_slli_epi16(c, 2));
			const __m128i blur = _mm_srli_epi16(sum, 3);
			const __m128i d = _mm_sub_epi16(c, blur);
			const __m128i neg = _mm_cmpgt_epi16(zero, d);                    /* all ones where d < 0 */
			__m128i mag = _mm_sub_epi16(_mm_xor_si128(d, neg), neg);          /* |d| */
			mag = _mm_subs_epu16(mag, one);                                  /* coring: one level is noise */
			const __m128i step = _mm_srli_epi16(_mm_mullo_epi16(mag, gain), 4);
			const __m128i delta = _mm_sub_epi16(_mm_xor_si128(step, neg), neg); /* the sign back */
			res[half] = _mm_add_epi16(c, delta);
		}
		_mm_storeu_si128(reinterpret_cast<__m128i *>(out + x), _mm_packus_epi16(res[0], res[1]));
	}
#endif
	for (; x + 1 < width; x++) {
		const int c = cur[x];
		const int blur = (above[x] + below[x] + cur[x - 1] + cur[x + 1] + 4 * c) / 8;
		int d = c - blur;
		d = d > 1 ? d - 1 : (d < -1 ? d + 1 : 0);
		const int v = c + (d * amount) / 16;
		out[x] = static_cast<uint8_t>(v < 0 ? 0 : (v > 255 ? 255 : v));
	}
}

/* The same picture, the rows split over the processors: each band starts from a copy of the row above it and ends on a
 * copy of the row below it, both taken before any band writes. */
static void banded(uint8_t *y, unsigned width, unsigned height, unsigned stride, int amount, unsigned bands)
{
	if (height < 3 || width < 3)
		return;
	const unsigned rows = height - 2;                       /* rows 1 .. height-2 are written */
	bands = std::clamp(bands, 1U, std::min(4U, rows));
	std::vector<std::vector<uint8_t>> above(bands), below(bands);
	std::vector<unsigned> first(bands + 1);
	for (unsigned b = 0; b <= bands; b++)
		first[b] = 1 + rows * b / bands;
	for (unsigned b = 0; b < bands; b++) {
		const uint8_t *a = y + static_cast<size_t>(first[b] - 1) * stride;
		const uint8_t *z = y + static_cast<size_t>(first[b + 1]) * stride;
		above[b].assign(a, a + width);
		below[b].assign(z, z + width);
	}
	auto job = [&](unsigned b) {
		std::vector<uint8_t> prevRow = above[b], curRow(width);
		for (unsigned r = first[b]; r < first[b + 1]; r++) {
			uint8_t *row = y + static_cast<size_t>(r) * stride;
			const uint8_t *next = r + 1 < first[b + 1] ? row + stride : below[b].data();
			std::copy(row, row + width, curRow.begin());
			sharpenRow(row, prevRow.data(), curRow.data(), next, width, amount);
			prevRow.swap(curRow);
		}
	};
	std::vector<std::thread> workers;
	for (unsigned b = 1; b < bands; b++)
		workers.emplace_back(job, b);
	job(0);
	for (auto &w : workers)
		w.join();
}

int main()
{
	const unsigned sizes[][3] = {{2560, 1920, 2560}, {1280, 960, 1280}, {641, 479, 704}, {3, 3, 8}, {5, 4, 8}, {64, 7, 64}};
	int bad = 0;
	for (auto &s : sizes) {
		const unsigned w = s[0], h = s[1], stride = s[2];
		std::vector<uint8_t> src(static_cast<size_t>(stride) * h);
		for (int picture = 0; picture < 4; picture++) {
		srand(w * 31 + h);
		for (size_t i = 0; i < src.size(); i++)   /* noise, black, white, the hardest edges */
			src[i] = picture == 0 ? rand() & 0xff : picture == 1 ? 0 : picture == 2 ? 255 : ((i / 3 + i / stride) & 1 ? 255 : 0);
		for (int amount : {0, 1, 8, 16, 31, 32, 47, 48}) {
			std::vector<uint8_t> a = src;
			serial(a.data(), w, h, stride, amount);
			for (unsigned bands = 1; bands <= 4; bands++) {
				std::vector<uint8_t> b = src;
				banded(b.data(), w, h, stride, amount, bands);
				if (a != b) { bad++; printf("DIFFERENT %ux%u amount %d bands %u\n", w, h, amount, bands); }
			}
		}
		}
	}
	printf("equivalence: %s\n", bad ? "FAILED" : "ok");
	std::vector<uint8_t> big(2560UL * 1920);
	for (auto &p : big) p = rand() & 0xff;
	for (unsigned bands = 0; bands <= 4; bands++) {
		auto t0 = std::chrono::steady_clock::now();
		for (int i = 0; i < 20; i++) {
			if (bands == 0) serial(big.data(), 2560, 1920, 2560, 16); else banded(big.data(), 2560, 1920, 2560, 16, bands);
		}
		double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count() / 20;
		printf("%s %u: %.1f ms per frame\n", bands ? "banded" : "serial", bands, ms);
	}
	return bad != 0;
}
