# SPDX-License-Identifier: Apache-2.0
"""Fetch the pinned Apache-2.0 Phonon checkpoint for the local phone experiment."""

import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
REVISION = "541f5752bc3c79583068bb205bfda5eb39aaa08a"
REPO = "gradium/phonon-31m-en"
FILES = ("config.json", "tokenizer.json", "model.q8.gguf", "default-voice.safetensors")
SHA256 = {
    "config.json": "b5d0f88353638370d94035b7d73d7d6577c0554d78f8d7ecfd40490aae39ae85",
    "tokenizer.json": "691a00068fa7b989f2f3e5ae5daa2d1a5bb319f2d5360deafcfb19a8bb6e7936",
    "model.q8.gguf": "a7d9aad2cd6dc66473f24a08bc6d2939030ef4d751ef82349361fbef3272dbae",
    "default-voice.safetensors": "f739e8c4c76ee7f92e7c94a82002748c8cd22e99582ac49f7b9b94cd63786e18",
}


def main():
    directory = ROOT / "android/speech-prototype/models" / REVISION
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {"repository": REPO, "revision": REVISION, "license": "Apache-2.0", "files": []}
    for name in FILES:
        target = directory / name
        if not target.exists():
            temporary = directory / (name + ".part")
            with urlopen(f"https://huggingface.co/{REPO}/resolve/{REVISION}/{name}", timeout=60) as response, temporary.open("wb") as stream:
                while chunk := response.read(1024 * 1024):
                    stream.write(chunk)
            temporary.replace(target)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if digest != SHA256[name]:
            raise SystemExit(f"Integrity check failed for {name}; remove that file and download again")
        manifest["files"].append({"name": name, "size_bytes": target.stat().st_size, "sha256": digest})
        print(name, target.stat().st_size, digest, flush=True)
    (directory.parent / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
