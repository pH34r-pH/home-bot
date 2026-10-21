# SPDX-License-Identifier: Apache-2.0
"""Fetch and verify pinned Apache-2.0 Android ASR runtime/model development assets."""

import hashlib
import json
from pathlib import Path
import tarfile
from urllib.request import urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / ".tools/sherpa"
MODEL = "sherpa-onnx-streaming-zipformer-en-20M-2023-02-17"
ASSETS = {
    "sherpa-onnx-1.13.8.aar": (
        "https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.13.8/sherpa-onnx-1.13.8.aar",
        "633c24321e06b1fe79feafa03ea16cbc0f8a286641e2da3559bac91bdb13bd96"),
    "model.tar.bz2": (
        f"https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/{MODEL}.tar.bz2",
        "9c559283e8498d3fe95913c79ca1cb454bb26281ac2b102b41306c7d752765d9"),
    "c-api.h": (
        "https://raw.githubusercontent.com/k2-fsa/sherpa-onnx/v1.13.8/sherpa-onnx/c-api/c-api.h",
        "2a1b95084be8fd1deb3228fcad2fd3f7f0258b64582f7402281ec174c7b7f4ce"),
}
MODEL_FILES = {
    "encoder-epoch-99-avg-1.int8.onnx": "3810755ce7c3ab26b42a8bcf39d191308fa27fb0f53358823ba46141d03b7eb3",
    "decoder-epoch-99-avg-1.onnx": "45a7f940ecfb53d89fa270ad11b88b961e53a317203eb24b1c8e95ed208b0f30",
    "joiner-epoch-99-avg-1.int8.onnx": "e085d73b593cf9b0707f370dbd656d58327d3fe36d80d849202ef81df02cb01e",
    "tokens.txt": "49e3c2646595fd907228b3c6787069658f67b17377c60aeb8619c4551b2316fb",
}


def verify(path, expected):
    with path.open("rb") as source:
        actual = hashlib.file_digest(source, "sha256").hexdigest()
    if actual != expected:
        raise SystemExit(f"Integrity check failed: {path.name}; remove it and download again")


def main():
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    manifest = {"runtime": "sherpa-onnx@1.13.8", "model": MODEL, "license": "Apache-2.0", "assets": []}
    for name, (url, digest) in ASSETS.items():
        target = DIRECTORY / name
        if not target.exists():
            temporary = target.with_suffix(target.suffix + ".part")
            with urlopen(url, timeout=60) as response, temporary.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            verify(temporary, digest)
            temporary.replace(target)
        verify(target, digest)
        manifest["assets"].append({"name": name, "url": url, "sha256": digest, "size_bytes": target.stat().st_size})
        print(name, digest)
    with zipfile.ZipFile(DIRECTORY / "sherpa-onnx-1.13.8.aar") as archive:
        for name in ("libsherpa-onnx-c-api.so", "libonnxruntime.so"):
            target = DIRECTORY / "aar/jni/arm64-v8a" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read("jni/arm64-v8a/" + name))
    with tarfile.open(DIRECTORY / "model.tar.bz2") as archive:
        for name in [*MODEL_FILES, "README.md"]:
            target = DIRECTORY / MODEL / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(MODEL + "/" + name) as source:
                target.write_bytes(source.read())
            if name in MODEL_FILES:
                verify(target, MODEL_FILES[name])
    manifest["selected_model_files"] = MODEL_FILES
    (DIRECTORY / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
