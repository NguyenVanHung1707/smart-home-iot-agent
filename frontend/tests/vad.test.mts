import assert from "node:assert/strict";
import test from "node:test";

import { VoiceActivityDetector } from "../src/vad.ts";

const quiet = new Float32Array(16);
const speech = new Float32Array(16).fill(0.1);

test("silence before speech never triggers", () => {
  const vad = new VoiceActivityDetector({ minSpeechMs: 100 });

  assert.equal(vad.update(quiet, 0, 100), false);
  assert.equal(vad.update(quiet, 5_000, 100), false);
});

test("two seconds of silence after speech triggers once", () => {
  const vad = new VoiceActivityDetector({ minSpeechMs: 100, silenceMs: 2_000 });

  assert.equal(vad.update(speech, 100, 100), false);
  assert.equal(vad.update(quiet, 2_099, 100), false);
  assert.equal(vad.update(quiet, 2_100, 100), true);
  assert.equal(vad.update(quiet, 3_000, 100), false);
});

test("new speech resets silence countdown", () => {
  const vad = new VoiceActivityDetector({ minSpeechMs: 100, silenceMs: 2_000 });

  vad.update(speech, 100, 100);
  assert.equal(vad.update(quiet, 1_500, 100), false);
  assert.equal(vad.update(speech, 1_600, 100), false);
  assert.equal(vad.update(quiet, 3_599, 100), false);
  assert.equal(vad.update(quiet, 3_600, 100), true);
});
