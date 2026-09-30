import { test } from "node:test";
import assert from "node:assert/strict";
import {
  concatFloat32,
  downsample,
  encodeWav,
  extractText,
  isHttpUrl,
  joinText,
  rms,
  toPcm16,
  transcribeUrl,
} from "../public/pcm.mjs";

test("downsample: 같은 속도면 입력을 그대로 돌려준다", () => {
  const input = new Float32Array([0.1, 0.2]);
  assert.equal(downsample(input, 16000), input);
});

test("downsample: 48kHz에서 3개 중 1개를 고른다", () => {
  const input = Float32Array.from({ length: 9 }, (_, i) => i);
  assert.deepEqual([...downsample(input, 48000)], [0, 3, 6]);
});

test("toPcm16: 범위를 자르고 little-endian int16으로 쓴다", () => {
  const view = new DataView(toPcm16(new Float32Array([0, 1, -1, 2, -2])));
  assert.equal(view.byteLength, 10);
  assert.deepEqual(
    [0, 1, 2, 3, 4].map((i) => view.getInt16(i * 2, true)),
    [0, 32767, -32768, 32767, -32768],
  );
});

test("concatFloat32: 순서대로 이어 붙인다", () => {
  const out = concatFloat32([new Float32Array([1, 2]), new Float32Array(), new Float32Array([3])]);
  assert.deepEqual([...out], [1, 2, 3]);
});

test("encodeWav: 16kHz 모노 16bit 헤더와 길이", () => {
  const buf = encodeWav(new Float32Array([0, 0.5, -0.5]));
  const view = new DataView(buf);
  const ascii = (o, n) => String.fromCharCode(...new Uint8Array(buf, o, n));
  assert.equal(buf.byteLength, 44 + 6);
  assert.equal(ascii(0, 4), "RIFF");
  assert.equal(view.getUint32(4, true), 36 + 6);
  assert.equal(ascii(8, 4), "WAVE");
  assert.equal(view.getUint16(20, true), 1);
  assert.equal(view.getUint16(22, true), 1);
  assert.equal(view.getUint32(24, true), 16000);
  assert.equal(view.getUint32(28, true), 32000);
  assert.equal(view.getUint16(34, true), 16);
  assert.equal(ascii(36, 4), "data");
  assert.equal(view.getUint32(40, true), 6);
  assert.equal(view.getInt16(46, true), 16383);
});

test("rms: 빈 입력은 0", () => {
  assert.equal(rms(new Float32Array()), 0);
  assert.equal(rms(new Float32Array([0.5, -0.5])), 0.5);
});

test("extractText: 공백을 정리하고 text가 없으면 빈 문자열", () => {
  assert.equal(extractText({ text: "안녕하세요.  오늘 회의는 세시에 시작합니다. " }), "안녕하세요. 오늘 회의는 세시에 시작합니다.");
  assert.equal(extractText({ detail: "x" }), "");
  assert.equal(extractText(null), "");
});

test("joinText: 구간 결과를 공백 하나로 잇는다", () => {
  assert.equal(joinText("", "가"), "가");
  assert.equal(joinText("가", "나"), "가 나");
  assert.equal(joinText("가", ""), "가");
});

test("isHttpUrl: http/https만 받는다", () => {
  assert.ok(isHttpUrl("http://192.168.210.10:8889/"));
  assert.ok(isHttpUrl(" https://host "));
  assert.ok(!isHttpUrl("ws://host"));
  assert.ok(!isHttpUrl("192.168.210.10:8889"));
});

test("transcribeUrl: 끝의 / 와 경로 포함 여부와 상관없이 같은 주소", () => {
  const want = "http://192.168.210.10:8889/v1/audio/transcriptions";
  assert.equal(transcribeUrl("http://192.168.210.10:8889"), want);
  assert.equal(transcribeUrl("http://192.168.210.10:8889/"), want);
  assert.equal(transcribeUrl("http://192.168.210.10:8889/v1/audio/transcriptions/"), want);
  assert.equal(transcribeUrl("http://h/asr/"), "http://h/asr/v1/audio/transcriptions");
});
