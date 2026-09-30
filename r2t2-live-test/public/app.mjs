import {
  SAMPLE_RATE,
  concatFloat32,
  downsample,
  encodeWav,
  extractText,
  isHttpUrl,
  joinText,
  rms,
  transcribeUrl,
} from "./pcm.mjs";

const $ = (id) => document.getElementById(id);
const LOG_LIMIT = 200;
const MIN_SEGMENT_SEC = 0.3;
// 모델을 바꿀 때 키를 바꿔서, 예전 모델용으로 저장된 언어 값이 남지 않게 한다.
const SAVED_KEY = "asr-transcribe-test-r2t2";
const LOCKED = ["base", "lang", "model", "seg", "file"];

let ctx, proc, src, stream;
let recording = false;
// 시작 도중 정지를 누르면 올라가는 번호. 늦게 도착한 마이크를 버리는 데 쓴다.
let session = 0;
let parts = [];
let partSamples = 0;
let recordedSamples = 0;
let request = null; // 녹음 시작 때 고정한 base/lang/model
let queue = Promise.resolve();
let pending = 0;
let requestCount = 0;
let totalResponseMs = 0;
let lastError = "";

function setStatus(text, state) {
  $("status").textContent = text;
  $("status").dataset.state = state;
}

function sendMode() {
  return document.querySelector('input[name="send"]:checked').value;
}

function segmentSeconds() {
  const n = Number($("seg").value);
  return Number.isFinite(n) ? Math.min(60, Math.max(2, n)) : 5;
}

function setRecording(on) {
  recording = on;
  $("start").disabled = on;
  $("stop").disabled = !on;
  for (const id of LOCKED) $(id).disabled = on;
  for (const el of document.querySelectorAll('input[name="send"]')) el.disabled = on;
  syncFileButton();
  if (!on) $("level").style.transform = "scaleX(0)";
}

function syncFileButton() {
  $("send-file").disabled = recording || !$("file").files.length;
}

function syncTranscriptState() {
  const has = $("out").textContent.length > 0;
  $("out-empty").hidden = has;
  $("copy").disabled = !has;
  $("clear").disabled = !has;
}

function appendText(text) {
  $("out").textContent = joinText($("out").textContent, text);
  $("out").scrollTop = $("out").scrollHeight;
  syncTranscriptState();
}

function logLine(line) {
  const li = document.createElement("li");
  li.textContent = line;
  $("log").append(li);
  while ($("log").children.length > LOG_LIMIT) $("log").firstElementChild.remove();
  $("log-count").textContent = String(requestCount);
}

function renderStats() {
  const bits = [];
  if (recordedSamples) bits.push(`녹음 ${(recordedSamples / SAMPLE_RATE).toFixed(1)}초`);
  if (requestCount) {
    bits.push(`요청 ${requestCount}건`);
    bits.push(`평균 응답 ${(totalResponseMs / requestCount / 1000).toFixed(1)}초`);
  }
  $("stats").textContent = bits.join(" · ");
}

function renderStatus() {
  if (recording) {
    const wait = pending ? ` · 전사 대기 ${pending}건` : "";
    setStatus(lastError ? `녹음 중. 직전 요청 실패: ${lastError}` : `녹음 중${wait}`, lastError ? "error" : "live");
  } else if (pending) {
    setStatus(`전사 중… ${pending}건 남음`, "busy");
  } else if (lastError) {
    setStatus(lastError, "error");
  }
}

function showEndpoint() {
  const base = $("base").value.trim();
  $("endpoint").textContent = isHttpUrl(base) ? transcribeUrl(base) : "(주소 확인 필요)";
}

function loadSaved() {
  try {
    const saved = JSON.parse(localStorage.getItem(SAVED_KEY) || "{}");
    if (saved.base) $("base").value = saved.base;
    if (saved.lang) $("lang").value = saved.lang;
    if (saved.seg) $("seg").value = saved.seg;
    if (saved.send) {
      const radio = document.querySelector(`input[name="send"][value="${saved.send}"]`);
      if (radio) radio.checked = true;
    }
  } catch {}
}

function save() {
  try {
    localStorage.setItem(SAVED_KEY, JSON.stringify({
      base: $("base").value.trim(),
      lang: $("lang").value.trim(),
      seg: $("seg").value,
      send: sendMode(),
    }));
  } catch {}
}

// 주소를 검사하고, 이번 요청에 쓸 값을 고정한다. 주소가 틀리면 null.
function readRequest() {
  const base = $("base").value.trim();
  const valid = isHttpUrl(base);
  $("base-error").hidden = valid;
  $("base").setAttribute("aria-invalid", String(!valid));
  if (!valid) {
    $("base").focus();
    return null;
  }
  save();
  return {
    target: transcribeUrl(base),
    lang: $("lang").value.trim() || "ko",
    model: $("model").value.trim() || "r2t2",
  };
}

async function upload(blob, filename, label, req) {
  const form = new FormData();
  form.append("file", blob, filename);
  form.append("model", req.model);
  form.append("language", req.lang);
  const started = performance.now();
  let status = 0;
  let raw = "";
  try {
    const res = await fetch(`/api/transcribe?target=${encodeURIComponent(req.target)}`, { method: "POST", body: form });
    status = res.status;
    raw = await res.text();
  } catch (err) {
    raw = String(err && err.message ? err.message : err);
  }
  const ms = performance.now() - started;
  requestCount += 1;
  totalResponseMs += ms;
  logLine(`#${requestCount} ${label} → ${status || "실패"}, ${(ms / 1000).toFixed(1)}초: ${raw}`);

  let body = null;
  try { body = JSON.parse(raw); } catch {}
  if (status === 200 && body) {
    lastError = "";
    appendText(extractText(body));
  } else if (!status) {
    lastError = "시험 페이지 서버에 닿지 못했습니다. node r2t2-live-test/server.mjs 가 켜져 있는지 확인하세요.";
  } else {
    const detail = body && body.detail ? (typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail)) : raw.slice(0, 200);
    lastError = `전사 실패 (HTTP ${status}): ${detail}`;
  }
}

