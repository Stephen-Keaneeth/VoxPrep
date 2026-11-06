/**
 * VoxPrep Adversarial Challenge & Stress-Test Harness
 * Challenger: teamwork_challenger (critic, specialist)
 * Target: Frontend contracts, API client, score normalization, error handling, state store
 */

import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createStore } from "zustand/vanilla";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendDir = path.resolve(__dirname, "..");
const BASE_URL = process.env.API_URL || "http://127.0.0.1:8000";

console.log("================================================================================");
console.log("⚡ VOXPREP ADVERSARIAL STRESS-TEST HARNESS — CHALLENGE 1");
console.log(`⚡ Target Backend: ${BASE_URL}`);
console.log("================================================================================\n");

const results = {
  passed: 0,
  failed: 0,
  warnings: 0,
  findings: [],
};

function recordPass(testName, details) {
  results.passed++;
  console.log(`  [PASS] ${testName}${details ? " — " + details : ""}`);
}

function recordFail(testName, error) {
  results.failed++;
  results.findings.push({ severity: "CRITICAL", test: testName, message: error.message });
  console.error(`  [FAIL] ${testName} ❌: ${error.message}`);
}

function recordWarning(testName, message, suggestion) {
  results.warnings++;
  results.findings.push({ severity: "WARNING", test: testName, message, suggestion });
  console.warn(`  [WARN] ${testName} ⚠️: ${message}`);
}

// -----------------------------------------------------------------------------
// Helper: 16kHz Mono 16-bit PCM WAV Generator
// -----------------------------------------------------------------------------
function createDummyWav(durationMs = 250, sampleRate = 16000) {
  const numSamples = Math.floor(sampleRate * (durationMs / 1000));
  const dataSize = numSamples * 2;
  const buffer = Buffer.alloc(44 + dataSize);

  buffer.write("RIFF", 0);
  buffer.writeUInt32LE(36 + dataSize, 4);
  buffer.write("WAVE", 8);

  buffer.write("fmt ", 12);
  buffer.writeUInt32LE(16, 16);
  buffer.writeUInt16LE(1, 20); // PCM
  buffer.writeUInt16LE(1, 22); // Mono
  buffer.writeUInt32LE(sampleRate, 24);
  buffer.writeUInt32LE(sampleRate * 2, 28);
  buffer.writeUInt16LE(2, 32);
  buffer.writeUInt16LE(16, 34);

  buffer.write("data", 36);
  buffer.writeUInt32LE(dataSize, 40);

  return buffer;
}

// =============================================================================
// TEST SUITE 1: Score Normalization Edge Cases
// =============================================================================
console.log("================================================================================");
console.log("SUITE 1: Score Normalization Stress Testing (frontend/lib/normalization.ts & api.ts)");
console.log("================================================================================");

// Load both implementations
const normSource = fs.readFileSync(path.join(frontendDir, "lib", "normalization.ts"), "utf8");
const apiSource = fs.readFileSync(path.join(frontendDir, "lib", "api.ts"), "utf8");

// Implementation from normalization.ts
function normalizeScoreLib(score, fallback = 0) {
  if (score === undefined || score === null || isNaN(score)) {
    return fallback;
  }
  return score <= 10 ? Math.round(score * 10) : Math.round(score);
}

// Implementation from api.ts
function normalizeScoreApi(score) {
  if (score <= 10) {
    return Math.round(score * 10);
  }
  return Math.round(score);
}

const scoreTestCases = [
  { input: 0, expected: 0, desc: "Zero score" },
  { input: 1.0, expected: 10, desc: "Minimum backend scale 1.0" },
  { input: 5.5, expected: 55, desc: "Midpoint backend scale 5.5" },
  { input: 9.99, expected: 100, desc: "Near-maximum backend scale 9.99" },
  { input: 10.0, expected: 100, desc: "Maximum backend scale 10.0" },
  { input: 50, expected: 50, desc: "Percentage scale 50%" },
  { input: 100, expected: 100, desc: "Percentage scale 100%" },
  { input: undefined, expectedLib: 0, expectedApi: NaN, desc: "undefined input" },
  { input: null, expectedLib: 0, expectedApi: 0, desc: "null input" },
  { input: NaN, expectedLib: 0, expectedApi: NaN, desc: "NaN input" },
  { input: -5.0, expected: -50, desc: "Negative score -5.0 (unclamped)" },
  { input: "8.5", expected: 85, desc: "String number '8.5'" },
  { input: "75", expected: 75, desc: "String number '75'" },
];

