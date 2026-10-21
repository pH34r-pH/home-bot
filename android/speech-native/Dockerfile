# SPDX-License-Identifier: Apache-2.0
FROM rust:1.93-slim-bookworm@sha256:5b9332190bb3b9ece73b810cd1f1e9f06343b294ce184bcb067f0747d7d333ea
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake curl unzip ca-certificates pkg-config && rm -rf /var/lib/apt/lists/*
RUN curl --fail --location --retry 3 https://dl.google.com/android/repository/android-ndk-r29-linux.zip -o /tmp/ndk.zip && unzip -q /tmp/ndk.zip -d /opt && rm /tmp/ndk.zip
ENV ANDROID_NDK_HOME=/opt/android-ndk-r29
RUN rustup target add aarch64-linux-android && cargo install cargo-ndk --version 4.1.2 --locked
WORKDIR /source
