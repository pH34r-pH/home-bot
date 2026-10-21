# Pixel Phonon voice lab

An initial **on-device CPU speech experiment in Chrome**, using Gradium's official
`phonon-tts` WebAssembly runtime. The PC serves static assets over an ADB reverse
tunnel and receives explicit test measurements/WAV saves. It does not generate
speech. This is not yet the native Android robot app or an Android system voice.

The microphone is not requested or accessed. Speech recognition through
sherpa-onnx is the next, separate experiment; PC-speaker-to-Pixel-microphone tests
will need that recognizer and explicit microphone activation.

## Run

From this repository, with Node.js/npm, Python and Android platform tools:

```powershell
cd android/speech-prototype
npm ci --ignore-scripts --no-audit --no-fund
cd ../..
python scripts/prepare_speech.py
python scripts/serve_speech.py
```

In another terminal, substitute the authorized Pixel's ADB serial:

```powershell
adb devices -l
adb -s <PIXEL_SERIAL> reverse tcp:8875 tcp:8875
```

Unlock the Pixel and manually open **http://127.0.0.1:8875/** in Chrome. Keep it
foreground, choose two CPU threads initially, tap **Load Phonon**, then **Speak**.
The initial text is synthetic robot speech. **Stop** cancels generation and
closes playback. **Save test WAV to PC** explicitly saves the most recent
synthesized utterance under `artifacts/phonon-pixel-01/phone-generated.wav`.
Use synthetic text when saving test evidence.

The server binds only to PC loopback. No LAN firewall changes, account, paid API,
Unity, Unreal, Rust build or cloud inference are required for this browser trial.
The page's content policy permits connections only to its own origin. The server
sets the cross-origin isolation headers required for threaded WebAssembly.

## Reproducibility and evidence

- npm runtime: `phonon-tts@0.4.1`; exact registry integrity is in `package-lock.json`.
- Model: `gradium/phonon-31m-en`, revision
  `541f5752bc3c79583068bb205bfda5eb39aaa08a`, q8, default bundled voice.
- `prepare_speech.py` checks SHA-256 for config, tokenizer, weights and voice,
  including already-downloaded files. Assets are ignored under `models/`.
- Events contain a page-session UUID and platform so a desktop check cannot be
  mistaken for a phone result. No device serial, transcript or synthesized text
  is included. Local model assets and run artifacts are not committed.
- The page reports model load time, requested/actual threads, SIMD features,
  first-chunk latency, generation duration, generated audio duration and playback
  starvation count. Runtime-reported timing is preserved separately from wrapper
  timing. These are software measurements, not acoustic latency measurements.
- Playback is streamed with an initial 250 ms scheduling buffer. A real speaker
  or headset listening check is still required to establish audible output.

### Initial validation — October 21, 2026

Static assets, JavaScript/Python syntax, model integrity, cross-origin isolation,
file traversal rejection and unrelated-origin POST rejection passed. The existing
16 robot unit/API tests also pass.

A **Windows desktop browser software check**, using two WASM CPU threads and the
synthetic sentence “This is a desktop software check. The Pixel phone test is
separate.”, generated 4.48 seconds of audio in 1.050 seconds. The first client
audio chunk arrived in 54.7 ms, the audio context reported running, and playback
finished with zero reported starvation gaps. This is not a phone benchmark or a
microphone test. See the [desktop-only measurement](../../docs/experiments/phonon-01/desktop-baseline.json).

The browser test on the Pixel remains unvalidated: its ADB browser launch was
rejected by the execution approval policy while the phone was locked. A subsequent
[native CPU experiment](../../docs/experiments/phonon-native-01/README.md) successfully
generated and played speech on the locked Pixel over ADB, without using a browser.
Those native measurements are distinct from this page's Windows baseline.

The model caches in Chrome, and a loaded model generates without remote services.
This page still needs the local server to open/reload and to receive evidence;
it is not packaged as a standalone offline app. Browser background/screen-off
behavior, native audio focus, echo cancellation and long-running thermal behavior
are not qualified by this prototype. The optional screen wake lock applies only
during speech and is released afterward.

## Native integration and the S23

The official native path is `libptts_ffi.so` plus the Kotlin wrapper, built with
Rust/cargo-ndk and the Android NDK, then streamed into Android audio playback.
Prefer CPU first on Pixel 5 and S23. Current published Phonon QNN bundles do not
include the S23's Snapdragon 8 Gen 2 generation. Device performance and actual
headset routes need physical testing rather than extrapolation from other phones.

## Licensing and sources

This experiment's original code is Apache-2.0. The runtime is MIT OR Apache-2.0;
the selected English Phonon 31M model is Apache-2.0. Runtime/model assets are
downloaded separately and retain their own notices. Phonon 40M has different terms
and is not selected here.

- [Official browser runtime](https://github.com/gradium-ai/xn-ptts/tree/main/ptts-wasm/js)
- [Model card](https://huggingface.co/gradium/phonon-31m-en)
- [Native Android integration](https://github.com/gradium-ai/xn-ptts/blob/main/android/README.md)
- [Android TTS engine](https://github.com/gradium-ai/xn-ptts/blob/main/android/tts-engine/README.md)
