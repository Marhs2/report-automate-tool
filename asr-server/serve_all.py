# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pyannote.audio>=4.0",
#   "torch",
#   "librosa",
#   "soundfile",
#   "httpx",
#   "fastapi",
#   "uvicorn",
#   "python-multipart",
# ]
# ///
"""
R2T2 전사 + pyannote 화자 분리를 파일 하나, 명령 하나로 서빙

  export HF_TOKEN=hf_xxx
  export ASR_API_KEY=...          # 선택. 정하면 모든 요청에 X-API-Key 헤더가 필요하다
  uv run serve_all.py --port 8889

내부 구조:
  - 이 파일이 자기 자신을 `vllm` 모드로 한 번 더 띄워 R2T2 vLLM 서버를 연다(내부 포트 18000).
    vLLM과 pyannote는 torch 버전이 부딪쳐서, vLLM 쪽은 uv가 따로 만든 가상환경
    (`uv run --with "vllm[audio]" ...`)에서 돈다. 위 script 의존성은 pyannote 쪽 환경이다.
  - 원래 프로세스는 pyannote를 GPU에 올리고 FastAPI로 API를 연다.
  - R2T2 모델은 처음 한 번 Hugging Face에서 받고, 그다음부터는 로컬 캐시를 쓴다.

엔드포인트:
  POST   /v1/audio/transcriptions        전사만 (OpenAI 호환, vLLM으로 프록시)
  POST   /v1/audio/diarize               파일 하나를 화자 분리 + 전사
         form: file, language=ko, num_speakers, min_speakers, max_speakers

  녹음 중에 조각을 쌓아 두었다가 끝에 회의 전체로 화자를 나누는 세션:
  POST   /v1/sessions                    세션 만들기 → {"id"}
  POST   /v1/sessions/{id}/audio         조각 이어 붙이기. form: file, transcribe=false, language=ko
                                         transcribe=true면 그 조각의 전사도 돌려준다
  POST   /v1/sessions/{id}/diarize       지금까지 쌓인 전체로 화자 분리 + 전사 (form은 /diarize와 같다)
  DELETE /v1/sessions/{id}               세션 지우기

  GET    /health                         준비됐으면 200, 아니면 503

화자 번호(SPEAKER_00 …)는 요청 하나 안에서만 같은 사람을 가리킨다.
조각마다 /diarize를 부르면 조각끼리 번호가 맞지 않으니, 녹음은 세션으로 쌓아서 끝에 한 번 나눈다.
"""
import argparse
import asyncio
import atexit
import io
import os
import shutil
import signal
import subprocess
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

R2T2_REPO = "netease-youdao/Confucius4-R2T2"
VLLM_PYTHON = "3.12"
VLLM_DEPS = ["vllm[audio]", "huggingface_hub"]


# ---------------- vllm 모드: R2T2를 vLLM으로 연다 ----------------
# 이 부분은 vLLM 가상환경에서 돈다. 그 환경에는 pyannote · torch(pyannote용)가 없으니
# 아래 무거운 import보다 먼저 처리하고 끝낸다.
def run_vllm(argv):
    p = argparse.ArgumentParser(prog="serve_all.py vllm")
    p.add_argument("--model", default=R2T2_REPO, help="repo id or local path")
    p.add_argument("--name", default="r2t2", help="served model name")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=18000)
    p.add_argument("--gpu", default="0", help="CUDA_VISIBLE_DEVICES")
    p.add_argument("--gpu-mem", type=float, default=0.2)
    p.add_argument("--max-model-len", type=int, default=8192)
    a, extra = p.parse_known_args(argv)  # 나머지는 vllm serve에 그대로 넘긴다

    from huggingface_hub import snapshot_download

    path = a.model
    if not os.path.isdir(path):
        try:
            path = snapshot_download(a.model, local_files_only=True)
        except Exception:
            print(f"[vllm] 캐시에 없어서 받는 중: {a.model}", flush=True)
            path = snapshot_download(a.model)
    print(f"[vllm] model path: {path}", flush=True)

    os.environ["CUDA_VISIBLE_DEVICES"] = a.gpu
    cmd = [
        sys.executable, "-m", "vllm.entrypoints.cli.main", "serve", path,
        "--served-model-name", a.name,
        "--host", a.host,
        "--port", str(a.port),
        "--gpu-memory-utilization", str(a.gpu_mem),
        "--max-model-len", str(a.max_model_len),
        "--trust-remote-code",
        *extra,
    ]
    print("[vllm]", " ".join(cmd), flush=True)
    os.execv(sys.executable, cmd)


