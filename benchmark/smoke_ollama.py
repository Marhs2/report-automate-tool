"""Ollama /api/generate 스모크 테스트.

아래 curl 명령을 코드로 검증한다:

    curl http://localhost:11434/api/generate -d '{
      "model": "kwangsuklee/Nanbeige4.1-3B.Q4_K_M",
      "prompt": "Why is the sky blue?"
    }'

순서:
  1. 서버 도달 여부 확인 (GET /api/tags)
  2. 설치된 모델 목록 조회 + 대상 모델 존재 확인
  3. 모델명 후행 공백 경고(Ollama는 공백을 trim 하지 않아 model not found 발생)
  4. POST /api/generate 호출 (기본 stream=false)
  5. 응답/지연/토큰 통계 출력

사용법:
    python benchmark/smoke_ollama.py
    python benchmark/smoke_ollama.py --model "kwangsuklee/Nanbeige4.1-3B.Q4_K_M" --prompt "Why is the sky blue?"
    python benchmark/smoke_ollama.py --host http://localhost:11434 --stream
"""

import argparse
import json
import sys
import time
from urllib.parse import urljoin

import requests

# Windows 콘솔(cp949)은 모델 출력의 emoji/특수문자를 인코딩하지 못해
# UnicodeEncodeError 로 스크립트가 죽는다. UTF-8 로 강제한다.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "kwangsuklee/Nanbeige4.1-3B.Q4_K_M"
DEFAULT_PROMPT = "Why is the sky blue?"
TIMEOUT = 300  # generate 는 모델 로드 + 추론까지 수 초~수십 초 걸릴 수 있다.


def _ok(msg):
    print(f"[OK]   {msg}")


def _warn(msg):
    print(f"[WARN] {msg}")


def _fail(msg):
    print(f"[FAIL] {msg}", file=sys.stderr)


def check_server(host):
    url = urljoin(host + "/", "api/tags")
    try:
        resp = requests.get(url, timeout=10)
    except requests.RequestException as e:
        _fail(f"Ollama 서버에 연결할 수 없습니다: {url}\n  -> {e}")
        return None
    if resp.status_code != 200:
        _fail(f"/api/tags 가 HTTP {resp.status_code} 로 실패했습니다.")
        return None
    models = [m.get("name", "") for m in resp.json().get("models", [])]
    _ok(f"서버 도달 확인: {host}  (설치 모델 {len(models)}개)")
    return models


def find_model(models, target):
    """대상 모델이 설치 목록에 있는지 확인. 모델명 매칭은 tag(:tag) 무시."""
    target_base = target.split(":")[0].strip().lower()
    for m in models:
        if m.split(":")[0].strip().lower() == target_base:
            return m
    return None


def generate(host, model, prompt, stream):
    """POST /api/generate 호출. stream=False 면 단일 JSON, True 면 라인 스트림."""
    url = urljoin(host + "/", "api/generate")
    payload = {"model": model, "prompt": prompt, "stream": stream}
    t0 = time.perf_counter()
    try:
        resp = requests.post(url, json=payload, timeout=TIMEOUT)
    except requests.RequestException as e:
        _fail(f"/api/generate 호출 실패: {e}")
        return 1
    elapsed = time.perf_counter() - t0

    if resp.status_code != 200:
        _fail(f"/api/generate 가 HTTP {resp.status_code} 로 실패했습니다.")
        try:
            print(json.dumps(resp.json(), ensure_ascii=False, indent=2))
        except ValueError:
            print(resp.text)
        return 1

    if stream:
        # 응답 본문은 한 줄당 JSON 객체. 모아서 최종 텍스트만 출력.
        text_parts, last = [], None
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                _warn(f"스트림 라인 파싱 실패: {e}")
                continue
            if obj.get("response"):
                text_parts.append(obj["response"])
            if obj.get("error"):
                _fail(f"스트림 내 에러: {obj['error']}")
                return 1
            last = obj
        text = "".join(text_parts)
    else:
        obj = resp.json()
        if obj.get("error"):
            _fail(f"응답 에러: {obj['error']}")
            return 1
        text = obj.get("response", "")
        last = obj

    _ok(f"generate 완료: {elapsed:.2f}s, HTTP {resp.status_code}")
    print("\n--- 응답 ---")
    print(text.strip() or "(빈 응답)")
    print("--- 통계 ---")
    for key in ("total_duration", "load_duration", "prompt_eval_count",
                "eval_count", "eval_duration"):
        if key in (last or {}):
            val = last[key]
            if isinstance(val, (int, float)) and key.endswith("_duration"):
                print(f"  {key}: {val / 1e9:.3f}s")
            else:
                print(f"  {key}: {val}")
    return 0


def main():
    p = argparse.ArgumentParser(description="Ollama /api/generate 스모크 테스트")
    p.add_argument("--host", default=DEFAULT_HOST, help=f"기본: {DEFAULT_HOST}")
    p.add_argument("--model", default=DEFAULT_MODEL, help="모델명")
    p.add_argument("--prompt", default=DEFAULT_PROMPT, help="프롬프트")
    p.add_argument("--stream", action="store_true", help="stream=true 로 호출")
    args = p.parse_args()

    raw_model = args.model
    model = raw_model.strip()
    if raw_model != model:
        _warn(f"모델명에 후행/선행 공백이 있습니다: {raw_model!r}")
        _warn(f"공백 제거 후 사용: {model!r}  (Ollama는 trim 하지 않아 model not found 유발)")

    print("=== Ollama generate 테스트 ===")
    print(f"host  : {args.host}")
    print(f"model : {model}")
    print(f"prompt: {args.prompt}")
    print(f"stream: {args.stream}\n")

    models = check_server(args.host)
    if models is None:
        return 1

    print("\n[설치 모델]")
    for m in models:
        print(f"  - {m}")

    match = find_model(models, model)
    if match is None:
        _fail(f"대상 모델을 찾을 수 없습니다: {model!r}")
        _warn("먼저 pull 하세요: ollama pull kwangsuklee/Nanbeige4.1-3B.Q4_K_M")
        return 1
    _ok(f"대상 모델 확인: {match}\n")

    return generate(args.host, model, args.prompt, args.stream)


if __name__ == "__main__":
    sys.exit(main())