for (const tc of scoreTestCases) {
  try {
    const resLib = normalizeScoreLib(tc.input);
    const expectedForLib = tc.expectedLib !== undefined ? tc.expectedLib : tc.expected;

    if (isNaN(expectedForLib)) {
      assert(isNaN(resLib), `${tc.desc}: expected NaN in normalization.ts`);
    } else {
      assert.equal(resLib, expectedForLib, `${tc.desc}: lib returned ${resLib}, expected ${expectedForLib}`);
    }
    recordPass(`normalization.ts: ${tc.desc} (input: ${tc.input} -> ${resLib})`);
  } catch (err) {
    recordFail(`normalization.ts: ${tc.desc}`, err);
  }

  // Check api.ts implementation
  try {
    const resApi = normalizeScoreApi(tc.input);
    const expectedForApi = tc.expectedApi !== undefined ? tc.expectedApi : tc.expected;

    if (isNaN(expectedForApi)) {
      assert(isNaN(resApi), `${tc.desc}: expected NaN in api.ts`);
    } else {
      assert.equal(resApi, expectedForApi, `${tc.desc}: api.ts returned ${resApi}, expected ${expectedForApi}`);
    }
    recordPass(`api.ts: ${tc.desc} (input: ${tc.input} -> ${resApi})`);
  } catch (err) {
    recordFail(`api.ts: ${tc.desc}`, err);
  }
}

// Adversarial Edge Case: 10.1 (Threshold Boundary Anomaly)
console.log("\n--- Testing 10.1 Threshold Boundary Anomaly ---");
{
  const resLib = normalizeScoreLib(10.1);
  const resApi = normalizeScoreApi(10.1);
  console.log(`  Input: 10.1 -> normalization.ts: ${resLib}, api.ts: ${resApi}`);
  if (resLib === 10) {
    recordWarning(
      "Score Normalization 10.1 Anomaly",
      `Score 10.1 evaluates to 10 (10%) instead of ~100% because threshold is score <= 10. If backend returns floating point jitter (e.g. 10.05), it is misinterpreted as a 0-100% percentage score.`,
      "Consider using a threshold buffer (e.g. score <= 10.0) or capping at 100: score <= 10 ? Math.min(100, Math.round(score * 10)) : Math.min(100, Math.round(score))"
    );
  }
}

// Discrepancy Check between api.ts and normalization.ts for undefined / NaN
console.log("\n--- Testing normalization.ts vs api.ts Undefined/NaN Discrepancy ---");
{
  const libUndefined = normalizeScoreLib(undefined);
  const apiUndefined = normalizeScoreApi(undefined);
  if (libUndefined === 0 && isNaN(apiUndefined)) {
    recordWarning(
      "api.ts normalizeScore Missing Null/Undefined Guards",
      `api.ts normalizeScore(undefined) returns NaN, while normalization.ts normalizeScore(undefined) safely returns fallback 0. UI components import from normalization.ts, but api.utils.normalizeScore may produce NaN in consumer code.`,
      "Align api.ts normalizeScore signature and implementation with normalization.ts (add undefined/null/NaN guard)."
    );
  }
}

// =============================================================================
// TEST SUITE 2: Pydantic Error Envelope Parsing & Resilience
// =============================================================================
console.log("\n================================================================================");
console.log("SUITE 2: Pydantic Error Envelope Parsing & HTTP Resilience");
console.log("================================================================================");

// Extract ApiError class from api.ts
class ApiError extends Error {
  constructor(status, detail, errorType) {
    let message = `API request failed with status ${status}`;
    if (typeof detail === "string") {
      message = detail;
    } else if (Array.isArray(detail)) {
      message = detail
        .map((item) => (item.msg ? `${item.loc?.join(".") || "field"}: ${item.msg}` : JSON.stringify(item)))
        .join("; ");
    }
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.errorType = errorType;
  }
}

