# Native Pixel speech and listening over ADB

This prototype runs **Phonon and sherpa-onnx directly on the Android CPU** in an
isolated debug Android foreground service. Phonon streams generated PCM into
AudioTrack. Sherpa-onnx recognizes a bounded microphone session or a test WAV.
No browser, screen unlock, cloud inference or paid service is involved.

The physical Pixel 5 / Android 14 test on October 21, 2026 passed synthesis,
waveform validation, complete speaker-route frame progress and playback
cancellation while the keyguard remained locked. The follow-up also verified
microphone capture and on-device WAV recognition. See the
[initial report/audio](../../docs/experiments/phonon-native-01/README.md) and
[streaming/listening report](../../docs/experiments/speech-duplex-01/README.md).

## Use the prepared phone

After the setup below, choose its authorized serial from `adb devices -l`:

```powershell
python scripts/phone_speech.py --serial <PIXEL_SERIAL> speak --text "Hello from your home robot."
python scripts/phone_speech.py --serial <PIXEL_SERIAL> speak --text "Hello from your home robot. Please turn left, then stop." --cancel-after 1
# Explicit microphone session, at most 30 seconds; no raw recording saved:
python scripts/phone_speech.py --serial <PIXEL_SERIAL> listen --seconds 12
# Direct file test, distinct from microphone recognition:
python scripts/phone_speech.py --serial <PIXEL_SERIAL> file --wav docs/experiments/phonon-native-01/pixel-generated.wav
# Play a known WAV on the PC after the Pixel begins listening (requires ffplay):
python scripts/phone_speech.py --serial <PIXEL_SERIAL> listen --seconds 12 --play-wav docs/experiments/phonon-native-01/pixel-generated.wav
# Explicitly save a synthetic test utterance on the PC:
python scripts/say_phone.py --serial <PIXEL_SERIAL> --text "Please turn left, then stop." --save-wav artifacts/phone-speech/example.wav
```

The wrappers validate input transfer hashes and wait for actual played-frame
completion. They print model/playback measurements or an explicitly requested
transcript. They serialize local callers with a shared file lease;
this is a single-PC development interface, not a multi-client robot speech queue.
On failure or Ctrl+C it requests playback cancellation. Temporary prompt/audio
files and app-private transcripts are removed after the operation. The most recent
listening transcript remains only in ignored `artifacts/phone-speech/latest-session.json`;
delete it when no longer needed. No microphone audio is saved. No text is sent to
actuators, an LLM, the network, or ordinary application logs.
An ADB disconnect may prevent remote cleanup. Audio is copied to the PC only when
`--save-wav` is explicitly supplied.

`phone_speech.py speak` uses JNI callbacks, a bounded two-block producer queue,
400 ms of initial ready PCM, and an AudioTrack stream. Playback and generation
overlap; cancellation pauses playback independently of native generator cleanup.
The first callback timing is distinct from the first observed played frame.
`say_phone.py` retains the earlier complete-WAV path for saved synthetic fixtures.
Listening uses 16 kHz mono PCM, CPU greedy decoding, and a fixed 1–30 second
window. It produces final text after that window; endpointing, wake words,
barge-in and conversation/command dispatch are not implemented.

