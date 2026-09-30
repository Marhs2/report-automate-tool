"""회의 녹음 → 전사(R2T2) → 회의록 요약에 쓰는 도우미.

라우트는 main.py에 있다. 여기에는 HTTP와 LLM 호출 없이 검사할 수 있는 부분과
ASR 서버 호출만 둔다.
"""

import difflib
import json
import os
import re
from datetime import date, timedelta

import requests
from dotenv import load_dotenv

# main.py는 import가 끝난 뒤에 load_dotenv()를 부른다. 여기서 먼저 읽어야 .env의 ASR_* 값이 들어온다.
load_dotenv()

ASR_BASE_URL = os.environ.get("ASR_BASE_URL", "http://192.168.210.10:8889")
ASR_MODEL = os.environ.get("ASR_MODEL", "r2t2")
ASR_LANGUAGE = os.environ.get("ASR_LANGUAGE", "ko")
ASR_TIMEOUT_SECONDS = float(os.environ.get("ASR_TIMEOUT_SECONDS", "120"))
# 회의 전체 화자 분리는 한 시간짜리면 몇 분 걸린다.
ASR_DIARIZE_TIMEOUT_SECONDS = float(os.environ.get("ASR_DIARIZE_TIMEOUT_SECONDS", "1200"))
# serve_all.py를 ASR_API_KEY와 함께 띄웠으면 같은 값을 넣는다.
ASR_API_KEY = os.environ.get("ASR_API_KEY", "")
ASR_PATH = "/v1/audio/transcriptions"
SESSION_ID = re.compile(r"^[0-9a-f]{32}$")

# 프론트는 녹음을 5초 안팎 조각(16kHz 모노 WAV, 약 200KB)으로 보낸다. 넉넉히 잡아도 이 이상은 잘못 온 것이다.
MAX_AUDIO_BYTES = 25 * 1024 * 1024
MAX_TRANSCRIPT_CHARS = 100_000
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class MeetingError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def asr_url(base: str = ASR_BASE_URL) -> str:
    base = base.rstrip("/")
    return base if base.endswith(ASR_PATH) else base + ASR_PATH


def clean_text(text) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _asr_call(method: str, url: str, *, timeout: float = ASR_TIMEOUT_SECONDS, **kwargs) -> dict:
    """음성 인식 서버를 부르고 JSON을 돌려준다. 실패는 사용자에게 보여 줄 MeetingError로 바꾼다."""
    headers = {"X-API-Key": ASR_API_KEY} if ASR_API_KEY else {}
    try:
        res = getattr(requests, method)(url, headers=headers, timeout=timeout, **kwargs)
    except requests.Timeout:
        raise MeetingError("음성 인식 서버가 제때 답하지 않았습니다.", 504)
    except requests.RequestException as e:
        print(f"[meeting-asr] connect error: {e}")
        raise MeetingError(
            f"음성 인식 서버({ASR_BASE_URL})에 연결하지 못했습니다. 서버가 켜져 있는지 확인해주세요.",
            502,
        )
    if res.status_code == 404 and "/v1/sessions" in url:
        raise MeetingError("음성 인식 서버에 이 녹음 세션이 없습니다. 서버가 다시 켜졌거나 오래되어 지워졌습니다.", 404)
    if res.status_code != 200:
        print(f"[meeting-asr] upstream status={res.status_code} body={res.text[:500]}")
        raise MeetingError(f"음성 인식 실패 (status={res.status_code}).", 502)
    try:
        body = res.json()
    except ValueError:
        raise MeetingError("음성 인식 서버의 응답을 읽지 못했습니다.", 502)
    return body if isinstance(body, dict) else {}


def _check_audio(data: bytes) -> None:
    if not data:
        raise MeetingError("녹음 조각이 비어 있습니다.")
    if len(data) > MAX_AUDIO_BYTES:
        raise MeetingError("녹음 조각이 25MB를 넘습니다.", 413)


def transcribe_audio(data: bytes, filename: str, content_type: str) -> str:
    _check_audio(data)
    body = _asr_call(
        "post",
        asr_url(),
        files={"file": (filename or "audio.wav", data, content_type or "audio/wav")},
        data={"model": ASR_MODEL, "language": ASR_LANGUAGE},
    )
    return clean_text(body.get("text"))


# ---- 녹음 세션: 조각을 서버에 쌓고, 정지하면 회의 전체로 화자를 나눈다 (asr-server/serve_all.py) ----