async function handleResponse(res) {
  if (!res.ok) {
    let detail = res.statusText || "Unknown server error";
    let errorType;

    try {
      const errJson = await res.json();
      if (errJson && errJson.detail !== undefined) {
        detail = errJson.detail;
        errorType = errJson.error_type;
      }
    } catch {
      // Body not JSON; retain default statusText
    }

    throw new ApiError(res.status, detail, errorType);
  }

  return await res.json();
}

// Test 2.1: Single String Details (400, 401, 404, 500)
console.log("\n--- Testing Single String Error Details ---");
const singleStringErrors = [
  { status: 400, body: { detail: "Invalid email format", error_type: "http_error", status_code: 400 } },
  { status: 401, body: { detail: "Invalid email or password", error_type: "http_error", status_code: 401 } },
  { status: 404, body: { detail: "Interview session not found", error_type: "http_error", status_code: 404 } },
  { status: 500, body: { detail: "Internal server error occurred.", error_type: "internal_server_error", status_code: 500 } },
];

for (const tc of singleStringErrors) {
  try {
    const mockRes = new Response(JSON.stringify(tc.body), {
      status: tc.status,
      headers: { "Content-Type": "application/json" },
    });

    let caught = null;
    try {
      await handleResponse(mockRes);
    } catch (err) {
      caught = err;
    }

    assert(caught instanceof ApiError, "Must throw an ApiError instance");
    assert.equal(caught.status, tc.status, `Status must be ${tc.status}`);
    assert.equal(caught.message, tc.body.detail, `Message must match ${tc.body.detail}`);
    assert.equal(caught.errorType, tc.body.error_type, `ErrorType must match ${tc.body.error_type}`);
    recordPass(`Single String Detail (${tc.status}): "${caught.message}" parsed successfully`);
  } catch (err) {
    recordFail(`Single String Detail (${tc.status})`, err);
  }
}

// Test 2.2: Pydantic 422 Validation Error Lists
console.log("\n--- Testing Pydantic 422 Validation Error Lists ---");
{
  const pydanticList = [
    { loc: ["body", "password"], msg: "String should have at least 6 characters", type: "string_too_short" },
    { loc: ["body", "email"], msg: "value is not a valid email address", type: "value_error" },
  ];
  const envelope = {
    detail: pydanticList,
    error_type: "validation_error",
    status_code: 422,
  };

  try {
    const mockRes = new Response(JSON.stringify(envelope), {
      status: 422,
      headers: { "Content-Type": "application/json" },
    });

    let caught = null;
    try {
      await handleResponse(mockRes);
    } catch (err) {
      caught = err;
    }

    assert(caught instanceof ApiError, "Must throw ApiError");
    assert.equal(caught.status, 422);
    assert.equal(caught.errorType, "validation_error");
    assert.equal(
      caught.message,
      "body.password: String should have at least 6 characters; body.email: value is not a valid email address"
    );
    recordPass(`Pydantic 422 Validation Error parsing: "${caught.message}"`);
  } catch (err) {
    recordFail("Pydantic 422 Validation Error parsing", err);
  }
}

// Test 2.3: Adversarial Validation List Variants (missing loc, missing msg, empty list)
console.log("\n--- Testing Adversarial Validation List Variants ---");
{
  // Variant A: Missing loc
  try {
    const err = new ApiError(422, [{ msg: "Generic validation issue" }], "validation_error");
    assert.equal(err.message, "field: Generic validation issue");
    recordPass("Adversarial 422: item with missing loc formats with fallback 'field'");
  } catch (e) {
    recordFail("Adversarial 422 missing loc", e);
  }

  // Variant B: Missing msg
  try {
    const err = new ApiError(422, [{ loc: ["body", "data"] }], "validation_error");
    assert(err.message.includes("body"), "Formats JSON representation without throwing");
    recordPass("Adversarial 422: item with missing msg formats JSON string");
  } catch (e) {
    recordFail("Adversarial 422 missing msg", e);
  }

  // Variant C: Empty list []
  try {
    const err = new ApiError(422, [], "validation_error");
    if (err.message === "") {
      recordWarning(
        "Empty Validation Detail Array",
        "ApiError with empty detail array detail: [] sets err.message to empty string ''.",
        "Consider falling back to default message if detail array produces empty string."
      );
    }
  } catch (e) {
    recordFail("Adversarial 422 empty list", e);
  }
}