For PC acoustic tests, `--play-delay` defaults to two seconds after the host first
observes `listening`; playback also waits for at least two seconds of captured PCM.
`--play-tail` defaults to four seconds. The wrapper expands `--seconds` when needed
to fit the clip, delay, tail, and two seconds of launch/report allowance. It rejects
clips that cannot fit within the app's 30-second limit and records launch/exit timing
in the report. An observed trailing margin below the requested tail fails the test.

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
python scripts/prepare_sherpa.py
docker run --rm --mount "type=bind,source=$speechRoot/.tools/phonon-native/source,target=/source,readonly" --mount "type=bind,source=$speechRoot/.tools/phonon-native/out,target=/out" --mount "type=bind,source=$speechRoot/.tools/sherpa,target=/sherpa,readonly" --mount "type=bind,source=$speechRoot/android/speech-native,target=/harness,readonly" home-bot-phonon-builder:rust1.93-ndkr29 bash /harness/build-bridge.sh
python scripts/build_speech_player.py
```

The Rust build uses the upstream lockfile, ARM64 Android API 26+, `dotprod` and
`fp16` kernels, and 16 KiB library alignment. These CPU flags were verified in
the Pixel's reported feature set; do not assume they work on every ARM64 phone.
The Phonon library requires only Android's system `libc`, `libm` and `libdl`.
The speech app additionally packages the pinned sherpa-onnx 1.13.8 C API and
ONNX Runtime libraries from its official Android AAR. No Kotlin or Java runtime
dependency is needed for the small C/JNI adapter. Asset downloads are SHA-256
checked; model files, headers and binaries remain in ignored `.tools/` folders.

## Install into the isolated test locations

Substitute the authorized device serial in every command:

```powershell
adb -s <PIXEL_SERIAL> install -r -t artifacts/phonon-native/build/home-bot-speech-player-debug.apk
adb -s <PIXEL_SERIAL> shell mkdir -p /data/local/tmp/home-bot-speech/model
adb -s <PIXEL_SERIAL> push .tools/phonon-native/out/phonon-phone /data/local/tmp/home-bot-speech/
adb -s <PIXEL_SERIAL> push .tools/phonon-native/out/arm64-v8a/libptts_ffi.so /data/local/tmp/home-bot-speech/
adb -s <PIXEL_SERIAL> push android/speech-prototype/models/541f5752bc3c79583068bb205bfda5eb39aaa08a/. /data/local/tmp/home-bot-speech/model/
adb -s <PIXEL_SERIAL> shell chmod 755 /data/local/tmp/home-bot-speech/phonon-phone
adb -s <PIXEL_SERIAL> shell pm grant org.homebot.speechlab android.permission.RECORD_AUDIO
adb -s <PIXEL_SERIAL> shell mkdir -p /data/local/tmp/home-bot-speech/asr
$asr = '.tools/sherpa/sherpa-onnx-streaming-zipformer-en-20M-2023-02-17'
foreach ($name in @('encoder-epoch-99-avg-1.int8.onnx', 'decoder-epoch-99-avg-1.onnx', 'joiner-epoch-99-avg-1.int8.onnx', 'tokens.txt')) {
  adb -s <PIXEL_SERIAL> push "$asr/$name" /data/local/tmp/home-bot-speech/asr/
}
adb -s <PIXEL_SERIAL> shell run-as org.homebot.speechlab cp -r /data/local/tmp/home-bot-speech/asr /data/local/tmp/home-bot-speech/model files/
```

The player package is `org.homebot.speechlab`; it is separate from Wardriver and
other installed apps. Its exported service requires the signature-level `DUMP`
permission held by ADB shell, preventing ordinary apps from invoking it. This
does not grant that permission to the app. Microphone access requires the explicit
ADB runtime grant shown above. It has no Internet, camera, location or shared-storage
permission. Playback temporarily uses quarter-scale
media volume and half track gain for tests, then restores the original volume.
It holds a bounded wake lock during an active test, returns audio focus, and
releases microphone/track resources afterward. An in-process gate also prevents
overlapping playback/listening services. A stopped session never restarts itself.

The WAV player accepts bounded canonical 24 kHz mono PCM16 WAVs; the ASR file
test additionally accepts 16 kHz. Whole-file hash checking is necessary: an initial stdin/tee
ADB transfer truncated binary audio, which produced misleading early media-player
completion. The final workflow copies the device-native file inside the debug
app context, verifies the hash, and waits for AudioTrack frame progress.

This is an ADB development prototype. It is not the autonomous Android robot
brain, a system TTS engine, an MCP server or a release APK. The first PC-speaker
acoustic tests returned empty text; a louder attempt recovered only partial words.
This is not reliable enough for verbal control. Room positioning/output route, recognition accuracy,
Bluetooth, camera concurrency and endurance require further tests. No S23 has
been tested. Services can be stopped manually with:

```powershell
adb -s <PIXEL_SERIAL> shell am start-foreground-service -n org.homebot.speechlab/.SpeechService -a STOP
adb -s <PIXEL_SERIAL> shell am start-foreground-service -n org.homebot.speechlab/.PlaybackService -a STOP
```

## License

Original harness/player/wrapper code is Apache-2.0. Upstream `xn-ptts` v0.4.0 is
MIT OR Apache-2.0; the selected English Phonon 31M and 20M English streaming
Zipformer model packages declare Apache-2.0. Sherpa-onnx is Apache-2.0; ONNX Runtime
is MIT. Model provenance/license links are recorded in the experiment report. Dependencies
and downloaded build tools retain their notices. Models, binaries, debug signing
keys and the upstream source checkout are kept in ignored local directories.
