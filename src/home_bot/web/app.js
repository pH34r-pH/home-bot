// SPDX-License-Identifier: Apache-2.0
const $ = id => document.getElementById(id);
let motion = null;
let sending = false;
let live = false;
const rad = degrees => Number(degrees) * Math.PI / 180;
function values() {
  const speed = Number($("speed").value);
  return {
    version: 1, ttl_ms: 400,
    linear_mps: motion === "forward" ? speed : motion === "back" ? -speed : 0,
    angular_rps: motion === "left" ? 1 : motion === "right" ? -1 : 0,
    pan_rad: rad($("pan").value), tilt_rad: rad($("tilt").value),
    expression: $("expression").value, text: $("text").value
  };
}
async function send() {
  if (sending) return;
  sending = true;
  try {
    const response = await fetch("/api/command", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(values()), signal:AbortSignal.timeout(700)});
    if (!response.ok) throw new Error((await response.json()).error);
  } catch (error) { motion = null; $("connection").textContent = error.message; }
  finally { sending = false; }
}
function stop() { motion = null; void send(); }
document.querySelectorAll("[data-drive]").forEach(button => {
  button.addEventListener("pointerdown", event => {
    if (!live) return;
    event.preventDefault(); button.setPointerCapture(event.pointerId);
    motion = button.dataset.drive; void send();
  });
  button.addEventListener("pointerup", stop);
  button.addEventListener("pointercancel", stop);
  button.addEventListener("lostpointercapture", stop);
});
$("stop").addEventListener("click", stop);
window.addEventListener("blur", stop);
document.addEventListener("visibilitychange", () => { if (document.hidden) stop(); });
for (const name of ["pan", "tilt", "speed"]) {
  $(name).addEventListener("input", () => {
    $(name + "-value").value = $(name).value + (name === "speed" ? " m/s" : "°");
    if (name !== "speed") stop();
  });
}
$("expression").addEventListener("change", stop);
$("text").addEventListener("change", stop);
function panTo(value) { $("pan").value = value; $("pan-value").value = value + "°"; stop(); }
$("look-forward").addEventListener("click", () => panTo(0));
$("show-face").addEventListener("click", () => panTo(180));
setInterval(() => { if (motion && !document.hidden) void send(); }, 100);
let polling = false;
let lastSimTime = -1;
let lastAdvanceWall = 0;
let initialized = false;
async function poll() {
  if (polling) return;
  polling = true;
  try {
    const response = await fetch("/api/state", {signal:AbortSignal.timeout(1000)});
    if (!response.ok) throw new Error("Simulator unavailable");
    const state = await response.json();
    if (!initialized && state.applied_command) {
      const command = state.applied_command;
      for (const name of ["pan", "tilt"]) {
        $(name).value = Math.round(command[name + "_rad"] * 180 / Math.PI);
        $(name + "-value").value = $(name).value + "°";
      }
      $("expression").value = command.expression;
      $("text").value = command.text;
      initialized = true;
    }
    if (state.sim_time_s !== lastSimTime) { lastAdvanceWall = performance.now(); lastSimTime = state.sim_time_s; }
    live = state.status === "running" && performance.now() - lastAdvanceWall < 1500;
    $("connection").textContent = live ? "● Simulator connected" : "Simulator paused";
    $("connection").classList.toggle("live", live);
    if (!live) motion = null;
    if (state.status === "running") {
      $("time").textContent = state.sim_time_s.toFixed(1) + " s";
      $("wheels").textContent = state.wheels_rad.map(x => x.toFixed(2)).join(" / ") + " rad";
      $("gimbal").textContent = state.gimbal_rad.map(x => (x * 180 / Math.PI).toFixed(1)).join("° / ") + "°";
      const o = state.odometry;
      $("odometry").textContent = `${o.x_m.toFixed(2)}, ${o.y_m.toFixed(2)} m · ${(o.yaw_rad * 180 / Math.PI).toFixed(0)}°`;
      $("watchdog").textContent = state.watchdog_expired ? "Expired · stopped" : "Command active";
      if (live) $("camera").src = "/api/camera.png?t=" + state.sim_time_s;
    }
  } catch { live = false; motion = null; $("connection").textContent = "Disconnected · stopped"; $("connection").classList.remove("live"); }
  finally { polling = false; }
}
setInterval(poll, 250);
void poll();
