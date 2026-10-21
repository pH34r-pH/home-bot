// SPDX-License-Identifier: Apache-2.0
package org.homebot.speechlab;

import android.app.KeyguardManager;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.media.AudioAttributes;
import android.media.AudioDeviceInfo;
import android.media.AudioFocusRequest;
import android.media.AudioFormat;
import android.media.AudioManager;
import android.media.AudioTrack;
import android.os.IBinder;
import android.os.PowerManager;
import android.os.SystemClock;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import org.json.JSONObject;

/** Isolated debug WAV playback, with completion tied to actual AudioTrack frame progress. */
public final class PlaybackService extends Service {
  private AudioTrack track;
  private AudioManager manager;
  private AudioFocusRequest focus;
  private PowerManager.WakeLock wake;
  private long started, frames;
  private volatile boolean cancelled, running;
  private volatile String cancellationReason = "cancelled";
  private int previousVolume = -1;
  private boolean ownsSession;

  @Override public IBinder onBind(Intent intent) { return null; }

  private void report(String state) {
    try {
      JSONObject value = new JSONObject();
      value.put("state", state);
      value.put("elapsed_ms", started == 0 ? 0 : SystemClock.elapsedRealtime() - started);
      value.put("keyguard_locked", ((KeyguardManager)getSystemService(KEYGUARD_SERVICE)).isKeyguardLocked());
      value.put("media_volume", manager.getStreamVolume(AudioManager.STREAM_MUSIC));
      value.put("media_volume_before", previousVolume);
      value.put("media_volume_max", manager.getStreamMaxVolume(AudioManager.STREAM_MUSIC));
      value.put("expected_frames", frames);
      value.put("duration_ms", frames / 24.0);
      if (track != null) {
        value.put("playback_head_frames", Integer.toUnsignedLong(track.getPlaybackHeadPosition()));
        value.put("play_state", track.getPlayState());
        AudioDeviceInfo route = track.getRoutedDevice();
        value.put("routed_device_type", route == null ? JSONObject.NULL : route.getType());
        value.put("speaker_route", route != null && route.getType() == AudioDeviceInfo.TYPE_BUILTIN_SPEAKER);
      }
      try (FileOutputStream file = new FileOutputStream(new File(getFilesDir(), "playback.json"))) {
        file.write(value.toString(2).getBytes(StandardCharsets.UTF_8));
      }
    } catch (Exception ignored) { /* No raw input or private file paths in logcat. */ }
  }

  @Override public int onStartCommand(Intent intent, int flags, int startId) {
    if (intent != null && "STOP".equals(intent.getAction())) {
      cancelled = true;
      if (!running) stopSelf();
      return START_NOT_STICKY;
    }
    if (running) return START_NOT_STICKY;
    running = true;
    manager = (AudioManager)getSystemService(AUDIO_SERVICE);
    NotificationManager notifications = (NotificationManager)getSystemService(NOTIFICATION_SERVICE);
    notifications.createNotificationChannel(new NotificationChannel("speech_test", "Local speech test", NotificationManager.IMPORTANCE_LOW));
    startForeground(1, new Notification.Builder(this, "speech_test").setContentTitle("Home Bot speech test")
        .setContentText("Playing locally generated synthetic speech")
        .setSmallIcon(android.R.drawable.ic_btn_speak_now).build());
    new Thread(this::play, "speech-playback").start();
    return START_NOT_STICKY;
  }

  private void play() {
    try {
      ownsSession = SpeechSession.acquire();
      if (!ownsSession) { report("busy"); return; }
      File input = new File(getFilesDir(), "test.wav");
      if (input.length() < 46 || input.length() > 10 * 1024 * 1024) throw new IllegalArgumentException();
      byte[] file = Files.readAllBytes(input.toPath());
      if (file.length < 46 || file.length > 10 * 1024 * 1024) throw new IllegalArgumentException();
      ByteBuffer header = ByteBuffer.wrap(file).order(ByteOrder.LITTLE_ENDIAN);
      if (!new String(file, 0, 4, StandardCharsets.US_ASCII).equals("RIFF") ||
          !new String(file, 8, 8, StandardCharsets.US_ASCII).equals("WAVEfmt ") ||
          header.getInt(16) != 16 || header.getShort(20) != 1 || header.getShort(22) != 1 ||
          header.getInt(24) != 24000 || header.getShort(34) != 16 ||
          !new String(file, 36, 4, StandardCharsets.US_ASCII).equals("data") ||
          header.getInt(40) != file.length - 44 || (file.length - 44) % 2 != 0) throw new IllegalArgumentException();
      frames = (file.length - 44) / 2;
      previousVolume = manager.getStreamVolume(AudioManager.STREAM_MUSIC);
      manager.setStreamVolume(AudioManager.STREAM_MUSIC, Math.max(1, manager.getStreamMaxVolume(AudioManager.STREAM_MUSIC) / 4), 0);
      AudioAttributes attributes = new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA)
          .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build();
      focus = new AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT)
          .setAudioAttributes(attributes).setOnAudioFocusChangeListener(change -> {
            if (change < 0) { cancellationReason = "focus_lost"; cancelled = true; }
          }).build();
      if (manager.requestAudioFocus(focus) != AudioManager.AUDIOFOCUS_REQUEST_GRANTED) {
        report("focus_denied"); return;
      }
      track = new AudioTrack.Builder().setAudioAttributes(attributes)
          .setAudioFormat(new AudioFormat.Builder().setSampleRate(24000)
              .setEncoding(AudioFormat.ENCODING_PCM_16BIT).setChannelMask(AudioFormat.CHANNEL_OUT_MONO).build())
          .setTransferMode(AudioTrack.MODE_STATIC).setBufferSizeInBytes(file.length - 44).build();
      for (AudioDeviceInfo device : manager.getDevices(AudioManager.GET_DEVICES_OUTPUTS)) {
        if (device.getType() == AudioDeviceInfo.TYPE_BUILTIN_SPEAKER) { track.setPreferredDevice(device); break; }
      }
      track.setVolume(.5f);
      if (track.write(file, 44, file.length - 44) != file.length - 44) throw new IllegalStateException();
      wake = ((PowerManager)getSystemService(POWER_SERVICE)).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "HomeBot:SpeechTest");
      wake.acquire((long)(frames / 24.0) + 10000);
      started = SystemClock.elapsedRealtime();
      track.play();
      report("playing");
      long nextReport = started + 500;
      while (!cancelled && Integer.toUnsignedLong(track.getPlaybackHeadPosition()) < frames) {
        long now = SystemClock.elapsedRealtime();
        if (now - started > frames / 24.0 + 5000) { report("playback_timeout"); return; }
        if (now >= nextReport) { report("playing"); nextReport = now + 500; }
        Thread.sleep(20);
      }
      report(cancelled ? cancellationReason : "completed");
    } catch (Exception failure) { report("setup_or_playback_failed"); }
    finally {
      if (track != null) { track.release(); track = null; }
      if (wake != null && wake.isHeld()) wake.release();
      if (focus != null) manager.abandonAudioFocusRequest(focus);
      if (previousVolume >= 0) manager.setStreamVolume(AudioManager.STREAM_MUSIC, previousVolume, 0);
      running = false;
      if (ownsSession) SpeechSession.release();
      stopForeground(STOP_FOREGROUND_REMOVE);
      stopSelf();
    }
  }

  @Override public void onDestroy() { cancelled = true; super.onDestroy(); }
}