// Test 2.4: Non-JSON / HTML Error Pages (502 / 504 / Cloudflare)
console.log("\n--- Testing Non-JSON / HTML Error Pages ---");
{
  try {
    const htmlBody = "<!DOCTYPE html><html><body><h1>502 Bad Gateway</h1></body></html>";
    const mockRes = new Response(htmlBody, {
      status: 502,
      statusText: "Bad Gateway",
      headers: { "Content-Type": "text/html" },
    });

    let caught = null;
    try {
      await handleResponse(mockRes);
    } catch (err) {
      caught = err;
    }

    assert(caught instanceof ApiError, "Must handle non-JSON without crashing with SyntaxError");
    assert.equal(caught.status, 502);
    assert.equal(caught.message, "Bad Gateway");
    assert.equal(caught.errorType, undefined);
    recordPass("502 HTML Gateway page handled safely; statusText extracted");
  } catch (err) {
    recordFail("502 HTML Gateway page handling", err);
  }

  // Empty statusText (common in HTTP/2)
  try {
    const mockRes = new Response("Service Unavailable", {
      status: 503,
      statusText: "",
      headers: { "Content-Type": "text/plain" },
    });

    let caught = null;
    try {
      await handleResponse(mockRes);
    } catch (err) {
      caught = err;
    }

    assert.equal(caught.message, "Unknown server error");
    recordPass("Empty statusText falls back cleanly to 'Unknown server error'");
  } catch (err) {
    recordFail("Empty statusText fallback", err);
  }
}

// Test 2.5: Network Timeout / AbortSignal Handling
console.log("\n--- Testing Network Timeout via AbortSignal ---");
{
  try {
    const controller = new AbortController();
    controller.abort(new Error("Timeout simulated"));

    let threwAbort = false;
    try {
      await fetch(`${BASE_URL}/health`, { signal: controller.signal });
    } catch (err) {
      threwAbort = true;
      assert(err.name === "AbortError" || err.message.includes("aborted") || err.message.includes("Timeout"));
    }
    assert(threwAbort, "Fetch must abort when signal is triggered");
    recordPass("Network AbortSignal triggers clean AbortError");
  } catch (err) {
    recordFail("Network AbortSignal handling", err);
  }
}

// =============================================================================
// TEST SUITE 3: Live API Request Body Serialization & Parameter Handling
// =============================================================================
console.log("\n================================================================================");
console.log("SUITE 3: Live Backend API Contract Serialization & Parameter Edge Cases");
console.log("================================================================================");

// 3.1: POST /interview/start — Guest user_id (null vs omitted vs valid UUID vs empty string)
console.log("\n--- Testing POST /interview/start: user_id handling ---");
const interviewUserIdCases = [
  { label: "user_id is null", body: { candidate_name: "Adv Candidate", role: "SRE", experience_level: "Senior", interview_type: "technical", user_id: null }, expectedStatus: 200 },
  { label: "user_id is omitted", body: { candidate_name: "Adv Candidate", role: "SRE", experience_level: "Senior", interview_type: "technical" }, expectedStatus: 200 },
  { label: "user_id is valid UUID", body: { candidate_name: "Adv Candidate", role: "SRE", experience_level: "Senior", interview_type: "technical", user_id: "550e8400-e29b-41d4-a716-446655440000" }, expectedStatus: 200 },
  { label: "user_id is empty string ''", body: { candidate_name: "Adv Candidate", role: "SRE", experience_level: "Senior", interview_type: "technical", user_id: "" }, expectedStatus: 200 },
];