if __name__ == "__main__" and sys.argv[1:2] == ["vllm"]:
    run_vllm(sys.argv[2:])
    sys.exit(0)

import httpx
import librosa
import numpy as np
import soundfile as sf
import torch
import uvicorn
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pyannote.audio import Pipeline

SR = 16000
HERE = Path(__file__).resolve().parent

# 화자 구간을 이어 붙이고 자르는 기준.
# 짧은 구간일수록 앞뒤 맥락이 없어 더 틀린다(5초 조각이 24~30초 조각보다 CER이 높았다).
# R2T2는 4분짜리도 한 번에 받아 적었으므로 같은 사람 구간은 60초까지 잇는다.
MERGE_GAP_S = 1.2       # 같은 화자 구간 사이가 이보다 짧으면 잇는다
MERGE_MAX_S = 60.0      # 이은 구간의 최대 길이
MIN_SEGMENT_S = 0.3     # 이보다 짧은 구간은 버린다(숨소리 · 잡음)
PAD_S = 0.2             # 첫 · 끝 음절이 잘리지 않게 구간 앞뒤에 붙이는 여유
ASR_RETRIES = 2         # 구간 전사가 실패하면 다시 시도하는 횟수
MAX_AUDIO_S = 3 * 3600  # 요청 · 세션 하나에 받는 최대 길이

state = {
    "pipe": None,
    "vllm_url": None,
    "model": "r2t2",
    "client": None,
    "diar_lock": None,       # pyannote 파이프라인은 한 번에 하나씩
    "asr_sem": None,         # 모든 요청을 합쳐 vLLM에 동시에 보내는 수
    "session_dir": None,
    "session_ttl_s": 6 * 3600,
    "session_locks": {},
    "api_key": os.environ.get("ASR_API_KEY", ""),
}


# ---------------- 인증 ----------------
def check_key(x_api_key: Optional[str] = Header(None), authorization: Optional[str] = Header(None)):
    key = state["api_key"]
    if not key:
        return
    bearer = (authorization or "").removeprefix("Bearer ").strip()
    if x_api_key != key and bearer != key:
        raise HTTPException(401, "API 키가 필요합니다")


# ---------------- vLLM 서브프로세스 ----------------
def start_vllm(a) -> subprocess.Popen:
    # 같은 파일을 vllm 모드로, vLLM만 깔린 별도 환경에서 띄운다.
    # `python 파일`로 부르므로 위의 script 의존성(pyannote)은 이 환경에 들어가지 않는다.
    cmd = ["uv", "run", "--no-project", "--python", VLLM_PYTHON]
    for dep in VLLM_DEPS:
        cmd += ["--with", dep]
    cmd += ["python", str(Path(__file__).resolve()), "vllm",
            "--port", str(a.vllm_port), "--host", "127.0.0.1",
            "--gpu", a.gpu, "--gpu-mem", str(a.gpu_mem), "--name", state["model"],
            "--max-num-seqs", "32", "--max-num-batched-tokens", "8192"]
    print("[serve_all] vLLM 시작:", " ".join(cmd), flush=True)
    # 새 세션으로 띄워서 그룹째 끈다. kill -9로 이 프로세스를 죽이면 vLLM이 GPU를 쥔 채 남으니
    # 운영에서는 systemd(KillMode=control-group)로 돌린다.
    proc = subprocess.Popen(cmd, start_new_session=True)

    def stop():
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(20)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
    atexit.register(stop)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    return proc


def wait_vllm(proc, url, timeout=1800):  # 첫 실행은 vLLM 설치 + 모델 다운로드까지 기다린다
    t0 = time.time()
    while time.time() - t0 < timeout:
        if proc.poll() is not None:
            sys.exit(f"[serve_all] vLLM이 종료됨 (code {proc.returncode}). 위 로그 확인")
        try:
            if httpx.get(f"{url}/health", timeout=2).status_code == 200:
                print("[serve_all] vLLM 준비 완료", flush=True)
                return
        except httpx.HTTPError:
            pass
        time.sleep(3)
    sys.exit("[serve_all] vLLM 시작 시간 초과")


