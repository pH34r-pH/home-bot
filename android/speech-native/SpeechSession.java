// SPDX-License-Identifier: Apache-2.0
package org.homebot.speechlab;

final class SpeechSession {
  private static boolean busy;
  static synchronized boolean acquire() { if (busy) return false; busy = true; return true; }
  static synchronized void release() { busy = false; }
}
