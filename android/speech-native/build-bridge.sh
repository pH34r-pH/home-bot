#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
cc="$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android26-clang"
"$cc" -O2 -shared -fPIC -Wall -Wextra -I /source/ptts-ffi/include -I /sherpa \
  /harness/bridge.c -L /out/arm64-v8a -L /sherpa/aar/jni/arm64-v8a \
  -lptts_ffi -lsherpa-onnx-c-api -Wl,-z,max-page-size=16384 -o /out/arm64-v8a/libhomebot_speech.so
