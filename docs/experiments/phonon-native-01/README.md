# Phonon on the physical Pixel 5

On October 21, 2026, Phonon 31M generated speech on the **Pixel 5 CPU** and an
isolated Android debug service played the result while the phone remained locked.
All operations used authorized ADB access. No browser, user unlock, microphone,
cloud inference or paid service was needed.

The [repeatable native setup and `say` command](../../../android/speech-native/README.md)
are checked in. The earlier [desktop browser baseline](../phonon-01/desktop-baseline.json)
is separate and is not used as phone evidence.

## Synthesis measurements

The same synthetic text produced 180,480 mono samples at 24 kHz: **7.52 seconds
of speech**. Each trial created a fresh native process/model handle; the filesystem
cache was warm from asset installation or earlier runs. These are short smoke
measurements on an otherwise idle phone, not cold-boot or endurance benchmarks.

| CPU threads / trial | Model load | First callback after synthesis starts | Generation time | Audio seconds / compute second |
| --- | --- | --- | --- | --- |
| 2 / initial | 184 ms | 444 ms | 3.134 s | 2.40× |
| 2 / repeat | 128 ms | 479 ms | 3.184 s | 2.36× |
| 1 | 123 ms | 333 ms | 3.481 s | 2.16× |

The waveform has RMS approximately 0.0661 and peak approximately 0.4281 on the
normalized float scale. The pulled PCM16 WAV was separately checked for valid
format, frame count and nonzero audio. [Download/listen to the actual Pixel-generated WAV](pixel-generated.wav).

Text: “Hello. I am your home robot. My voice is running directly on this Pixel
phone. Please turn left, then stop.”

These callback measurements exclude model loading. The current wrapper writes a
complete WAV before playback, so **callback latency is not end-to-end speech
onset**. Integrating the callback directly with streaming AudioTrack is future work.

## Playback and cancellation

The final helper uses AudioTrack frame progress rather than only a media-player
completion callback. It reported:

- all **180,480 / 180,480 frames** played, over **7,632 ms** for the 7,520 ms WAV;
- built-in speaker route, media volume **6/25**, half track gain;
- **keyguard locked throughout**;
- cancellation of a second playback after approximately one second, with
  **22,560 frames** played at 1,022 ms rather than the whole utterance;
- original media volume restored to **0**, foreground playback service stopped,
  audio focus and the playback wake lock released.

An end-to-end run of `say_phone.py` then generated a different 5.28-second
utterance in 2.377 seconds and played all **126,720 frames** while locked. The
wrapper verified the transferred WAV's SHA-256 before starting playback and
removed its temporary prompt/audio files afterward. Its text-free measurements
are in [say-command.json](say-command.json).

The checks establish native synthesis and Android speaker-route playback progress.
No person or calibrated microphone measured the physical acoustic output at the
speaker, so acoustic quality, loudness and mouth-to-ear latency are not claimed.
No microphone or S23 test is included.

## A useful failure caught during validation

The initial stdin/tee ADB transfer truncated a WAV even though its header still
declared the full duration. A media-player completion event alone misleadingly
appeared successful. Strict file-length checks caught the mismatch. The final
workflow uses an on-device copy into the debug app's storage, checks identical
hashes and requires AudioTrack's played-frame count to reach the expected length.
The early completion events are not accepted playback evidence.

A separate synthesis cancellation test requested stopping after 24,000 samples
(one second). This runtime delivered a 48,000-sample callback before stopping,
so callback cancellation is batch-granular in this configuration. That test must
not be described as one-second generation cancellation. Playback cancellation
was checked independently as described above.

## Reproducibility and limits

- `ptts-ffi` v0.4.0, source `f07d7952db0c6127d5e4bc3f41c82b3304b6b5aa`.
- Apache-2.0 English model `gradium/phonon-31m-en`, pinned revision
  `541f5752bc3c79583068bb205bfda5eb39aaa08a`, q8/default voice.
- ARM64 Android API 26+, Rust 1.93.1, cargo-ndk 4.1.2, Android NDK r29.
- `dotprod` and `fp16` were present in the phone's reported CPU features.
- Android 14, no browser/NPU involvement, no changes to screen credentials or
  other applications' data. The player has no network/microphone/camera/location
  permission. The device serial and unrelated diagnostics are not published.

Camera/ASR concurrency, sustained power/heat, Bluetooth/headsets, microphone
recognition, streaming playback and an autonomous Android brain remain untested.
The next voice experiment can feed this synthetic WAV from PC speakers into a
Pixel-hosted recognizer; that will test the actual microphone path separately
from direct PCM injection.

[Manifest and audio hash](manifest.json), [initial synthesis](pixel-metrics.json),
[repeat](pixel-metrics-repeat.json), [one thread](pixel-metrics-one-thread.json),
[synthesis cancellation](pixel-metrics-cancel.json),
[completed playback](pixel-playback-completed.json),
[cancelled playback](pixel-playback-cancelled.json).
