// 브라우저와 node --test 양쪽에서 쓰는 순수 함수만 둔다.

export const SAMPLE_RATE = 16000;
export const DEFAULT_BASE = "http://192.168.210.10:8889";
export const TRANSCRIBE_PATH = "/v1/audio/transcriptions";

// AudioContext가 16kHz를 거부한 브라우저용. 최근접 샘플을 고른다.
export function downsample(input, inRate, outRate = SAMPLE_RATE) {
  if (inRate === outRate) return input;
  const ratio = inRate / outRate;
  const out = new Float32Array(Math.floor(input.length / ratio));
  for (let i = 0; i < out.length; i++) out[i] = input[Math.floor(i * ratio)];
  return out;
}

export function toPcm16(f32) {
  const buf = new ArrayBuffer(f32.length * 2);
  const view = new DataView(buf);
  for (let i = 0; i < f32.length; i++) {
    const s = Math.max(-1, Math.min(1, f32[i]));
    view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return buf;
}

export function concatFloat32(parts) {
  let length = 0;
  for (const p of parts) length += p.length;
  const out = new Float32Array(length);
  let offset = 0;
  for (const p of parts) {
    out.set(p, offset);
    offset += p.length;
  }
  return out;
}

// 모노 16bit PCM WAV. 서버는 librosa로 읽으므로 WAV면 추가 디코더가 필요 없다.
export function encodeWav(f32, sampleRate = SAMPLE_RATE) {
  const pcm = toPcm16(f32);
  const buf = new ArrayBuffer(44 + pcm.byteLength);
  const view = new DataView(buf);
  const ascii = (offset, text) => {
    for (let i = 0; i < text.length; i++) view.setUint8(offset + i, text.charCodeAt(i));
  };
  ascii(0, "RIFF");
  view.setUint32(4, 36 + pcm.byteLength, true);
  ascii(8, "WAVE");
  ascii(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  ascii(36, "data");
  view.setUint32(40, pcm.byteLength, true);
  new Uint8Array(buf, 44).set(new Uint8Array(pcm));
  return buf;
}

export function rms(f32) {
  if (!f32.length) return 0;
  let sum = 0;
  for (let i = 0; i < f32.length; i++) sum += f32[i] * f32[i];
  return Math.sqrt(sum / f32.length);
}

// 서버는 { text } 를 돌려준다. 공백을 정리하고, 없으면 "".
export function extractText(body) {
  if (!body || typeof body.text !== "string") return "";
  return body.text.replace(/\s+/g, " ").trim();
}

// 구간 결과를 이어 붙인다. 앞 결과가 있으면 공백 하나로 잇는다.
export function joinText(current, next) {
  if (!next) return current;
  return current ? `${current} ${next}` : next;
}

export function isHttpUrl(value) {
  try {
    const url = new URL(String(value).trim());
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

// 사용자가 끝에 / 를 붙이거나 엔드포인트 경로까지 넣어도 같은 주소가 되게 한다.
export function transcribeUrl(base) {
  const url = new URL(String(base).trim());
  const path = url.pathname.replace(/\/+$/, "");
  url.pathname = path.endsWith(TRANSCRIBE_PATH) ? path : path + TRANSCRIBE_PATH;
  url.search = "";
  url.hash = "";
  return url.toString();
}