# ---------------- 공통 ----------------
def load_audio(data: bytes) -> np.ndarray:
    if not data:
        raise HTTPException(400, "빈 파일입니다")
    try:
        wav, _ = librosa.load(io.BytesIO(data), sr=SR, mono=True)
    except Exception as e:
        raise HTTPException(400, f"오디오를 읽지 못했습니다: {e}")
    if len(wav) > MAX_AUDIO_S * SR:
        raise HTTPException(413, f"{MAX_AUDIO_S // 3600}시간보다 긴 음성은 받지 않습니다")
    return wav.astype(np.float32)


async def read_audio(file: UploadFile) -> np.ndarray:
    # librosa 디코딩은 무겁다. 이벤트 루프에서 돌리면 그동안 다른 요청이 모두 멈춘다.
    return await run_in_threadpool(load_audio, await file.read())


async def asr(wav: np.ndarray, language: Optional[str]) -> str:
    buf = io.BytesIO()
    sf.write(buf, wav, SR, format="WAV")
    data = {"model": state["model"]}
    if language:
        data["language"] = language
    async with state["asr_sem"]:
        r = await state["client"].post(
            f"{state['vllm_url']}/v1/audio/transcriptions",
            files={"file": ("a.wav", buf.getvalue(), "audio/wav")}, data=data)
    if r.status_code != 200:
        raise HTTPException(502, f"vLLM error: {r.text[:300]}")
    return r.json()["text"].strip()


async def asr_with_retry(wav: np.ndarray, language: Optional[str]) -> dict:
    """구간 하나를 전사한다. 실패해도 예외를 던지지 않고 error를 담아 돌려준다.
    한 구간 때문에 한 시간짜리 회의 결과가 통째로 사라지지 않게 한다."""
    last = ""
    for attempt in range(ASR_RETRIES + 1):
        try:
            return {"text": await asr(wav, language)}
        except (HTTPException, httpx.HTTPError) as e:
            last = getattr(e, "detail", None) or str(e)
            await asyncio.sleep(0.5 * (attempt + 1))
    return {"text": "", "error": last[:300]}


def speaker_kwargs(num_speakers, min_speakers, max_speakers) -> dict:
    if num_speakers:
        return {"num_speakers": num_speakers}
    kw = {}
    if min_speakers:
        kw["min_speakers"] = min_speakers
    if max_speakers:
        kw["max_speakers"] = max_speakers
    return kw


def run_diarization(wav: np.ndarray, kw: dict):
    out = state["pipe"]({"waveform": torch.from_numpy(wav).unsqueeze(0), "sample_rate": SR}, **kw)
    exclusive = getattr(out, "exclusive_speaker_diarization", out)
    segs = [(t.start, t.end, spk) for t, _, spk in exclusive.itertracks(yield_label=True)]
    # 겹친 구간(여러 명이 동시에 말함)은 전사가 섞이기 쉽다. 구간마다 겹친 비율을 알려 준다.
    full = getattr(out, "speaker_diarization", out)
    try:
        overlap = full.get_overlap()
    except Exception:
        overlap = None
    return segs, overlap


def merge(segs, gap=MERGE_GAP_S, max_len=MERGE_MAX_S, min_len=MIN_SEGMENT_S):
    merged = []
    for s, e, spk in segs:
        if merged and merged[-1][2] == spk and s - merged[-1][1] <= gap and e - merged[-1][0] <= max_len:
            merged[-1][1] = e
        else:
            merged.append([s, e, spk])
    return [m for m in merged if m[1] - m[0] >= min_len]


def overlap_ratio(overlap, s: float, e: float) -> float:
    if overlap is None or e <= s:
        return 0.0
    try:
        from pyannote.core import Segment
        return round(overlap.crop(Segment(s, e)).duration() / (e - s), 2)
    except Exception:
        return 0.0