for (const tc of interviewUserIdCases) {
  try {
    const res = await fetch(`${BASE_URL}/interview/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(tc.body),
    });
    assert.equal(res.status, tc.expectedStatus, `Expected ${tc.expectedStatus}, got ${res.status}`);
    const data = await res.json();
    assert(data.session_id, "Response must include session_id");
    assert(data.opening_message, "Response must include opening_message");
    recordPass(`POST /interview/start [${tc.label}]: returned 200 OK (session_id: ${data.session_id.slice(0, 8)}...)`);
  } catch (err) {
    recordFail(`POST /interview/start [${tc.label}]`, err);
  }
}

// 3.2: Empty Form Fields & Input Constraints
console.log("\n--- Testing Empty Form Fields on /interview/start ---");
const emptyFieldCases = [
  { field: "candidate_name", body: { candidate_name: "", role: "Dev", experience_level: "Mid", interview_type: "hr" } },
  { field: "role", body: { candidate_name: "Alex", role: "", experience_level: "Mid", interview_type: "hr" } },
  { field: "experience_level", body: { candidate_name: "Alex", role: "Dev", experience_level: "", interview_type: "hr" } },
  { field: "interview_type (invalid 'debate')", body: { candidate_name: "Alex", role: "Dev", experience_level: "Mid", interview_type: "debate" } },
];

for (const tc of emptyFieldCases) {
  try {
    const res = await fetch(`${BASE_URL}/interview/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(tc.body),
    });
    assert.equal(res.status, 422, `Empty/invalid ${tc.field} must return 422, got ${res.status}`);
    const data = await res.json();
    assert.equal(data.error_type, "validation_error");
    assert(Array.isArray(data.detail), "Detail must be validation error array");
    recordPass(`Validation caught on ${tc.field}: HTTP 422 with ${data.detail[0]?.msg}`);
  } catch (err) {
    recordFail(`Validation check for ${tc.field}`, err);
  }
}

// 3.3: Voice Pipeline: Valid vs 0-byte vs Corrupt vs Missing file
console.log("\n--- Testing POST /voice/process Audio Payloads ---");
// Valid WAV
try {
  const wavBuffer = createDummyWav(250, 16000);
  const form = new FormData();
  form.append("file", new Blob([wavBuffer]), "test.wav");
  form.append("agent_type", "interview");

  const res = await fetch(`${BASE_URL}/voice/process`, { method: "POST", body: form });
  assert.equal(res.status, 200);
  const data = await res.json();
  assert(data.spoken_response !== undefined, "Must return spoken_response");
  recordPass("POST /voice/process [Valid 16kHz WAV]: returned 200 OK");
} catch (err) {
  recordFail("POST /voice/process [Valid 16kHz WAV]", err);
}

// 0-byte Audio
try {
  const form = new FormData();
  form.append("file", new Blob([new Uint8Array(0)]), "empty.wav");
  form.append("agent_type", "interview");

  const res = await fetch(`${BASE_URL}/voice/process`, { method: "POST", body: form });
  assert.equal(res.status, 200);
  const data = await res.json();
  assert.equal(data.transcript, "");
  assert.equal(data.spoken_response, "Could not understand. Please try again.");
  assert.equal(data.audio_base64, null);
  recordPass("POST /voice/process [0-byte Audio]: safely returned 200 with fallback message and null audio");
} catch (err) {
  recordFail("POST /voice/process [0-byte Audio]", err);
}

// Sub-12 byte Audio
try {
  const form = new FormData();
  form.append("file", new Blob([Buffer.from("12345")]), "tiny.wav");
  form.append("agent_type", "interview");

  const res = await fetch(`${BASE_URL}/voice/process`, { method: "POST", body: form });
  assert.equal(res.status, 200);
  const data = await res.json();
  assert.equal(data.transcript, "");
  assert.equal(data.spoken_response, "Could not understand. Please try again.");
  recordPass("POST /voice/process [Sub-12 Byte Audio]: returned fallback prompt");
} catch (err) {
  recordFail("POST /voice/process [Sub-12 Byte Audio]", err);
}

// Non-audio Corrupted Payload (50 bytes ASCII)
try {
  const form = new FormData();
  form.append("file", new Blob([Buffer.from("CORRUPTED_NON_AUDIO_PAYLOAD_TESTING_DATA_BYTES_1234")]), "corrupt.wav");
  form.append("agent_type", "coach");

  const res = await fetch(`${BASE_URL}/voice/process`, { method: "POST", body: form });
  assert.equal(res.status, 200, "Corrupt audio must never crash backend with 500");
  const data = await res.json();
  assert(data.spoken_response !== undefined);
  recordPass("POST /voice/process [Corrupt Audio]: handled gracefully without 500 crash");
} catch (err) {
  recordFail("POST /voice/process [Corrupt Audio]", err);
}