def _session_url(session_id: str = "", tail: str = "") -> str:
    if session_id and not SESSION_ID.match(session_id):
        raise MeetingError("녹음 세션 번호가 올바르지 않습니다.")
    url = ASR_BASE_URL.rstrip("/") + "/v1/sessions"
    return f"{url}/{session_id}{tail}" if session_id else url


def create_session() -> str:
    session_id = str(_asr_call("post", _session_url()).get("id") or "")
    if not SESSION_ID.match(session_id):
        raise MeetingError("음성 인식 서버가 녹음 세션을 만들지 못했습니다.", 502)
    return session_id


def append_session_audio(session_id: str, data: bytes, filename: str, content_type: str) -> str:
    """조각을 세션에 이어 붙이고, 같은 조각의 받아 적은 글을 돌려준다."""
    _check_audio(data)
    body = _asr_call(
        "post",
        _session_url(session_id, "/audio"),
        files={"file": (filename or "audio.wav", data, content_type or "audio/wav")},
        data={"transcribe": "true", "language": ASR_LANGUAGE},
    )
    return clean_text(body.get("text"))


def diarize_session(session_id: str, num_speakers: int | None = None) -> dict:
    data = {"language": ASR_LANGUAGE}
    if num_speakers:
        data["num_speakers"] = str(num_speakers)
    body = _asr_call(
        "post",
        _session_url(session_id, "/diarize"),
        data=data,
        timeout=ASR_DIARIZE_TIMEOUT_SECONDS,
    )
    return normalize_diarization(body)


def delete_session(session_id: str) -> None:
    try:
        _asr_call("delete", _session_url(session_id))
    except MeetingError as e:
        # 서버가 6시간 뒤에 지우므로, 못 지워도 사용자 흐름은 멈추지 않는다.
        print(f"[meeting-asr] session delete skipped: {e}")


def normalize_diarization(body: dict) -> dict:
    """서버 결과를 앱이 쓰는 모양으로 맞춘다. 화자 번호는 나온 순서대로 0, 1, 2 …로 다시 매긴다."""
    order = {}
    segments = []
    for row in body.get("segments") or []:
        if not isinstance(row, dict):
            continue
        text = clean_text(row.get("text"))
        if not text:
            continue
        speaker = order.setdefault(str(row.get("speaker") or ""), len(order))
        segment = {
            "start": float(row.get("start") or 0),
            "end": float(row.get("end") or 0),
            "speaker": speaker,
            "text": text,
        }
        if row.get("overlap"):
            segment["overlap"] = float(row["overlap"])
        segments.append(segment)
    return {
        "segments": segments,
        "speakerCount": len(order),
        "failedSegments": int(body.get("failed_segments") or 0),
    }


WEEKDAYS = "월화수목금토일"


def week_calendar(meeting_date: str) -> str:
    """회의 날짜가 속한 주와 다음 주의 날짜표. 모델이 "이번 주 목요일"을 직접 계산하지 않고 찾아 쓰게 한다."""
    day = date.fromisoformat(meeting_date)
    monday = day - timedelta(days=day.weekday())
    lines = []
    for label, offset in (("이번 주", 0), ("다음 주", 7)):
        days = [monday + timedelta(days=offset + i) for i in range(7)]
        lines.append(f"{label}: " + ", ".join(f"{WEEKDAYS[d.weekday()]} {d.isoformat()}" for d in days))
    return "\n".join(lines)


def summary_user_message(transcript: str, meeting_date: str) -> str:
    weekday = WEEKDAYS[date.fromisoformat(meeting_date).weekday()]
    return (
        f"[회의 날짜]\n{meeting_date} ({weekday})\n\n"
        f"[날짜표]\n{week_calendar(meeting_date)}\n\n"
        f"[녹취록]\n{transcript}"
    )


def check_transcript(transcript) -> str:
    text = str(transcript or "").strip()
    if not text:
        raise MeetingError("요약할 녹취록이 없습니다.")
    if len(text) > MAX_TRANSCRIPT_CHARS:
        raise MeetingError(f"녹취록이 {MAX_TRANSCRIPT_CHARS:,}자를 넘습니다. 나눠서 요약해주세요.")
    return text


def check_meeting_date(value) -> str:
    text = str(value or "").strip()
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return date.today().isoformat()


def _lines(value, limit: int) -> str:
    text = str(value or "").strip()
    return text[:limit]


