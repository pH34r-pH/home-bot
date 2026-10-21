# Pixel brain

The native Android robot-brain app is not implemented in this simulator milestone.
Target: the owner's Google Pixel 5, upright portrait, rear camera forward in the
driving pose. Unity and Unreal are not dependencies.

Keep perception/behavior separate from `SensorSource`, `ActuatorSink`, and face UI.
Implement a simulation source using the [API contract](../docs/protocol.md) through
a future paired LAN bridge, then a real camera/IMU source and Mega hardware sink.
The current operator server is loopback-only and cannot be reached from the phone.

Use the actual phone to validate ARCore, camera intrinsics, sensor timestamps,
USB/charging, long-running operation and Android lifecycle behavior. Desktop
simulation does not validate those. Expression names are currently `neutral`,
`happy`, `curious`, and `sleepy`, with a short text message.

## Speech experiment

The [native speech prototype](speech-native/README.md) now runs Phonon directly
on the physical Pixel CPU over ADB and plays the resulting WAV through a debug
Android service while the phone remains locked. Synthesis, speaker-route frame
progress and playback cancellation were verified; microphone recognition and the
integrated robot brain are still future work.

The [Phonon voice lab](speech-prototype/README.md) is a separate browser-based
prototype for running English TTS directly on the Pixel CPU. It serves pinned
assets over USB, streams playback on the phone, and records test measurements.
This does not implement the native brain, microphone recognition or hardware
control. Its desktop browser check is separate from the native Pixel results.
