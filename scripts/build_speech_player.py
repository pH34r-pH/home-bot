# SPDX-License-Identifier: Apache-2.0
"""Build the isolated native speech lab using installed Android SDK tools, no Gradle."""

import argparse
import os
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def run(*arguments):
    subprocess.run([str(a) for a in arguments], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", type=Path, default=Path(os.environ["LOCALAPPDATA"]) / "Android/Sdk")
    args = parser.parse_args()
    source = ROOT / "android/speech-native"
    output = ROOT / "artifacts/phonon-native/build"
    output.mkdir(parents=True, exist_ok=True)
    classes, dex = output / "classes", output / "dex"
    classes.mkdir(exist_ok=True); dex.mkdir(exist_ok=True)
    tools = args.sdk / "build-tools/36.0.0"
    android = args.sdk / "platforms/android-36/android.jar"
    run("javac", "--release", "8", "-cp", android, "-d", classes, *source.glob("*.java"))
    run(tools / "d8.bat", "--lib", android, "--min-api", "26", "--output", dex, *classes.rglob("*.class"))
    unsigned = output / "unsigned.apk"
    run(tools / "aapt2.exe", "link", "-I", android, "--manifest", source / "AndroidManifest.xml", "--version-code", "1", "--version-name", "0.1", "-o", unsigned)
    with zipfile.ZipFile(unsigned, "a", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(dex / "classes.dex", "classes.dex")
        libraries = [ROOT / ".tools/phonon-native/out/arm64-v8a" / name for name in ("libptts_ffi.so", "libhomebot_speech.so")]
        libraries += [ROOT / ".tools/sherpa/aar/jni/arm64-v8a" / name for name in ("libsherpa-onnx-c-api.so", "libonnxruntime.so")]
        for library in libraries:
            archive.write(library, f"lib/arm64-v8a/{library.name}")
    aligned, signed = output / "aligned.apk", output / "home-bot-speech-player-debug.apk"
    run(tools / "zipalign.exe", "-f", "4", unsigned, aligned)
    key = output / "test-only.keystore"
    if not key.exists():
        run("keytool", "-genkeypair", "-keystore", key, "-alias", "androiddebugkey", "-storepass", "android", "-keypass", "android", "-keyalg", "RSA", "-keysize", "2048", "-validity", "365", "-dname", "CN=Home Bot Debug Test")
    run(tools / "apksigner.bat", "sign", "--ks", key, "--ks-pass", "pass:android", "--key-pass", "pass:android", "--out", signed, aligned)
    run(tools / "apksigner.bat", "verify", signed)
    print(signed)


if __name__ == "__main__":
    main()
