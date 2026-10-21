# Arduino Mega actuator adapter — planned

No firmware is flashed or implemented by this simulator milestone. The target is
the existing Arduino Mega, two continuous wheel servos with reported position
feedback, and two gimbal actuators with reported feedback.

Before writing output code, identify actuator models, voltage, signal interfaces,
feedback decoding and actual mechanical limits. Do not infer these from the
original Boe-Bot kit or the term “stepper-servo.” Do not invent Mega pin assignments.

The firmware will own actuator timing, feedback sampling, command timeout and
stop/arm behavior. The Pixel will own navigation and behavior. Define a bounded,
versioned transport with sequence/acknowledgement behavior after selecting and
verifying the physical link. The simulator's HTTP contract is not a finalized
wire-level serial protocol. Wheel feedback wrap handling must preserve continuous
angles or report discontinuities explicitly.
