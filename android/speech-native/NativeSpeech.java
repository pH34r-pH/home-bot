// SPDX-License-Identifier: Apache-2.0
package org.homebot.speechlab;

/** Minimal JNI adapter; handles are confined to the service's worker thread. */
final class NativeSpeech {
  static { System.loadLibrary("homebot_speech"); }
  interface Sink { boolean pcm(float[] samples); }
  static native boolean speak(String model, String text, Sink sink);
  static native long recognizer(String model);
  static native void accept(long handle, float[] samples, int count, int rate);
  static native String result(long handle, boolean finish);
  static native void close(long handle);
}
