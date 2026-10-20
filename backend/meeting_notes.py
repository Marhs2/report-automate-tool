"""회의 녹음 → 받아 적기(Qwen3-ASR) → 회의록 요약에 쓰는 도우미.

라우트는 main.py에 있다. 여기에는 HTTP와 LLM 호출 없이 검사할 수 있는 부분을 둔다.
받아 적기 서버는 OpenAI 형식의 POST {ASR_BASE_URL}/audio/transcriptions다(Unsloth Studio의 Voice 모델).
브라우저가 회의를 5분씩 잘라 WAV로 올리면 백엔드가 30초 안팎으로 다시 나눠 받아 적고,
녹음이 끝나면 모은 녹취록을 한 번 요약한다.
"""

import difflib
import io
import json
import os
import re
import wave
from array import array
from datetime import date, timedelta

from dotenv import load_dotenv

# main.py는 import가 끝난 뒤에 load_dotenv()를 부른다. 여기서 먼저 읽어야 .env의 ASR_* 값이 들어온다.
load_dotenv()

# 따로 정하지 않으면 보고서 LLM과 같은 서버(Unsloth Studio, …/v1)를 쓴다.
ASR_BASE_URL = os.environ.get("ASR_BASE_URL") or os.environ.get("LM_BASE_URL") or "http://192.168.210.10:8888/v1"
ASR_API_KEY = os.environ.get("ASR_API_KEY") or os.environ.get("LM_API_KEY", "")
# Studio의 Settings → Voice에서 내려받은 모델만 받아 적기에 쓸 수 있다.
ASR_MODEL = os.environ.get("ASR_MODEL", "qwen3-asr-1.7b")
# OpenAI 형식이라 언어는 ISO 코드("ko")로 넘긴다. 비우면 자동 감지.
# 자동 감지는 읽은 문장 벤치마크에서는 조금 나았지만(글자 오류율 16.5% → 16.2%), 실제 회의 녹음(43분)에서는
# 15초 구간 236개 중 11개를 빈 글로 돌려주었다("ko"는 0개). 말을 통째로 잃지 않도록 "ko"를 기본으로 둔다.
ASR_LANGUAGE = os.environ.get("ASR_LANGUAGE", "ko")
ASR_TRANSCRIBE_PATH = "/audio/transcriptions"
# Qwen3-ASR은 5분을 한 번에 받으면 같은 문장을 되풀이해 지어낸다(306초 → 문장 6배).
# 30초 구간도 문장이 여럿 들면 한두 문장을 통째로 빼먹었다(실제 목소리 회의 dev 세트 clean 7.3%).
# 15초로 줄이면 빠지는 문장이 거의 없다(clean 3.8%, 전체 19.4% → 16.5%). 10초부터는 다시 나빠진다.
PIECE_SECONDS = 15
# 말 한가운데를 자르지 않도록, 구간 끝 이 길이 안에서 가장 조용한 0.1초를 찾아 자른다.
PIECE_WINDOW_SECONDS = 8
# 이보다 조용한 구간(-50dBFS 안팎)은 보내지 않는다. 말이 없으면 모델이 없는 말을 지어낸다.
SILENCE_RMS = 100
# 받아 적기 모델에 문맥(context)으로 사내 용어(이름 · 프로젝트)를 넘길지. Qwen3-ASR은 넘긴 용어 목록을
# 말이 없는 곳에서 그대로 읽어 녹취록에 적는다("관리자, 박민준, 유시은, …"). 그래서 기본은 넘기지 않고,
# 사내 용어 교정은 조각마다 LLM 교정(polish_segments)에 맡긴다. 1이면 prompt로 넘긴다.
ASR_SEND_CONTEXT = os.environ.get("ASR_SEND_CONTEXT", "0") == "1"
# 넘길 때 이 글자 수까지만.
HOTWORD_CHARS = 600
# 잡음 속에서 모델이 같은 말을 끝없이 되풀이하기도 한다(15초 구간 하나에 "아들" 1,939번).
# 구간 길이에 비례해 출력 토큰을 자른다. 실제 회의는 초당 8글자를 넘지 않아 두 배를 둔다.
TOKENS_PER_SECOND = 16
MIN_COMPLETION_TOKENS = 64
# 단어 묶음이 이보다 많이 연달아 나오면 되풀이로 보고 한 번만 남긴다. 사람은 "네 네 네"처럼 세 번까지는 말한다.
MAX_REPEATS = 3
REPEAT_UNIT_WORDS = 6
# 용어가 이만큼 이상 쉼표로 이어지면 모델이 문맥을 읽은 것으로 보고 지운다.
# 사람이 프로젝트 이름 서너 개를 늘어놓는 말을 지우지 않도록 넉넉히 잡는다.
ECHO_MIN_TERMS = 4

