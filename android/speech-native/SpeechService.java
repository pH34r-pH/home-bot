// SPDX-License-Identifier: Apache-2.0
package org.homebot.speechlab;

import android.app.*;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.media.*;
import android.os.*;
import java.io.*;
import java.nio.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.ArrayList;
import org.json.JSONObject;

/** Explicit, bounded speech experiments. No network or actuator interface. */
public final class SpeechService extends Service implements NativeSpeech.Sink {
  private volatile boolean cancelled, running;
  private volatile AudioTrack track;
  private AudioRecord microphone;
  private AudioManager audio;
  private AudioFocusRequest focus;
  private PowerManager.WakeLock wake;
  private int originalVolume = -1;
  private long started, captureStarted, computeNanos;
  private volatile long samples, played, firstCallback = -1, firstPlayed = -1, callbacks, maxCallback;
  private final ArrayBlockingQueue<float[]> pending = new ArrayBlockingQueue<>(2);
  private volatile boolean generationDone, writerFailed;
  private Thread playbackWriter;
  private volatile long cancelRequested = -1, framesAtCancel = -1;
  private double squares, peak;
  private String mode, state = "starting";
  private JSONObject metrics;

  @Override public IBinder onBind(Intent intent) { return null; }
  @Override public int onStartCommand(Intent intent, int flags, int id) {
    if (intent != null && "STOP".equals(intent.getAction())) {
      cancelled = true;
      cancelRequested = started == 0 ? -1 : SystemClock.elapsedRealtime() - started;
      AudioTrack current = track;
      if (current != null) try {
        current.pause(); played = Integer.toUnsignedLong(current.getPlaybackHeadPosition()); framesAtCancel = played;
      } catch (IllegalStateException ignored) { }
      if (!running) stopSelf();
      return START_NOT_STICKY;
    }
    if (running) return START_NOT_STICKY;
    mode = intent == null ? "" : intent.getStringExtra("mode");
    if (!"speak".equals(mode) && !"listen".equals(mode) && !"file".equals(mode)) {
      stopSelf(); return START_NOT_STICKY;
    }
    running = true;
    cancelled = false;
    audio = (AudioManager)getSystemService(AUDIO_SERVICE);
    NotificationManager notifications = (NotificationManager)getSystemService(NOTIFICATION_SERVICE);
    notifications.createNotificationChannel(new NotificationChannel("speech_lab", "Local speech experiments", NotificationManager.IMPORTANCE_LOW));
    Notification notification = new Notification.Builder(this, "speech_lab").setContentTitle("Home Bot Speech Lab")
        .setContentText("listen".equals(mode) ? "Microphone test (at most 30 seconds)" : "Local synthetic speech test")
        .setSmallIcon(android.R.drawable.ic_btn_speak_now).build();
    int type = "listen".equals(mode) ? ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE : ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK;
    startForeground(2, notification, type);
    int seconds = Math.max(1, Math.min(30, intent.getIntExtra("seconds", 12)));
    new Thread(() -> runExperiment(seconds), "speech-lab").start();
    return START_NOT_STICKY;
  }