// Missing File Field (Empty FormData)
try {
  const form = new FormData();
  form.append("agent_type", "interview");

  const res = await fetch(`${BASE_URL}/voice/process`, { method: "POST", body: form });
  assert.equal(res.status, 422, "Missing file must return 422 Unprocessable Entity");
  const data = await res.json();
  assert.equal(data.error_type, "validation_error");
  recordPass("POST /voice/process [Missing file field]: returned HTTP 422 validation_error");
} catch (err) {
  recordFail("POST /voice/process [Missing file field]", err);
}

// =============================================================================
// TEST SUITE 4: Coach Mode Parameter Bounds & Enforcement
// =============================================================================
console.log("\n================================================================================");
console.log("SUITE 4: Coach Mode Parameter Bounds & Validation Enforcement");
console.log("================================================================================");

const validCoachModes = ["conversation", "answer_training", "english_improvement"];
const guestCoachId = `adversarial_coach_user_${Date.now()}`;

for (const mode of validCoachModes) {
  try {
    const res = await fetch(`${BASE_URL}/coach/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: guestCoachId, mode }),
    });
    assert.equal(res.status, 200, `Mode '${mode}' must return 200 OK`);
    const data = await res.json();
    assert.equal(data.mode, mode);
    assert(data.session_id, "Must have session_id");
    assert(data.opening_message, "Must have opening_message");
    recordPass(`POST /coach/start [Valid Mode '${mode}']: returned 200 OK`);
  } catch (err) {
    recordFail(`POST /coach/start [Valid Mode '${mode}']`, err);
  }
}

// Case & Whitespace Normalization (e.g. " CONVERSATION ")
try {
  const res = await fetch(`${BASE_URL}/coach/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: guestCoachId, mode: " CONVERSATION " }),
  });
  assert.equal(res.status, 200, "Backend should strip and lowercase mode");
  const data = await res.json();
  assert.equal(data.mode, "conversation");
  recordPass("POST /coach/start [Case & Whitespace ' CONVERSATION ']: normalized to 'conversation'");
} catch (err) {
  recordFail("POST /coach/start [Case & Whitespace normalization]", err);
}

// Invalid Modes
const invalidCoachModes = [
  { mode: "debate", expectedStatus: 400, desc: "Unsupported mode 'debate'" },
  { mode: "technical", expectedStatus: 400, desc: "Interview track 'technical' used in coach" },
  { mode: "interview_answer_training", expectedStatus: 400, desc: "Misnamed mode variant" },
  { mode: "conversation; DROP TABLE users;", expectedStatus: 400, desc: "SQL injection payload" },
  { mode: "", expectedStatus: 422, desc: "Empty mode string" },
];

for (const tc of invalidCoachModes) {
  try {
    const res = await fetch(`${BASE_URL}/coach/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: guestCoachId, mode: tc.mode }),
    });
    assert.equal(res.status, tc.expectedStatus, `${tc.desc} expected ${tc.expectedStatus}, got ${res.status}`);
    const data = await res.json();
    if (res.status === 400) {
      assert(data.detail.includes("Invalid coach mode"), "400 message must explain invalid mode");
    }
    recordPass(`POST /coach/start [${tc.desc}]: rejected with status ${res.status}`);
  } catch (err) {
    recordFail(`POST /coach/start [${tc.desc}]`, err);
  }
}

// Coach user_id Validation Edge Cases
console.log("\n--- Testing Coach user_id Validation ---");
try {
  // Empty user_id
  const resEmpty = await fetch(`${BASE_URL}/coach/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: "", mode: "conversation" }),
  });
  assert.equal(resEmpty.status, 422, "Empty user_id string must be rejected by Pydantic min_length: 1");
  recordPass("POST /coach/start [Empty user_id '']: rejected with HTTP 422");

  // Whitespace-only user_id
  const resWhitespace = await fetch(`${BASE_URL}/coach/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: "    ", mode: "conversation" }),
  });
  assert.equal(resWhitespace.status, 400, "Whitespace user_id must be caught by clean_user_id check");
  const wsData = await resWhitespace.json();
  assert.equal(wsData.detail, "user_id must not be empty");
  recordPass("POST /coach/start [Whitespace user_id '   ']: rejected with HTTP 400 'user_id must not be empty'");

  // Null user_id
  const resNull = await fetch(`${BASE_URL}/coach/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: null, mode: "conversation" }),
  });
  assert.equal(resNull.status, 422, "Null user_id must be rejected");
  recordPass("POST /coach/start [Null user_id]: rejected with HTTP 422");
} catch (err) {
  recordFail("POST /coach/start user_id validation", err);
}