async def diarize_wav(wav: np.ndarray, kw: dict, language: Optional[str]) -> dict:
    t0 = time.perf_counter()
    async with state["diar_lock"]:
        raw, overlap = await run_in_threadpool(run_diarization, wav, kw)
    segs = merge(raw)
    t_diar = time.perf_counter() - t0

    pad = int(PAD_S * SR)
    results = await asyncio.gather(*(
        asr_with_retry(wav[max(0, int(s * SR) - pad): int(e * SR) + pad], language)
        for s, e, _ in segs
    ))

    rows = []
    for (s, e, spk), res in zip(segs, results):
        if not res["text"] and "error" not in res:
            continue
        row = {"start": round(s, 2), "end": round(e, 2), "speaker": spk, "text": res["text"]}
        ratio = overlap_ratio(overlap, s, e)
        if ratio:
            row["overlap"] = ratio
        if "error" in res:
            row["error"] = res["error"]
        rows.append(row)

    return {
        "segments": rows,
        "num_speakers": len({r["speaker"] for r in rows}),
        "failed_segments": sum(1 for r in rows if "error" in r),
        "text": "\n".join(f"{r['speaker']}: {r['text']}" for r in rows if r["text"]),
        "timing": {"diarization_s": round(t_diar, 2),
                   "total_s": round(time.perf_counter() - t0, 2),
                   "audio_s": round(len(wav) / SR, 2)},
    }


# ---------------- 세션 (녹음 조각을 디스크에 쌓는다) ----------------
def session_path(sid: str) -> Path:
    if not sid or not all(c in "0123456789abcdef" for c in sid) or len(sid) != 32:
        raise HTTPException(404, "세션이 없습니다")
    path = state["session_dir"] / sid
    if not path.is_dir():
        raise HTTPException(404, "세션이 없습니다")
    return path


def session_lock(sid: str) -> asyncio.Lock:
    return state["session_locks"].setdefault(sid, asyncio.Lock())


def session_seconds(path: Path) -> float:
    pcm = path / "audio.pcm"
    return (pcm.stat().st_size / 2 / SR) if pcm.exists() else 0.0


def append_pcm(path: Path, wav: np.ndarray) -> None:
    pcm = (np.clip(wav, -1, 1) * 32767).astype("<i2").tobytes()
    with open(path / "audio.pcm", "ab") as f:
        f.write(pcm)
    (path / "touched").write_text(str(time.time()))


def read_pcm(path: Path) -> np.ndarray:
    pcm = path / "audio.pcm"
    if not pcm.exists():
        return np.zeros(0, dtype=np.float32)
    return np.fromfile(pcm, dtype="<i2").astype(np.float32) / 32768


async def cleanup_sessions():
    """오래 손대지 않은 세션을 지운다. 브라우저가 닫혀 정지를 못 누른 녹음이 쌓이지 않게."""
    while True:
        now = time.time()
        for path in state["session_dir"].iterdir():
            try:
                touched = float((path / "touched").read_text())
            except (OSError, ValueError):
                touched = path.stat().st_mtime
            if now - touched > state["session_ttl_s"]:
                shutil.rmtree(path, ignore_errors=True)
                state["session_locks"].pop(path.name, None)
        await asyncio.sleep(600)


# ---------------- API ----------------
@asynccontextmanager
async def lifespan(_app):
    state["client"] = httpx.AsyncClient(timeout=600)
    state["diar_lock"] = asyncio.Lock()
    cleaner = asyncio.create_task(cleanup_sessions())
    yield
    cleaner.cancel()
    await state["client"].aclose()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health():
    try:
        ok = (await state["client"].get(f"{state['vllm_url']}/health", timeout=2)).status_code == 200
    except httpx.HTTPError:
        ok = False
    body = {"asr": ok, "diarization": state["pipe"] is not None}
    return JSONResponse(body, status_code=200 if all(body.values()) else 503)


@app.post("/v1/audio/transcriptions", dependencies=[Depends(check_key)])
async def transcriptions(file: UploadFile = File(...), language: str = Form("ko")):
    wav = await read_audio(file)
    return {"text": await asr(wav, language)}


@app.post("/v1/audio/diarize", dependencies=[Depends(check_key)])
async def diarize(
    file: UploadFile = File(...),
    language: str = Form("ko"),
    num_speakers: Optional[int] = Form(None),
    min_speakers: Optional[int] = Form(None),
    max_speakers: Optional[int] = Form(None),
):
    wav = await read_audio(file)
    return await diarize_wav(wav, speaker_kwargs(num_speakers, min_speakers, max_speakers), language)