def normalize_summary(raw) -> dict:
    """모델 출력(JSON 문자열 또는 dict)을 회의록 폼이 받는 모양으로 맞춘다.

    기한은 YYYY-MM-DD만 남긴다. 저장할 때 work_records가 다른 형식을 거절하기 때문이다.
    """
    data = raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            raise MeetingError("AI 모델 응답이 JSON이 아닙니다. 다시 시도해주세요.", 502)
    if not isinstance(data, dict):
        raise MeetingError("AI 모델 응답 형식이 올바르지 않습니다.", 502)

    followups = []
    for row in data.get("followups") or []:
        if not isinstance(row, dict):
            continue
        task = clean_text(row.get("task"))[:500]
        if not task:
            continue
        due = clean_text(row.get("due"))
        if not ISO_DATE.match(due):
            due = ""
        else:
            try:
                date.fromisoformat(due)
            except ValueError:
                due = ""
        followups.append({"task": task, "owner": clean_text(row.get("owner"))[:80], "due": due})

    return {
        "title": clean_text(data.get("title"))[:200],
        "agenda": _lines(data.get("agenda"), 4000),
        "decisions": _lines(data.get("decisions"), 4000),
        "followups": followups[:30],
    }


# ---- 받아 적은 글 교정 ----

# 교정 결과가 원문보다 이만큼 넘게 길거나 짧으면 모델이 요약하거나 지어낸 것으로 보고 원문을 쓴다.
FIX_LENGTH_TOLERANCE = 0.3


def fix_user_message(text: str, vocabulary: list[str]) -> str:
    terms = ", ".join(dict.fromkeys(term.strip() for term in vocabulary if term and term.strip()))
    return f"[용어]\n{terms or '(없음)'}\n\n[받아 적은 글]\n{text}"


def _letters(text: str) -> int:
    return len(re.sub(r"[\s\.,\?!·]", "", text))


# 영어 약어를 한국어로 읽은 소리. "알티엘에스"와 "RTLS"를 같은 소리로 비교하려고 쓴다.
LETTER_READINGS = {
    "a": "에이", "b": "비", "c": "씨", "d": "디", "e": "이", "f": "에프", "g": "지", "h": "에이치",
    "i": "아이", "j": "제이", "k": "케이", "l": "엘", "m": "엠", "n": "엔", "o": "오", "p": "피",
    "q": "큐", "r": "알", "s": "에스", "t": "티", "u": "유", "v": "브이", "w": "더블유", "x": "엑스",
    "y": "와이", "z": "제트",
}
KOREAN_NUMBER = re.compile(r"[일이삼사오육칠팔구십백천만억영공]|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열|스물|서른|마흔|쉰")
# 받아들이는 소리 비슷함의 하한(자모 단위 SequenceMatcher 비율). 합성 회의 벤치마크로 정했다.
SOUND_SIMILARITY = 0.55
# 고친 말의 소리가 원래보다 이만큼 넘게 길어지면 덧붙인 것으로 본다. 예: 현대건설기계 → HD 현대건설기계
SOUND_GROWTH = 0.35