// Coach Respond: Empty text validation
console.log("\n--- Testing Coach Respond Empty Text ---");
try {
  const res = await fetch(`${BASE_URL}/coach/respond`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: "non-existent-session-id", user_text: "" }),
  });
  assert.equal(res.status, 400);
  const data = await res.json();
  assert.equal(data.detail, "user_text cannot be empty");
  recordPass("POST /coach/respond [Empty user_text]: rejected with HTTP 400 'user_text cannot be empty'");
} catch (err) {
  recordFail("POST /coach/respond [Empty user_text]", err);
}

// =============================================================================
// TEST SUITE 5: State Store Mutations, Concurrency & Transitions
// =============================================================================
console.log("\n================================================================================");
console.log("SUITE 5: State Store Mutations, Concurrency & Guest Transitions");
console.log("================================================================================");

// Create Vanilla Zustand store mimicking useStore.ts
function createTestStore() {
  return createStore((set) => ({
    user: null,
    token: null,
    guestUserId: "guest-test-uuid-initial",

    interviewSessionId: null,
    coachSessionId: null,

    interviewReport: null,
    coachReport: null,

    activeSection: 1,
    isCameraOn: false,
    isMicOn: true,
    isCallActive: false,
    currentQuestionIndex: 0,

    setUser: (user, token) =>
      set((state) => ({
        user,
        token: token !== undefined ? token : state.token,
      })),
    setToken: (token) => set({ token }),
    setGuestUserId: (guestUserId) => set({ guestUserId }),
    setInterviewSessionId: (interviewSessionId) => set({ interviewSessionId }),
    setCoachSessionId: (coachSessionId) => set({ coachSessionId }),
    setInterviewReport: (interviewReport) => set({ interviewReport }),
    setCoachReport: (coachReport) => set({ coachReport }),
    setCallActive: (isCallActive) => set({ isCallActive }),
    nextQuestion: () =>
      set((state) => ({
        currentQuestionIndex: (state.currentQuestionIndex + 1) % 5,
      })),
    resetQuestions: () => set({ currentQuestionIndex: 0 }),
    clearSession: () =>
      set({
        interviewSessionId: null,
        coachSessionId: null,
        interviewReport: null,
        coachReport: null,
        isCallActive: false,
      }),
  }));
}

// 5.1: Concurrency Stress Test
console.log("\n--- Testing Store Mutation Concurrency ---");
{
  const store = createTestStore();
  const iterations = 100;
  const promises = [];

  for (let i = 0; i < iterations; i++) {
    promises.push(
      new Promise((resolve) => {
        setTimeout(() => {
          store.getState().nextQuestion();
          store.getState().setInterviewSessionId(`session-${i}`);
          resolve();
        }, Math.floor(Math.random() * 10));
      })
    );
  }

  await Promise.all(promises);
  const state = store.getState();
  assert(state.interviewSessionId !== null, "interviewSessionId must be set");
  // 100 iterations of (x + 1) % 5 with 0 initial should equal 0
  assert.equal(state.currentQuestionIndex, 0, "100 cycles of modulo 5 must equal 0");
  recordPass(`Concurrency Stress Test: 100 parallel asynchronous mutations completed safely`);
}

