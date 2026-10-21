# Native Pixel speech over ADB

This prototype runs **Phonon directly on the Android CPU**, writes its decoded
PCM to a WAV, and plays that WAV through an isolated debug Android foreground
service. No browser, screen unlock, cloud inference or paid service is involved.
It does not unlock Android or read other applications' private data.

The physical Pixel 5 / Android 14 test on October 21, 2026 passed synthesis,
waveform validation, complete speaker-route frame progress and playback
cancellation while the keyguard remained locked. See the
[device report and audio sample](../../docs/experiments/phonon-native-01/README.md).

## Use the prepared phone

After the setup below, choose its authorized serial from `adb devices -l`:

```powershell
python scripts/say_phone.py --serial <PIXEL_SERIAL> --text "Hello from your home robot."
# Explicitly save a synthetic test utterance on the PC:
python scripts/say_phone.py --serial <PIXEL_SERIAL> --text "Please turn left, then stop." --save-wav artifacts/phone-speech/example.wav
```

The wrapper validates WAV transfer hashes, waits for actual played-frame
completion, and requires a speaker route with nonzero media volume. It prints
model and playback measurements. It serializes local callers with a file lease;
this is a single-PC development interface, not a multi-client robot speech queue.
On failure or Ctrl+C it requests playback cancellation. Temporary prompt/audio
files are removed after the operation; model assets and text-free metrics remain.
An ADB disconnect may prevent remote cleanup. Audio is copied to the PC only when
`--save-wav` is explicitly supplied.

The current helper buffers a complete utterance before playback. The first
Phonon callback timing is **not** first audible speech latency for this wrapper.
Direct callback-to-AudioTrack streaming in the native app is future work.

## Build the CPU library and harness

Requirements: Docker Desktop with Linux containers, Git, Python, and free Android
SDK Platform 36 / Build-Tools 36.0.0 / JDK 17 for the debug player. The container
downloads the Android NDK and Rust dependencies; they are build tools, not phone
runtime requirements.

From the repository root in PowerShell:

```powershell
git clone --depth 1 --branch v0.4.0 https://github.com/gradium-ai/xn-ptts.git .tools/phonon-native/source
git -C .tools/phonon-native/source rev-parse HEAD
# Expected source: f07d7952db0c6127d5e4bc3f41c82b3304b6b5aa
docker build -t home-bot-phonon-builder:rust1.93-ndkr29 android/speech-native
New-Item -ItemType Directory -Force .tools/phonon-native/out
$speechRoot = (Get-Location).Path
docker run --rm --mount "type=bind,source=$speechRoot/.tools/phonon-native/source,target=/source" --mount "type=bind,source=$speechRoot/.tools/phonon-native/out,target=/out" --mount "type=bind,source=$speechRoot/android/speech-native,target=/harness,readonly" home-bot-phonon-builder:rust1.93-ndkr29 bash /harness/build-native.sh
python scripts/prepare_speech.py
python scripts/build_speech_player.py
```

The Rust build uses the upstream lockfile, ARM64 Android API 26+, `dotprod` and
`fp16` kernels, and 16 KiB library alignment. These CPU flags were verified in
the Pixel's reported feature set; do not assume they work on every ARM64 phone.
The library requires only Android's system `libc`, `libm` and `libdl`.

## Install into the isolated test locations

Substitute the authorized device serial in every command:

```powershell
adb -s <PIXEL_SERIAL> install -r -t artifacts/phonon-native/build/home-bot-speech-player-debug.apk
adb -s <PIXEL_SERIAL> shell mkdir -p /data/local/tmp/home-bot-speech/model
adb -s <PIXEL_SERIAL> push .tools/phonon-native/out/phonon-phone /data/local/tmp/home-bot-speech/
adb -s <PIXEL_SERIAL> push .tools/phonon-native/out/arm64-v8a/libptts_ffi.so /data/local/tmp/home-bot-speech/
adb -s <PIXEL_SERIAL> push android/speech-prototype/models/541f5752bc3c79583068bb205bfda5eb39aaa08a/. /data/local/tmp/home-bot-speech/model/
adb -s <PIXEL_SERIAL> shell chmod 755 /data/local/tmp/home-bot-speech/phonon-phone
```

The player package is `org.homebot.speechlab`; it is separate from Wardriver and
other installed apps. Its exported service requires the signature-level `DUMP`
permission held by ADB shell, preventing ordinary apps from invoking it. This
does not grant that permission to the player. It has no Internet, microphone,
camera, location or shared-storage permission. It temporarily uses quarter-scale
media volume and half track gain for tests, then restores the original volume.
It holds a bounded wake lock only during playback and returns audio focus.

The helper deliberately accepts only bounded canonical 24 kHz mono PCM16 WAVs
from this harness. Whole-file hash checking is necessary: an initial stdin/tee
ADB transfer truncated binary audio, which produced misleading early media-player
completion. The final workflow copies the device-native file inside the debug
app context, verifies the hash, and waits for AudioTrack frame progress.

This is an ADB development prototype. It is not the autonomous Android robot
brain, a system TTS engine, an MCP server, a release APK, or speech recognition.
Native application lifecycle, streaming, real acoustic audibility, Bluetooth,
camera concurrency and endurance require further tests. The current evidence
does not claim a microphone or S23 test.

## License

Original harness/player/wrapper code is Apache-2.0. Upstream `xn-ptts` v0.4.0 is
MIT OR Apache-2.0; the selected English Phonon 31M model is Apache-2.0. Dependencies
and downloaded build tools retain their notices. Models, binaries, debug signing
keys and the upstream source checkout are kept in ignored local directories.