  private synchronized void report(String next) {
    state = next;
    try {
      metrics.put("state", state).put("mode", mode).put("elapsed_ms", SystemClock.elapsedRealtime() - started)
          .put("keyguard_locked", ((KeyguardManager)getSystemService(KEYGUARD_SERVICE)).isKeyguardLocked())
          .put("samples", samples).put("rms", samples == 0 ? 0 : Math.sqrt(squares / samples)).put("peak", peak);
      if ("speak".equals(mode)) {
        AudioTrack current = track;
        if (current != null) {
          played = Math.max(played, Integer.toUnsignedLong(current.getPlaybackHeadPosition()));
          AudioDeviceInfo route = current.getRoutedDevice();
          metrics.put("speaker_route", route != null && route.getType() == AudioDeviceInfo.TYPE_BUILTIN_SPEAKER);
          metrics.put("underruns", current.getUnderrunCount());
        }
        metrics.put("playback_head_frames", played).put("callbacks", callbacks).put("max_callback_samples", maxCallback)
            .put("first_callback_ms", firstCallback).put("first_played_observed_ms", firstPlayed)
            .put("media_volume_before", originalVolume).put("media_volume", audio.getStreamVolume(AudioManager.STREAM_MUSIC));
        metrics.put("cancel_request_ms", cancelRequested).put("frames_at_cancel", framesAtCancel);
      } else {
        metrics.put("decode_ms", computeNanos / 1e6).put("feature_sample_rate_hz", 16000);
        if (microphone != null) {
          AudioDeviceInfo route = microphone.getRoutedDevice();
          metrics.put("recording_state", microphone.getRecordingState())
              .put("input_device_type", route == null ? JSONObject.NULL : route.getType());
          if (Build.VERSION.SDK_INT >= 29) for (AudioRecordingConfiguration config : audio.getActiveRecordingConfigurations())
            if (config.getClientAudioSessionId() == microphone.getAudioSessionId()) metrics.put("client_silenced", config.isClientSilenced());
        }
      }
      File temporary = new File(getFilesDir(), "session.json.tmp");
      Files.write(temporary.toPath(), metrics.toString(2).getBytes(StandardCharsets.UTF_8));
      Files.move(temporary.toPath(), new File(getFilesDir(), "session.json").toPath(), StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
    } catch (Exception ignored) { /* No transcript, raw audio or prompt in logcat. */ }
  }

  private void runExperiment(int seconds) {
    long recognizer = 0;
    started = SystemClock.elapsedRealtime();
    metrics = new JSONObject();
    try {
      if (!SpeechSession.acquire()) { report("busy"); return; }
      wake = ((PowerManager)getSystemService(POWER_SERVICE)).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "HomeBot:SpeechLab");
      wake.acquire(90000);
      report("loading");
      if ("speak".equals(mode)) { speak(); return; }
      recognizer = NativeSpeech.recognizer(new File(getFilesDir(), "asr").getPath());
      if (recognizer == 0) throw new IOException("model_load");
      metrics.put("model_load_ms", SystemClock.elapsedRealtime() - started);
      if ("file".equals(mode)) {
        File input = new File(getFilesDir(), "input.wav");
        if (input.length() > 10 * 1024 * 1024 || input.length() < 46) throw new IOException("wav_size");
        byte[] bytes = Files.readAllBytes(input.toPath());
        ByteBuffer header = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN);
        if (header.getInt(16) != 16 || header.getShort(20) != 1 || header.getShort(22) != 1 ||
            header.getShort(34) != 16 || header.getInt(40) != bytes.length - 44 || (bytes.length - 44) % 2 != 0 ||
            !new String(bytes, 0, 4, StandardCharsets.US_ASCII).equals("RIFF") ||
            !new String(bytes, 8, 8, StandardCharsets.US_ASCII).equals("WAVEfmt ") ||
            !new String(bytes, 36, 4, StandardCharsets.US_ASCII).equals("data")) throw new IOException("wav_format");
        int rate = header.getInt(24);
        if (rate != 16000 && rate != 24000) throw new IOException("wav_rate");
        metrics.put("source_sample_rate_hz", rate);
        float[] block = new float[1600];
        for (int offset = 44; offset < bytes.length && !cancelled;) {
          int count = Math.min(block.length, (bytes.length - offset) / 2);
          for (int i = 0; i < count; i++, offset += 2) block[i] = header.getShort(offset) / 32768f;
          feed(recognizer, block, count, rate);
        }
      } else {
        int buffer = Math.max(16000, AudioRecord.getMinBufferSize(16000, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT) * 4);
        microphone = new AudioRecord.Builder().setAudioSource(MediaRecorder.AudioSource.VOICE_RECOGNITION)
            .setAudioFormat(new AudioFormat.Builder().setSampleRate(16000).setChannelMask(AudioFormat.CHANNEL_IN_MONO)
                .setEncoding(AudioFormat.ENCODING_PCM_16BIT).build()).setBufferSizeInBytes(buffer).build();
        if (microphone.getState() != AudioRecord.STATE_INITIALIZED) throw new IOException("record_init");
        for (AudioDeviceInfo device : audio.getDevices(AudioManager.GET_DEVICES_INPUTS))
          if (device.getType() == AudioDeviceInfo.TYPE_BUILTIN_MIC) { microphone.setPreferredDevice(device); break; }
        microphone.startRecording();
        captureStarted = SystemClock.elapsedRealtime();
        metrics.put("capture_start_ms", captureStarted - started).put("requested_seconds", seconds).put("capture_sample_rate_hz", 16000);
        report("listening");
        short[] pcm = new short[1600]; float[] block = new float[1600];
        long nextReport = captureStarted + 500;
        while (!cancelled && samples < seconds * 16000L) {
          if (SystemClock.elapsedRealtime() - captureStarted > seconds * 1000L + 3000) throw new IOException("record_timeout");
          int count = microphone.read(pcm, 0, (int)Math.min(pcm.length, seconds * 16000L - samples), AudioRecord.READ_BLOCKING);
          if (count <= 0) throw new IOException("record_read");
          for (int i = 0; i < count; i++) block[i] = pcm[i] / 32768f;
          feed(recognizer, block, count, 16000);
          if (SystemClock.elapsedRealtime() >= nextReport) { report("listening"); nextReport += 500; }
        }
        metrics.put("capture_wall_ms", SystemClock.elapsedRealtime() - captureStarted);
      }
      // Final text stays app-private; the host must explicitly retrieve it. Never dispatch commands.
      if (!cancelled) metrics.put("text", NativeSpeech.result(recognizer, true));
      report(cancelled ? "cancelled" : "completed");
    } catch (Throwable failure) {
      try { metrics.put("error_type", failure.getClass().getSimpleName()); } catch (Exception ignored) { }
      report("failed");
    } finally {
      cancelled = true;
      if (playbackWriter != null) try { playbackWriter.join(1000); }
      catch (InterruptedException interrupted) { Thread.currentThread().interrupt(); }
      if (recognizer != 0) NativeSpeech.close(recognizer);
      if (microphone != null) {
        try { if (microphone.getRecordingState() == AudioRecord.RECORDSTATE_RECORDING) microphone.stop(); }
        finally { microphone.release(); microphone = null; }
      }
      if (track != null) { track.release(); track = null; }
      if (focus != null) audio.abandonAudioFocusRequest(focus);
      if (originalVolume >= 0) audio.setStreamVolume(AudioManager.STREAM_MUSIC, originalVolume, 0);
      if (wake != null && wake.isHeld()) wake.release();
      if (!"busy".equals(state)) SpeechSession.release();
      running = false;
      stopForeground(STOP_FOREGROUND_REMOVE);
      stopSelf();
    }
  }

  private void feed(long handle, float[] block, int count, int rate) {
    for (int i = 0; i < count; i++) { squares += block[i] * block[i]; peak = Math.max(peak, Math.abs(block[i])); }
    samples += count;
    long before = System.nanoTime(); NativeSpeech.accept(handle, block, count, rate); computeNanos += System.nanoTime() - before;
  }

  private void speak() throws Exception {
    File prompt = new File(getFilesDir(), "prompt.txt");
    if (prompt.length() < 1 || prompt.length() > 2047) throw new IOException("prompt_size");
    String text = new String(Files.readAllBytes(prompt.toPath()), StandardCharsets.UTF_8);
    originalVolume = audio.getStreamVolume(AudioManager.STREAM_MUSIC);
    audio.setStreamVolume(AudioManager.STREAM_MUSIC, Math.max(1, audio.getStreamMaxVolume(AudioManager.STREAM_MUSIC) / 4), 0);
    AudioAttributes attributes = new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build();
    focus = new AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT).setAudioAttributes(attributes)
        .setOnAudioFocusChangeListener(change -> { if (change < 0) cancelled = true; }).build();
    if (audio.requestAudioFocus(focus) != AudioManager.AUDIOFOCUS_REQUEST_GRANTED) throw new IOException("focus_denied");
    track = new AudioTrack.Builder().setAudioAttributes(attributes).setAudioFormat(new AudioFormat.Builder()
        .setSampleRate(24000).setChannelMask(AudioFormat.CHANNEL_OUT_MONO).setEncoding(AudioFormat.ENCODING_PCM_FLOAT).build())
        .setTransferMode(AudioTrack.MODE_STREAM).setBufferSizeInBytes(4800 * 4).build();
    for (AudioDeviceInfo device : audio.getDevices(AudioManager.GET_DEVICES_OUTPUTS))
      if (device.getType() == AudioDeviceInfo.TYPE_BUILTIN_SPEAKER) { track.setPreferredDevice(device); break; }
    track.setVolume(.5f);
    Thread observer = new Thread(() -> {
      while (track != null && firstPlayed < 0 && !cancelled) {
        try {
          if (track.getPlaybackHeadPosition() > 0) firstPlayed = SystemClock.elapsedRealtime() - started;
          Thread.sleep(10);
        } catch (Exception ended) { return; }
      }
    }, "speech-first-frame");
    observer.start();
    Thread writer = new Thread(() -> {
      try {
        // The CPU's first callback can contain only 80 ms, followed by a much
        // larger batch. Wait for 400 ms of ready PCM before starting the track.
        ArrayList<float[]> initial = new ArrayList<>();
        int ready = 0;
        while (!cancelled && ready < 9600 && (!generationDone || !pending.isEmpty())) {
          float[] block = pending.poll(100, TimeUnit.MILLISECONDS);
          if (block != null) { initial.add(block); ready += block.length; }
        }
        if (!cancelled) {
          track.play();
          for (float[] block : initial) if (!writePcm(block)) {
            if (!cancelled) { writerFailed = true; cancelled = true; }
            break;
          }
        }
        while (!cancelled && (!generationDone || !pending.isEmpty())) {
          float[] block = pending.poll(100, TimeUnit.MILLISECONDS);
          if (block != null && !writePcm(block) && !cancelled) { writerFailed = true; cancelled = true; }
        }
      } catch (Exception failure) { writerFailed = true; cancelled = true; }
    }, "speech-stream-writer");
    playbackWriter = writer;
    writer.start();
    report("generating");
    boolean ok;
    try { ok = NativeSpeech.speak(new File(getFilesDir(), "model").getPath(), text, this); }
    finally { generationDone = true; }
    synchronized (this) { metrics.put("native_ok", ok).put("generation_and_queue_ms", SystemClock.elapsedRealtime() - started); }
    while (writer.isAlive() && SystemClock.elapsedRealtime() - started < 65000) writer.join(100);
    if (writer.isAlive() || writerFailed) throw new IOException("writer_failed");
    if (!ok && !cancelled) throw new IOException("synthesis_failed");
    long deadline = SystemClock.elapsedRealtime() + 5000;
    while (!cancelled && Integer.toUnsignedLong(track.getPlaybackHeadPosition()) < samples) {
      if (SystemClock.elapsedRealtime() > deadline) throw new IOException("drain_timeout");
      Thread.sleep(20);
    }
    report(cancelled ? "cancelled" : "completed");
  }

  @Override public boolean pcm(float[] block) {
    if (firstCallback < 0) firstCallback = SystemClock.elapsedRealtime() - started;
    callbacks++; maxCallback = Math.max(maxCallback, block.length);
    if (block.length > 24000 * 5) { writerFailed = true; return false; }
    try {
      while (!cancelled && SystemClock.elapsedRealtime() - started <= 60000)
        if (pending.offer(block, 100, TimeUnit.MILLISECONDS)) return true;
    } catch (InterruptedException interrupted) { Thread.currentThread().interrupt(); }
    if (!cancelled) writerFailed = true;
    return false;
  }

  private boolean writePcm(float[] block) {
    for (int offset = 0; offset < block.length && !cancelled;) {
      if (SystemClock.elapsedRealtime() - started > 60000) { cancelled = true; break; }
      int count = Math.min(1920, block.length - offset);
      for (int i = offset; i < offset + count; i++) if (!Float.isFinite(block[i])) return false;
      int written = track.write(block, offset, count, AudioTrack.WRITE_BLOCKING);
      if (written <= 0) return false;
      for (int i = offset; i < offset + written; i++) { squares += block[i] * block[i]; peak = Math.max(peak, Math.abs(block[i])); }
      samples += written; offset += written;
      report("streaming");
    }
    return !cancelled;
  }
  @Override public void onDestroy() { cancelled = true; super.onDestroy(); }
}
