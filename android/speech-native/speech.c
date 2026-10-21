// SPDX-License-Identifier: Apache-2.0
// Native Android CPU test. No network, microphone, browser or screen access.
#include "ptts.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

typedef struct {
  FILE *wav;
  size_t samples, cancel_after;
  double start_ms, first_ms, sum_squares, peak;
} Capture;

static double now_ms(void) {
  struct timespec t;
  clock_gettime(CLOCK_MONOTONIC, &t);
  return t.tv_sec * 1000.0 + t.tv_nsec / 1000000.0;
}

static void le16(FILE *f, unsigned value) {
  fputc(value & 255, f); fputc((value >> 8) & 255, f);
}

static void le32(FILE *f, unsigned value) {
  le16(f, value & 65535); le16(f, value >> 16);
}

static void wav_header(FILE *f, size_t samples) {
  rewind(f);
  fwrite("RIFF", 1, 4, f); le32(f, 36 + samples * 2);
  fwrite("WAVEfmt ", 1, 8, f); le32(f, 16); le16(f, 1); le16(f, 1);
  le32(f, 24000); le32(f, 48000); le16(f, 2); le16(f, 16);
  fwrite("data", 1, 4, f); le32(f, samples * 2);
}

static bool capture(const float *pcm, size_t count, void *user) {
  Capture *c = user;
  if (!c->samples) c->first_ms = now_ms() - c->start_ms;
  for (size_t i = 0; i < count; ++i) {
    if (!isfinite(pcm[i])) return false;
    double sample = fmax(-1.0, fmin(1.0, pcm[i]));
    c->sum_squares += sample * sample;
    if (fabs(sample) > c->peak) c->peak = fabs(sample);
    le16(c->wav, (unsigned)(unsigned short)(short)lrint(sample * 32767));
    ++c->samples;
  }
  return !ferror(c->wav) && (!c->cancel_after || c->samples < c->cancel_after);
}

int main(int argc, char **argv) {
  if (argc < 5 || argc > 6) {
    fprintf(stderr, "usage: phonon-phone MODEL_DIR TEXT_FILE OUTPUT.wav METRICS.json [CANCEL_AFTER_SAMPLES]\n");
    return 2;
  }
  FILE *input = fopen(argv[2], "rb");
  if (!input) { perror("text"); return 2; }
  char text[2049]; size_t length = fread(text, 1, 2048, input);
  if (!length || !feof(input)) { fclose(input); fprintf(stderr, "text must contain 1..2047 bytes\n"); return 2; }
  fclose(input); text[length] = 0;
  if (!getenv("RAYON_NUM_THREADS")) setenv("RAYON_NUM_THREADS", "2", 1);
  double load_start = now_ms();
  PttsHandle *h = ptts_new(argv[1], PTTS_UNIT_CPU, "en");
  double load_ms = now_ms() - load_start;
  if (!h) { fprintf(stderr, "model load failed: %s\n", ptts_last_error(NULL)); return 3; }
  Capture c = {0};
  c.cancel_after = argc == 6 ? strtoull(argv[5], NULL, 10) : 0;
  c.wav = fopen(argv[3], "wb");
  if (!c.wav) { perror("wav"); ptts_free(h); return 2; }
  wav_header(c.wav, 0);
  c.start_ms = now_ms();
  PttsResult result = {0};
  bool ok = ptts_speak(h, text, capture, &c, &result);
  double elapsed = now_ms() - c.start_ms;
  wav_header(c.wav, c.samples); fclose(c.wav);
  if (!ok) fprintf(stderr, "synthesis returned error: %s\n", ptts_last_error(h));
  FILE *report = fopen(argv[4], "wb");
  if (!report) { perror("metrics"); ptts_free(h); return 2; }
  fprintf(report, "{\n  \"runtime\": \"ptts-ffi@0.4.0\",\n  \"backend\": \"native_android_cpu\",\n  \"threads\": %s,\n  \"load_ms\": %.6f,\n  \"first_callback_ms\": %.6f,\n  \"generation_wall_ms\": %.6f,\n  \"sample_rate_hz\": 24000,\n  \"samples\": %zu,\n  \"audio_seconds\": %.6f,\n  \"audio_seconds_per_compute_second\": %.6f,\n  \"rms\": %.9f,\n  \"peak\": %.9f,\n  \"library_ok\": %s,\n  \"cancellation_requested\": %s,\n  \"library_frames\": %u,\n  \"library_first_audio_ms\": %.6f,\n  \"library_total_ms\": %.6f\n}\n",
    getenv("RAYON_NUM_THREADS"), load_ms, c.first_ms, elapsed, c.samples, c.samples / 24000.0,
    c.samples / 24.0 / elapsed, c.samples ? sqrt(c.sum_squares / c.samples) : 0,
    c.peak, ok ? "true" : "false", c.cancel_after ? "true" : "false", result.frames, result.ttfa_ms, result.total_ms);
  fclose(report); ptts_free(h);
  printf("native speech: %zu samples, %.3f s audio, %.3f ms generation, %.3f ms first callback\n", c.samples, c.samples / 24000.0, elapsed, c.first_ms);
  return ok && c.samples > 0 ? 0 : 4;
}
