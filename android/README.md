# Pixel brain — planned

The native Android app is not implemented in this first simulator milestone.
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
