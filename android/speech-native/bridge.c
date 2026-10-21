// SPDX-License-Identifier: Apache-2.0
#include <jni.h>
#include <stdlib.h>
#include <stdio.h>
#include "ptts.h"
#include "c-api.h"

typedef struct { JNIEnv *env; jobject sink; jmethodID method; } Sink;
static bool emit(const float *pcm, size_t n, void *opaque) {
  Sink *s = opaque;
  jfloatArray array = (*s->env)->NewFloatArray(s->env, n);
  if (!array) return false;
  (*s->env)->SetFloatArrayRegion(s->env, array, 0, n, pcm);
  jboolean ok = (*s->env)->CallBooleanMethod(s->env, s->sink, s->method, array);
  (*s->env)->DeleteLocalRef(s->env, array);
  return !(*s->env)->ExceptionCheck(s->env) && ok;
}

JNIEXPORT jboolean JNICALL Java_org_homebot_speechlab_NativeSpeech_speak(
    JNIEnv *env, jclass type, jstring model, jstring text, jobject sink) {
  (void)type;
  setenv("RAYON_NUM_THREADS", "2", 1);
  const char *dir = (*env)->GetStringUTFChars(env, model, NULL);
  PttsHandle *h = ptts_new(dir, PTTS_UNIT_CPU, "en");
  (*env)->ReleaseStringUTFChars(env, model, dir);
  if (!h) return false;
  const char *prompt = (*env)->GetStringUTFChars(env, text, NULL);
  jclass cls = (*env)->GetObjectClass(env, sink);
  Sink s = {env, sink, (*env)->GetMethodID(env, cls, "pcm", "([F)Z")};
  PttsResult result = {0};
  bool ok = s.method && ptts_speak(h, prompt, emit, &s, &result);
  (*env)->ReleaseStringUTFChars(env, text, prompt);
  ptts_free(h);
  return ok;
}

typedef struct {
  const SherpaOnnxOnlineRecognizer *recognizer;
  const SherpaOnnxOnlineStream *stream;
  int rate;
} Recognition;

JNIEXPORT jlong JNICALL Java_org_homebot_speechlab_NativeSpeech_recognizer(
    JNIEnv *env, jclass type, jstring model) {
  (void)type;
  const char *dir = (*env)->GetStringUTFChars(env, model, NULL);
  char encoder[1024], decoder[1024], joiner[1024], tokens[1024];
  snprintf(encoder, sizeof encoder, "%s/encoder-epoch-99-avg-1.int8.onnx", dir);
  snprintf(decoder, sizeof decoder, "%s/decoder-epoch-99-avg-1.onnx", dir);
  snprintf(joiner, sizeof joiner, "%s/joiner-epoch-99-avg-1.int8.onnx", dir);
  snprintf(tokens, sizeof tokens, "%s/tokens.txt", dir);
  (*env)->ReleaseStringUTFChars(env, model, dir);
  SherpaOnnxOnlineRecognizerConfig config = {0};
  config.feat_config.sample_rate = 16000;
  config.feat_config.feature_dim = 80;
  config.model_config.transducer.encoder = encoder;
  config.model_config.transducer.decoder = decoder;
  config.model_config.transducer.joiner = joiner;
  config.model_config.tokens = tokens;
  config.model_config.num_threads = 2;
  config.model_config.provider = "cpu";
  config.decoding_method = "greedy_search";
  Recognition *r = calloc(1, sizeof *r);
  if (!r) return 0;
  r->recognizer = SherpaOnnxCreateOnlineRecognizer(&config);
  if (r->recognizer) r->stream = SherpaOnnxCreateOnlineStream(r->recognizer);
  if (!r->recognizer || !r->stream) {
    if (r->recognizer) SherpaOnnxDestroyOnlineRecognizer(r->recognizer);
    free(r); return 0;
  }
  return (jlong)(intptr_t)r;
}

JNIEXPORT void JNICALL Java_org_homebot_speechlab_NativeSpeech_accept(
    JNIEnv *env, jclass type, jlong handle, jfloatArray array, jint count, jint rate) {
  (void)type;
  Recognition *r = (Recognition *)(intptr_t)handle;
  if (!r || count < 0 || count > (*env)->GetArrayLength(env, array)) return;
  if (rate != 16000 && rate != 24000) return;
  if (r->rate && r->rate != rate) return;
  r->rate = rate;
  jfloat *samples = (*env)->GetFloatArrayElements(env, array, NULL);
  if (!samples) return;
  SherpaOnnxOnlineStreamAcceptWaveform(r->stream, rate, samples, count);
  (*env)->ReleaseFloatArrayElements(env, array, samples, JNI_ABORT);
  while (SherpaOnnxIsOnlineStreamReady(r->recognizer, r->stream))
    SherpaOnnxDecodeOnlineStream(r->recognizer, r->stream);
}

JNIEXPORT jstring JNICALL Java_org_homebot_speechlab_NativeSpeech_result(
    JNIEnv *env, jclass type, jlong handle, jboolean finish) {
  (void)type;
  Recognition *r = (Recognition *)(intptr_t)handle;
  if (!r) return (*env)->NewStringUTF(env, "");
  if (finish) {
    float tail[12000] = {0};
    int rate = r->rate ? r->rate : 16000;
    SherpaOnnxOnlineStreamAcceptWaveform(r->stream, rate, tail, rate / 2);
    SherpaOnnxOnlineStreamInputFinished(r->stream);
    while (SherpaOnnxIsOnlineStreamReady(r->recognizer, r->stream))
      SherpaOnnxDecodeOnlineStream(r->recognizer, r->stream);
  }
  const SherpaOnnxOnlineRecognizerResult *result = SherpaOnnxGetOnlineStreamResult(r->recognizer, r->stream);
  jstring text = (*env)->NewStringUTF(env, result && result->text ? result->text : "");
  if (result) SherpaOnnxDestroyOnlineRecognizerResult(result);
  return text;
}

JNIEXPORT void JNICALL Java_org_homebot_speechlab_NativeSpeech_close(
    JNIEnv *env, jclass type, jlong handle) {
  (void)env; (void)type;
  Recognition *r = (Recognition *)(intptr_t)handle;
  if (!r) return;
  SherpaOnnxDestroyOnlineStream(r->stream);
  SherpaOnnxDestroyOnlineRecognizer(r->recognizer);
  free(r);
}