@app.post("/v1/sessions", dependencies=[Depends(check_key)])
async def create_session():
    sid = uuid.uuid4().hex
    path = state["session_dir"] / sid
    path.mkdir(parents=True)
    (path / "touched").write_text(str(time.time()))
    return {"id": sid}


@app.post("/v1/sessions/{sid}/audio", dependencies=[Depends(check_key)])
async def session_audio(
    sid: str,
    file: UploadFile = File(...),
    transcribe: bool = Form(False),
    language: str = Form("ko"),
):
    path = session_path(sid)
    wav = await read_audio(file)
    async with session_lock(sid):
        if session_seconds(path) + len(wav) / SR > MAX_AUDIO_S:
            raise HTTPException(413, f"세션이 {MAX_AUDIO_S // 3600}시간을 넘었습니다")
        await run_in_threadpool(append_pcm, path, wav)
        seconds = session_seconds(path)
    body = {"seconds": round(seconds, 2)}
    if transcribe:
        body.update(await asr_with_retry(wav, language))
    return body


@app.post("/v1/sessions/{sid}/diarize", dependencies=[Depends(check_key)])
async def session_diarize(
    sid: str,
    language: str = Form("ko"),
    num_speakers: Optional[int] = Form(None),
    min_speakers: Optional[int] = Form(None),
    max_speakers: Optional[int] = Form(None),
):
    path = session_path(sid)
    async with session_lock(sid):
        wav = await run_in_threadpool(read_pcm, path)
    if len(wav) < SR // 2:
        raise HTTPException(400, "세션에 쌓인 소리가 없습니다")
    return await diarize_wav(wav, speaker_kwargs(num_speakers, min_speakers, max_speakers), language)


@app.delete("/v1/sessions/{sid}", dependencies=[Depends(check_key)])
async def delete_session(sid: str):
    path = session_path(sid)
    async with session_lock(sid):
        shutil.rmtree(path, ignore_errors=True)
    state["session_locks"].pop(sid, None)
    return {"deleted": sid}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8889)
    p.add_argument("--vllm-port", type=int, default=18000)
    p.add_argument("--gpu", default="0")
    p.add_argument("--gpu-mem", type=float, default=0.2)
    p.add_argument("--asr-concurrency", type=int, default=16,
                   help="모든 요청을 합쳐 vLLM에 동시에 보내는 전사 수")
    p.add_argument("--session-dir", default="/tmp/asr_sessions")
    p.add_argument("--session-ttl-hours", type=float, default=6)
    a = p.parse_args()

    if not os.environ.get("HF_TOKEN"):
        sys.exit("HF_TOKEN 환경변수를 설정하세요 (pyannote 약관 동의 필요)")

    state["vllm_url"] = f"http://127.0.0.1:{a.vllm_port}"
    state["asr_sem"] = asyncio.Semaphore(a.asr_concurrency)
    state["session_dir"] = Path(a.session_dir)
    state["session_dir"].mkdir(parents=True, exist_ok=True)
    state["session_ttl_s"] = a.session_ttl_hours * 3600
    proc = start_vllm(a)

    # vLLM이 뜨는 동안 pyannote 로드. CUDA를 처음 쓰기 전에 GPU를 골라야 한다.
    os.environ["CUDA_VISIBLE_DEVICES"] = a.gpu
    print("[serve_all] pyannote 로드 중...", flush=True)
    pipe = Pipeline.from_pretrained("pyannote/speaker-diarization-community-1",
                                    token=os.environ["HF_TOKEN"])
    if torch.cuda.is_available():
        pipe.to(torch.device("cuda"))
    state["pipe"] = pipe
    print("[serve_all] pyannote 준비 완료", flush=True)

    wait_vllm(proc, state["vllm_url"])
    if state["api_key"]:
        print("[serve_all] ASR_API_KEY 설정됨: 요청에 X-API-Key 헤더가 필요합니다", flush=True)
    print(f"[serve_all] http://{a.host}:{a.port} 에서 서비스 시작", flush=True)
    uvicorn.run(app, host=a.host, port=a.port)


if __name__ == "__main__":
    main()
