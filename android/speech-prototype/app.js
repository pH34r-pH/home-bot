// SPDX-License-Identifier: Apache-2.0
import { PhononTTS, concatPcm, encodeWav } from '/vendor/index.js';

const ui = Object.fromEntries(['load','threads','status','text','speak','stop','save','metrics'].map(id => [id, document.getElementById(id)]));
const revision = '541f5752bc3c79583068bb205bfda5eb39aaa08a';
const path = `/models/${revision}`;
let tts, abort, context, latestWav, wakeLock;
const history = [];
const clientSession = crypto.randomUUID();
const platform = navigator.userAgentData?.platform || navigator.platform;
async function event(value) {
  value = {clientSession, platform, ...value};
  history.push(value);
  ui.metrics.textContent = JSON.stringify(history.slice(-3), null, 2);
  try { await fetch('/api/event', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(value)}); }
  catch { /* Measurements remain on screen if the PC disconnects. */ }
}
function status(text) { ui.status.textContent = text; }
async function fail(error) { status(`Error: ${error.message}`); await event({event:'error',kind:'speech_runtime'}); }
window.addEventListener('unhandledrejection', e => { void fail(e.reason instanceof Error ? e.reason : new Error(String(e.reason))); });

ui.load.onclick = async () => {
  ui.load.disabled = true; ui.speak.disabled = true; ui.threads.disabled = true;
  try {
    tts?.dispose(); tts = undefined;
    status('Loading the local English model...');
    const started = performance.now();
    tts = await PhononTTS.load({lang:'en', quant:'q8',device:'cpu',threads:Number(ui.threads.value),
      model:{weights:{q8:`${path}/model.q8.gguf`},tokenizer:`${path}/tokenizer.json`,config:`${path}/config.json`,voices:{default:`${path}/default-voice.safetensors`},defaultVoice:'default'},
      onProgress: p => status(`Loading ${p.file}: ${Math.round(p.loaded / 1048576)} MB${p.cached ? ' (cached)' : ''}`)});
    const measurement = {event:'loaded',runtime:'phonon-tts@0.4.1',revision,loadMs:performance.now()-started,device:tts.device,threads:tts.threads,threadsReason:tts.threadsReason,features:tts.features,sampleRate:tts.sampleRate,crossOriginIsolated,hardwareConcurrency:navigator.hardwareConcurrency};
    await event(measurement);
    status(`Ready. This device's CPU, ${tts.threads} threads, ${tts.sampleRate} Hz.`);
    ui.speak.disabled = false;
  } catch (error) { await fail(error); }
  finally { ui.load.disabled = false; ui.threads.disabled = false; }
};

ui.speak.onclick = async () => {
  if (!tts || !ui.text.value.trim()) return;
  ui.speak.disabled = true; ui.load.disabled = true; ui.stop.disabled = false; ui.save.disabled = true; latestWav = null;
  abort = new AbortController();
  let audio;
  try {
    context = new AudioContext({sampleRate:tts.sampleRate}); audio = context;
    await audio.resume();
    try { wakeLock = await navigator.wakeLock?.request('screen'); } catch { /* Optional. */ }
    const start = performance.now(), chunks = [];
    let scheduledEnd = audio.currentTime, firstAudioMs = null, gaps = 0, samples = 0;
    const stream = tts.stream(ui.text.value.trim(), {signal:abort.signal});
    // A thrown iterator error must not leave its matching done promise unhandled.
    void stream.done.catch(()=>{});
    status('Speaking on this device...');
    for await (const pcm of stream) {
      if (abort.signal.aborted) break;
      if (firstAudioMs === null) firstAudioMs = performance.now()-start;
      else if (audio.currentTime > scheduledEnd) gaps++;
      const buffer = audio.createBuffer(1,pcm.length,tts.sampleRate);
      buffer.getChannelData(0).set(pcm);
      const source = audio.createBufferSource(); source.buffer=buffer; source.connect(audio.destination);
      const when = Math.max(scheduledEnd,audio.currentTime + (chunks.length ? .01 : .25));
      source.start(when); scheduledEnd=when+buffer.duration;
      chunks.push(pcm); samples += pcm.length;
    }
    const stats = await stream.done;
    const generationMs = performance.now()-start, audioSeconds=samples/tts.sampleRate;
    latestWav = encodeWav(concatPcm(chunks),tts.sampleRate);
    const measurement = {event:'synthesis',characters:ui.text.value.trim().length,firstChunkClientMs:firstAudioMs,generationWallMs:generationMs,audioSeconds,audioSecondsPerComputeSecond:audioSeconds/(generationMs/1000),playbackGapCount:gaps,audioContextState:audio.state,device:tts.device,threads:tts.threads,cancelled:abort.signal.aborted,stats};
    await event(measurement);
    if (!abort.signal.aborted) {
      await new Promise(resolve => setTimeout(resolve,Math.max(0,(scheduledEnd-audio.currentTime)*1000)+100));
      status(`Finished. ${audioSeconds.toFixed(2)} seconds of speech; ${gaps} playback gaps.`);
      ui.save.disabled = false;
      await event({event:'playback_finished',audioSeconds});
    } else status('Stopped.');
  } catch (error) { if (abort.signal.aborted) status('Stopped.'); else await fail(error); }
  finally {
    await audio?.close().catch(()=>{}); context=null;
    await wakeLock?.release().catch(()=>{}); wakeLock=null;
    ui.speak.disabled=false; ui.load.disabled=false; ui.stop.disabled=true;
  }
};
ui.stop.onclick = () => { abort?.abort(); void context?.close().catch(()=>{}); status('Stopping...'); };
ui.save.onclick = async () => {
  if (!latestWav) return;
  const response = await fetch('/api/test.wav',{method:'POST',headers:{'Content-Type':'audio/wav'},body:latestWav});
  if (!response.ok) throw new Error(`WAV save failed: ${response.status}`);
  status('Saved synthetic speech to the local PC.');
  await event({event:'wav_saved',bytes:latestWav.size});
};
await event({event:'page_ready',crossOriginIsolated,secureContext:isSecureContext});
