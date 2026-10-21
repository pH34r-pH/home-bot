#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
cd /source
export CARGO_TARGET_AARCH64_LINUX_ANDROID_RUSTFLAGS='-C strip=symbols -C link-arg=-Wl,-z,max-page-size=16384 -C target-cpu=generic -C target-feature=+dotprod,+fp16'
unset RUSTFLAGS CARGO_ENCODED_RUSTFLAGS
cargo ndk -t arm64-v8a --platform 26 -o /out build --locked --release -p ptts-ffi
"$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android26-clang" -O2 -I /source/ptts-ffi/include /harness/speech.c -L /out/arm64-v8a -lptts_ffi -lm -Wl,-z,max-page-size=16384 -o /out/phonon-phone
"$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-readelf" -d /out/arm64-v8a/libptts_ffi.so
rustc --version > /out/toolchain.txt
cargo ndk --version >> /out/toolchain.txt