def _jamo(text: str) -> str:
    """한글은 초성 · 중성 · 종성으로 풀고, 영문자는 한국어 읽는 소리로 바꾼다."""
    out = []
    for ch in text.lower():
        code = ord(ch) - 0xAC00
        if 0 <= code < 11172:
            out += [chr(0x1100 + code // 588), chr(0x1161 + (code % 588) // 28)]
            if code % 28:
                out.append(chr(0x11A7 + code % 28))
        elif ch in LETTER_READINGS:
            out.append(_jamo(LETTER_READINGS[ch]))
        elif ch.isalnum():
            out.append(ch)
    return "".join(out)


def sounds_alike(a: str, b: str) -> float:
    ja, jb = _jamo(a), _jamo(b)
    if not ja or not jb:
        return 0.0
    return difflib.SequenceMatcher(None, ja, jb).ratio()


def _edit_ok(before: str, after: str) -> bool:
    """단어 단위로 바뀐 한 곳을 받아들일지. 지어낸 말 · 숫자 바꾸기 · 소리가 다른 용어 바꾸기를 막는다."""
    a, b = re.sub(r"\s", "", before), re.sub(r"\s", "", after)
    bare_a = re.sub(r"[\.,\?!·]", "", a)
    bare_b = re.sub(r"[\.,\?!·]", "", b)
    if bare_a == bare_b:
        return True  # 띄어쓰기 · 문장부호만 바뀜
    if not bare_a:
        return len(bare_b) <= 1 and not re.search(r"[A-Za-z0-9]", bare_b)  # 새로 넣은 말
    if not bare_b:
        return len(bare_a) <= 1 and not re.search(r"[0-9]", bare_a)  # 뺀 말
    digits_a, digits_b = re.findall(r"\d", bare_a), re.findall(r"\d", bare_b)
    if digits_a and digits_a != digits_b:
        return False  # 이미 숫자로 적힌 값은 바꾸지 않는다
    if digits_b and not digits_a:
        return bool(KOREAN_NUMBER.search(bare_a))  # 한글 숫자 → 아라비아 숫자
    if len(_jamo(bare_b)) > len(_jamo(bare_a)) * (1 + SOUND_GROWTH):
        return False
    return sounds_alike(bare_a, bare_b) >= SOUND_SIMILARITY


def guard_fix(original: str, fixed: str) -> str:
    """교정 결과를 단어 단위로 원문과 맞춰 보고, 받아들일 수 있는 수정만 남긴다."""
    src, dst = original.split(), fixed.split()
    key = lambda words: [re.sub(r"[\.,\?!·]", "", w) for w in words]
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, key(src), key(dst), autojunk=False).get_opcodes():
        if op == "equal":
            out += dst[j1:j2]
        elif _edit_ok(" ".join(src[i1:i2]), " ".join(dst[j1:j2])):
            out += dst[j1:j2]
        else:
            print(f"[transcript-fix] kept {' '.join(src[i1:i2])!r} (model wrote {' '.join(dst[j1:j2])!r})")
            out += src[i1:i2]
    return " ".join(out)


# 화자별 구간을 한 번에 교정할 때 한 요청에 넣는 글자 수. 너무 길면 모델이 줄을 빼먹는다.
FIX_BATCH_CHARS = 1500


def numbered_lines(texts: list[str]) -> str:
    return "\n".join(f"[{i + 1}] {text}" for i, text in enumerate(texts))


def split_numbered(raw_text: str, count: int) -> list[str | None]:
    """교정 결과를 [번호] 줄로 다시 나눈다. 없는 줄은 None이다."""
    lines: list[str | None] = [None] * count
    for match in re.finditer(r"^\s*\[(\d+)\]\s*(.*)$", raw_text or "", re.M):
        index = int(match.group(1)) - 1
        if 0 <= index < count and lines[index] is None:
            lines[index] = match.group(2).strip()
    return lines


def fix_batches(texts: list[str], limit: int = FIX_BATCH_CHARS) -> list[list[int]]:
    """구간 번호를 글자 수 limit 안쪽 묶음으로 나눈다. 순서는 그대로다."""
    batches, current, size = [], [], 0
    for index, text in enumerate(texts):
        if current and size + len(text) > limit:
            batches.append(current)
            current, size = [], 0
        current.append(index)
        size += len(text)
    if current:
        batches.append(current)
    return batches


def merge_numbered_fix(raw, originals: list[str]) -> list[str]:
    """[번호] 줄 교정 결과를 구간마다 guard_fix로 걸러 받아들인다. 빠진 줄은 원문 그대로."""
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
        text = data.get("text") if isinstance(data, dict) else ""
    except json.JSONDecodeError:
        text = ""
    fixed = split_numbered(str(text or ""), len(originals))
    out = []
    for original, candidate in zip(originals, fixed):
        candidate = clean_text(candidate)
        if not candidate:
            out.append(original)
            continue
        before, after = _letters(original), _letters(candidate)
        if before and abs(after - before) / before > FIX_LENGTH_TOLERANCE:
            out.append(original)
            continue
        out.append(guard_fix(original, candidate))
    return out


def normalize_fix(raw, original: str) -> str:
    """교정 결과를 받아들일지 정한다. 읽을 수 없거나 길이가 크게 달라지면 원문을 돌려준다."""
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        return original
    fixed = clean_text(data.get("text") if isinstance(data, dict) else "")
    if not fixed:
        return original
    before, after = _letters(original), _letters(fixed)
    if before and abs(after - before) / before > FIX_LENGTH_TOLERANCE:
        print(f"[transcript-fix] rejected: length {before} -> {after}")
        return original
    return guard_fix(original, fixed)