function enqueue(blob, filename, label, req) {
  pending += 1;
  renderStatus();
  queue = queue
    .then(() => upload(blob, filename, label, req))
    .finally(() => {
      pending -= 1;
      renderStats();
      renderStatus();
      if (!recording && !pending && !lastError) {
        setStatus(`완료. 요청 ${requestCount}건을 전사했습니다.`, "idle");
      }
    });
}

function flush() {
  if (partSamples < MIN_SEGMENT_SEC * SAMPLE_RATE) {
    parts = [];
    partSamples = 0;
    return;
  }
  const seconds = (partSamples / SAMPLE_RATE).toFixed(1);
  const wav = new Blob([encodeWav(concatFloat32(parts))], { type: "audio/wav" });
  parts = [];
  partSamples = 0;
  enqueue(wav, "mic.wav", `녹음 ${seconds}초`, request);
}

async function openMic() {
  try {
    return await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true } });
  } catch (err) {
    if (err && err.name === "NotAllowedError") {
      throw new Error("마이크 권한이 거부되었습니다. 주소창의 사이트 설정에서 마이크를 허용한 뒤 다시 시작하세요.");
    }
    if (err && err.name === "NotFoundError") {
      throw new Error("연결된 마이크를 찾지 못했습니다.");
    }
    throw new Error(`마이크를 열지 못했습니다: ${err && err.message ? err.message : err}`);
  }
}

async function start() {
  if (recording) return;
  const req = readRequest();
  if (!req) return;
  if (!navigator.mediaDevices || !window.isSecureContext) {
    setStatus("이 주소에서는 마이크를 쓸 수 없습니다. http://localhost 로 열어 주세요.", "error");
    return;
  }
  request = req;
  lastError = "";
  parts = [];
  partSamples = 0;
  recordedSamples = 0;
  setRecording(true);
  setStatus("마이크 권한 확인 중…", "busy");

  const mine = ++session;
  const mic = await openMic();
  if (mine !== session) {
    mic.getTracks().forEach((t) => t.stop());
    return;
  }
  stream = mic;

  const segment = sendMode() === "segment" ? segmentSeconds() * SAMPLE_RATE : Infinity;
  ctx = new AudioContext({ sampleRate: SAMPLE_RATE });
  src = ctx.createMediaStreamSource(stream);
  proc = ctx.createScriptProcessor(4096, 1, 1);
  proc.onaudioprocess = (ev) => {
    if (!recording) return;
    const f32 = downsample(ev.inputBuffer.getChannelData(0), ctx.sampleRate);
    $("level").style.transform = `scaleX(${Math.min(1, rms(f32) * 4)})`;
    parts.push(Float32Array.from(f32));
    partSamples += f32.length;
    recordedSamples += f32.length;
    if (partSamples >= segment) flush();
  };
  // ScriptProcessor는 destination에 이어져야 돈다. 소리는 0으로 막는다.
  const mute = ctx.createGain();
  mute.gain.value = 0;
  src.connect(proc);
  proc.connect(mute);
  mute.connect(ctx.destination);
  renderStatus();
  renderStats();
}

function releaseAudio() {
  try { proc && proc.disconnect(); } catch {}
  try { src && src.disconnect(); } catch {}
  try { ctx && ctx.state !== "closed" && ctx.close(); } catch {}
  try { stream && stream.getTracks().forEach((t) => t.stop()); } catch {}
  proc = src = ctx = stream = undefined;
}

function stop() {
  session += 1;
  const wasRecording = recording && request;
  releaseAudio();
  setRecording(false);
  if (wasRecording) flush();
  renderStats();
  if (!pending && !lastError) setStatus("정지함. 보낼 녹음이 없습니다.", "idle");
  else renderStatus();
}

$("conn").addEventListener("submit", (e) => {
  e.preventDefault();
  const before = session;
  start().catch((err) => {
    if (session !== before + 1) return; // 이미 정지한 시도
    releaseAudio();
    setRecording(false);
    request = null;
    setStatus(err.message, "error");
  });
});
$("stop").addEventListener("click", stop);
$("base").addEventListener("input", () => {
  showEndpoint();
  if (!$("base-error").hidden && isHttpUrl($("base").value)) {
    $("base-error").hidden = true;
    $("base").setAttribute("aria-invalid", "false");
  }
});
$("seg").addEventListener("focus", () => {
  document.querySelector('input[name="send"][value="segment"]').checked = true;
});
$("file").addEventListener("change", syncFileButton);
$("send-file").addEventListener("click", () => {
  const file = $("file").files[0];
  const req = file && readRequest();
  if (!req) return;
  lastError = "";
  enqueue(file, file.name, `파일 ${file.name} (${(file.size / 1024).toFixed(0)}KB)`, req);
});
$("copy").addEventListener("click", async () => {
  const label = $("copy").textContent;
  try {
    await navigator.clipboard.writeText($("out").textContent);
    $("copy").textContent = "복사함";
  } catch {
    $("copy").textContent = "복사 실패";
  }
  setTimeout(() => { $("copy").textContent = label; }, 1500);
});
$("clear").addEventListener("click", () => {
  $("out").textContent = "";
  syncTranscriptState();
});
window.addEventListener("pagehide", () => { if (recording) releaseAudio(); });

loadSaved();
showEndpoint();
syncTranscriptState();
syncFileButton();