MAX_TRANSCRIPT_CHARS = 100_000
# 5분 조각(16kHz 16비트 모노 WAV)은 9.6MB다. 브라우저가 늦게 잘라도 받도록 넉넉히 잡는다.
MAX_CHUNK_BYTES = 40 * 1024 * 1024
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class MeetingError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def asr_transcribe_url(base: str = ASR_BASE_URL) -> str:
    """http://host:port 또는 http://host:port/v1 → http://host:port/v1/audio/transcriptions"""
    base = base.rstrip("/").removesuffix(ASR_TRANSCRIBE_PATH)
    if not base.endswith("/v1"):
        base += "/v1"
    return base + ASR_TRANSCRIBE_PATH


def clean_text(text) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def hotwords(terms, limit: int = HOTWORD_CHARS) -> str:
    """사내 용어를 "a, b, c"로 잇는다. 같은 말은 한 번만, 한 글자는 빼고, limit 글자까지."""
    seen = set()
    out = []
    size = 0
    for term in terms:
        term = clean_text(term)
        if len(term) < 2 or term in seen:
            continue
        add = len(term) + (2 if out else 0)
        if size + add > limit:
            break
        seen.add(term)
        out.append(term)
        size += add
    return ", ".join(out)


def transcribe_form(terms, seconds: float | None = None) -> dict:
    """받아 적기 서버에 구간과 함께 보내는 폼 값. seconds를 주면 출력 토큰을 그 길이에 맞춰 자른다."""
    form = {"model": ASR_MODEL}
    if ASR_LANGUAGE:
        form["language"] = ASR_LANGUAGE
    if seconds is not None:
        form["max_completion_tokens"] = str(max(MIN_COMPLETION_TOKENS, int(seconds * TOKENS_PER_SECOND)))
    context = hotwords(terms) if ASR_SEND_CONTEXT else ""
    if context:
        form["prompt"] = context
    return form


def check_chunk(data: bytes) -> bytes:
    if not data:
        raise MeetingError("녹음 조각이 비어 있습니다.")
    if len(data) > MAX_CHUNK_BYTES:
        raise MeetingError("녹음 조각이 너무 큽니다.", status=413)
    return data