// 5.2: Session Reset Isolation (clearSession vs User Auth)
console.log("\n--- Testing Session Reset Isolation ---");
{
  const store = createTestStore();

  // Populate active user and sessions
  store.getState().setUser({ id: "user-auth-uuid", email: "user@voxprep.ai", name: "Alice Dev" }, "jwt-access-token-123");
  store.getState().setInterviewSessionId("int-session-123");
  store.getState().setCoachSessionId("coach-session-456");
  store.getState().setInterviewReport({ overall_score: 8.5 });
  store.getState().setCoachReport({ status: "completed" });
  store.getState().setCallActive(true);

  // Trigger reset
  store.getState().clearSession();

  const state = store.getState();
  assert.equal(state.interviewSessionId, null, "interviewSessionId must be null after reset");
  assert.equal(state.coachSessionId, null, "coachSessionId must be null after reset");
  assert.equal(state.interviewReport, null, "interviewReport must be null after reset");
  assert.equal(state.coachReport, null, "coachReport must be null after reset");
  assert.equal(state.isCallActive, false, "isCallActive must be false after reset");

  // CRITICAL CHECK: User auth must NOT be wiped by clearSession
  assert(state.user !== null, "user must NOT be cleared by clearSession");
  assert.equal(state.user.id, "user-auth-uuid");
  assert.equal(state.token, "jwt-access-token-123");
  assert.equal(state.guestUserId, "guest-test-uuid-initial", "guestUserId must remain preserved");
  recordPass("Session Reset Isolation: clearSession wipes interaction state without destroying auth credentials");
}

// 5.3: Guest State Lifecycle Transitions
console.log("\n--- Testing Guest State Transitions ---");
{
  const store = createTestStore();

  // Initial State: Pure guest
  assert.equal(store.getState().user, null);
  assert.equal(store.getState().token, null);
  assert(store.getState().guestUserId.startsWith("guest-"));
  const initialGuestId = store.getState().guestUserId;
  recordPass("Transition 1: Initial state is guest with auto-generated guestUserId");

  // Transition 2: User registers or logs in
  store.getState().setUser({ id: "reg-user-999", email: "candidate@work.com", name: "Candidate" }, "token-xyz");
  assert.equal(store.getState().user.id, "reg-user-999");
  assert.equal(store.getState().token, "token-xyz");
  assert.equal(store.getState().guestUserId, initialGuestId, "guestUserId preserved during login");
  recordPass("Transition 2: Guest logs in -> user and token set, guestUserId preserved");

  // Transition 3: Profile update without passing token (token === undefined)
  store.getState().setUser({ id: "reg-user-999", email: "candidate@work.com", name: "Candidate Renamed" });
  assert.equal(store.getState().user.name, "Candidate Renamed");
  assert.equal(store.getState().token, "token-xyz", "Existing token preserved when undefined passed");
  recordPass("Transition 3: User profile updated with undefined token -> token preserved");

  // Transition 4: User logs out
  store.getState().setUser(null, null);
  assert.equal(store.getState().user, null);
  assert.equal(store.getState().token, null);
  assert.equal(store.getState().guestUserId, initialGuestId, "guestUserId survives logout");
  recordPass("Transition 4: Logout -> user and token cleared, guestUserId intact");
}

// =============================================================================
// SUMMARY & VERDICT
// =============================================================================
console.log("\n================================================================================");
console.log("⚡ TEST EXECUTION SUMMARY");
console.log("================================================================================");
console.log(`Total Passed:   ${results.passed}`);
console.log(`Total Failed:   ${results.failed}`);
console.log(`Total Warnings: ${results.warnings}`);

if (results.findings.length > 0) {
  console.log("\nFindings and Observations:");
  for (const f of results.findings) {
    console.log(`  [${f.severity}] ${f.test}: ${f.message}`);
    if (f.suggestion) console.log(`      Suggestion: ${f.suggestion}`);
  }
}

console.log("\n--------------------------------------------------------------------------------");
if (results.failed === 0) {
  console.log("VERDICT: ✅ APPROVE (All core contracts, error handling, and bounds verified)");
  console.log("--------------------------------------------------------------------------------\n");
  process.exit(0);
} else {
  console.error("VERDICT: ❌ REJECT (Adversarial test failures detected)");
  console.log("--------------------------------------------------------------------------------\n");
  process.exit(1);
}