def read_wav(data: bytes) -> tuple[array, int]:
    """브라우저가 보낸 16비트 모노 WAV → (샘플, 샘플레이트)."""
    try:
        with wave.open(io.BytesIO(data)) as wav:
            if wav.getnchannels() != 1 or wav.getsampwidth() != 2:
                raise MeetingError("녹음 조각은 16비트 모노 WAV여야 합니다.")
            rate = wav.getframerate()
            frames = wav.readframes(wav.getnframes())
    except (wave.Error, EOFError) as exc:
        raise MeetingError("녹음 조각을 읽지 못했습니다.") from exc
    samples = array("h")
    samples.frombytes(frames[: len(frames) // 2 * 2])
    return samples, rate


def _rms(samples, start: int, end: int) -> float:
    if end <= start:
        return 0.0
    return (sum(x * x for x in samples[start:end]) / (end - start)) ** 0.5


def split_pieces(samples, rate: int, piece_seconds: float = PIECE_SECONDS,
                 window_seconds: float = PIECE_WINDOW_SECONDS) -> list[tuple[int, int]]:
    """조각을 piece_seconds 안팎의 (시작, 끝) 샘플 구간으로 나눈다.
    구간 끝 window_seconds 안에서 가장 조용한 0.1초 가운데서 자르고, 말이 없는 구간은 뺀다."""
    piece = int(piece_seconds * rate)
    window = min(piece, int(window_seconds * rate))
    frame = max(1, rate // 10)
    spans, start, total = [], 0, len(samples)
    while total - start > piece:
        cut, best = start + piece, float("inf")
        at = start + piece - window
        while at + frame <= start + piece:
            level = _rms(samples, at, at + frame)
            if level <= best:
                best, cut = level, at + frame // 2
            at += frame
        spans.append((start, cut))
        start = cut
    if total - start >= rate // 2:
        spans.append((start, total))
    return [(s, e) for s, e in spans if _rms(samples, s, e) >= SILENCE_RMS]


def wav_bytes(samples, rate: int) -> bytes:
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(samples.tobytes())
    return out.getvalue()


def _squash(text: str) -> str:
    return re.sub(r"[\s.,!?·]", "", str(text or "")).lower()


def _term_like(piece: str, terms: set) -> bool:
    key = _squash(piece)
    if not key:
        return False
    if key in terms:
        return True
    # 모델이 용어를 조금 틀리게 읽기도 한다("보고변합도구"). 비슷하면 용어로 본다.
    return any(len(t) >= 3 and difflib.SequenceMatcher(None, key, t).ratio() >= 0.75 for t in terms)


def strip_context_echo(text: str, terms) -> str:
    """받아 적은 글에서 모델이 문맥(사내 용어 목록)을 그대로 읽은 부분을 지운다.
    쉼표 · 마침표로 나눈 조각이 ECHO_MIN_TERMS개 이상 연달아 용어(또는 용어와 비슷한 말)뿐이면 그 묶음을 뺀다."""
    keys = {_squash(t) for t in terms if _squash(t)}
    if not text or not keys:
        return clean_text(text)
    parts = re.split(r"([,.，、]\s*)", str(text))
    pieces = [(parts[i], parts[i + 1] if i + 1 < len(parts) else "") for i in range(0, len(parts), 2)]
    like = [_term_like(p, keys) for p, _ in pieces]
    drop = [False] * len(pieces)
    i = 0
    while i < len(pieces):
        if not like[i]:
            i += 1
            continue
        # 용어 묶음 사이에 모델이 알아보기 어렵게 읽은 조각 하나가 끼어도(앞뒤가 용어면) 같은 묶음으로 본다.
        j, count = i, 0
        while j < len(pieces) and (like[j] or (j + 1 < len(pieces) and like[j + 1] and like[j - 1])):
            count += like[j]
            j += 1
        if count >= ECHO_MIN_TERMS:
            for k in range(i, j):
                drop[k] = True
        i = j
    kept = "".join(p + d for (p, d), gone in zip(pieces, drop) if not gone)
    return clean_text(re.sub(r"[,\s]+$", "", re.sub(r"^[,.\s]+", "", kept)))


def final_segment(msg: dict, terms=(), offset: float = 0) -> dict | None:
    """받아 적은 발화 하나를 앱이 쓰는 구간으로. 문맥을 읽은 부분은 빼고, 글이 없으면 None.
    offset은 조각이 회의에서 시작한 시각(초)이다. 구간 시각을 회의 처음부터 센 값으로 바꾼다."""
    text = strip_context_echo(msg.get("text"), terms)
    if not text:
        return None
    start = round(float(msg.get("start") or 0) + offset, 2)
    end = round(float(msg.get("end") or 0) + offset, 2)
    return {"start": start, "end": end, "text": text}


def _repeat_run(keys: list[str], at: int) -> tuple[int, int]:
    """keys[at]에서 시작해 연달아 되풀이되는 단어 묶음 (묶음 크기, 횟수). 가장 길게 덮는 것을 고른다."""
    best = (1, 1)
    for size in range(1, REPEAT_UNIT_WORDS + 1):
        unit = keys[at:at + size]
        if len(unit) < size:
            break
        count = 1
        while keys[at + count * size:at + (count + 1) * size] == unit:
            count += 1
        if count > 1 and size * count > best[0] * best[1]:
            best = (size, count)
    return best


def collapse_repeats(text: str) -> str:
    """같은 단어 묶음이 MAX_REPEATS번보다 많이 연달아 나오면 한 번만 남긴다. 문장부호는 비교에서 버린다."""
    words = str(text or "").split()
    keys = [re.sub(r"[.,?!·]", "", w) for w in words]
    out, at = [], 0
    while at < len(words):
        size, count = _repeat_run(keys, at)
        if count > MAX_REPEATS:
            out += words[at:at + size]
            at += size * count
        else:
            out.append(words[at])
            at += 1
    return " ".join(out)


def piece_segment(result: dict, start: float, end: float, terms=(), offset: float = 0) -> dict | None:
    """구간 하나를 받아 적은 결과({text})를 구간 시각이 붙은 발화로. 되풀이는 접고, 글이 없으면 None."""
    text = collapse_repeats((result or {}).get("text"))
    return final_segment({"start": start, "end": end, "text": text}, terms, offset)


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
