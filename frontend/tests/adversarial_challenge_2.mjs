// frontend/tests/adversarial_challenge_2.mjs
// Adversarial Integration Stress & Boundary Verification Harness
// Target Backend: http://127.0.0.1:8000

import assert from "node:assert/strict";

const BASE_URL = process.env.API_URL || "http://127.0.0.1:8000";

console.log("================================================================================");
console.log("=== VOXPREP ADVERSARIAL CHALLENGER 2: LIVE BOUNDARY & STRESS VERIFICATION ===");
console.log(`=== Target: ${BASE_URL} ===`);
console.log("================================================================================\n");

// --- Helper Functions ---

function createWavBuffer(durationMs = 500, sampleRate = 16000) {
  const numSamples = Math.floor(sampleRate * (durationMs / 1000));
  const dataSize = numSamples * 2;
  const buffer = Buffer.alloc(44 + dataSize);

  // RIFF chunk descriptor
  buffer.write("RIFF", 0);
  buffer.writeUInt32LE(36 + dataSize, 4);
  buffer.write("WAVE", 8);

  // "fmt " sub-chunk
  buffer.write("fmt ", 12);
  buffer.writeUInt32LE(16, 16); // Subchunk1Size (16 for PCM)
  buffer.writeUInt16LE(1, 20);  // AudioFormat (1 = PCM)
  buffer.writeUInt16LE(1, 22);  // NumChannels (1 = Mono)
  buffer.writeUInt32LE(sampleRate, 24); // SampleRate (16000)
  buffer.writeUInt32LE(sampleRate * 2, 28); // ByteRate (16000 * 1 * 2)
  buffer.writeUInt16LE(2, 32);  // BlockAlign (1 * 2)
  buffer.writeUInt16LE(16, 34); // BitsPerSample (16)

  // "data" sub-chunk
  buffer.write("data", 36);
  buffer.writeUInt32LE(dataSize, 40);

  // Fill with 440Hz test sine tone
  for (let i = 0; i < numSamples; i++) {
    const t = i / sampleRate;
    const sample = Math.floor(Math.sin(2 * Math.PI * 440 * t) * 16000);
    buffer.writeInt16LE(sample, 44 + i * 2);
  }

  return buffer;
}

function normalizeScore(score, fallback = 0) {
  if (score === undefined || score === null || isNaN(score)) return fallback;
  return score <= 10 ? Math.round(score * 10) : Math.round(score);
}

let passCount = 0;
let failCount = 0;

function reportResult(name, passed, detail = "") {
  if (passed) {
    passCount++;
    console.log(`  [PASS] ${name}${detail ? ` (${detail})` : ""}`);
  } else {
    failCount++;
    console.error(`  [FAIL] ${name}${detail ? ` - ${detail}` : ""}`);
  }
}

async function run() {
  // Check backend health
  console.log("Checking backend health...");
  const healthRes = await fetch(`${BASE_URL}/health`);
  assert.equal(healthRes.status, 200, "Backend must return 200 OK on /health");
  const healthJson = await healthRes.json();
  assert.equal(healthJson.status, "ok", "Backend health status must be 'ok'");
  console.log("Backend is healthy.\n");

  // =========================================================================
  // SUITE 1: Full Interview Round (Guest Access, Follow-up, Rubric Scoring)
  // =========================================================================
  console.log("--------------------------------------------------------------------------------");
  console.log("SUITE 1: Full Interview Round & Rubric Scoring Bounds");
  console.log("--------------------------------------------------------------------------------");
  try {
    // 1.1 Start interview as guest (user_id = null)
    const startPayload = {
      candidate_name: "Empirical Candidate",
      role: "Distributed Systems Engineer",
      experience_level: "Senior",
      interview_type: "technical",
      user_id: null,
    };
    const startRes = await fetch(`${BASE_URL}/interview/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(startPayload),
    });
    assert.equal(startRes.status, 200, "POST /interview/start should return 200");
    const startData = await startRes.json();
    assert.ok(startData.session_id, "session_id must be non-empty");
    assert.ok(startData.opening_message, "opening_message must be non-empty");
    const sessionId = startData.session_id;
    reportResult("1.1 Guest Interview Initialization", true, `session_id: ${sessionId}`);

    // 1.2 Boundary check: Fetching report while session is in progress must fail cleanly with 400
    const inProgressReportRes = await fetch(`${BASE_URL}/interview/report/${sessionId}`);
    assert.equal(inProgressReportRes.status, 400, "In-progress report fetch must return 400");
    const inProgressReportErr = await inProgressReportRes.json();
    assert.ok(
      typeof inProgressReportErr.detail === "string" &&
        inProgressReportErr.detail.toLowerCase().includes("not yet completed"),
      "Detail must indicate interview is not completed"
    );
    reportResult("1.2 In-Progress Report Fetch Rejection (400)", true);

    // 1.3 Answer 1: Provide technical response to trigger follow-up probe
    const ans1Payload = {
      session_id: sessionId,
      answer_text: "In distributed architectures, I rely on asynchronous I/O and event-driven patterns with non-blocking sockets. For CPU-bound operations, we distribute work to background workers, whereas I/O bound pipelines scale via event loops.",
    };
    const ans1Res = await fetch(`${BASE_URL}/interview/respond`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(ans1Payload),
    });
    assert.equal(ans1Res.status, 200, "POST /interview/respond (Turn 1) should return 200");
    const ans1Data = await ans1Res.json();
    assert.equal(ans1Data.is_complete, false, "Interview must not be completed after turn 1");
    assert.equal(ans1Data.follow_up_or_next, "follow_up", "Turn 1 must trigger follow_up");
    assert.ok(ans1Data.spoken_response && ans1Data.spoken_response.length > 0, "Spoken follow-up must be returned");
    reportResult("1.3 Turn 1 Answer & Follow-up Generation", true, `follow_up_or_next: ${ans1Data.follow_up_or_next}`);

    // 1.4 Answer 2: Address the follow-up question, advancing question index
    const ans2Payload = {
      session_id: sessionId,
      answer_text: "To guarantee idempotency and avoid cache stampedes, we attach distributed UUID idempotency keys with mutual exclusion locks and Redis TTL jittering across all replica nodes.",
    };
    const ans2Res = await fetch(`${BASE_URL}/interview/respond`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(ans2Payload),
    });
    assert.equal(ans2Res.status, 200, "POST /interview/respond (Turn 2) should return 200");
    const ans2Data = await ans2Res.json();
    assert.equal(ans2Data.follow_up_or_next, "next", "Turn 2 after follow-up must advance to next question");
    assert.ok(ans2Data.spoken_response && ans2Data.spoken_response.length > 0, "Next question prompt must be returned");
    reportResult("1.4 Turn 2 Answer Progression to Next Question", true, `follow_up_or_next: ${ans2Data.follow_up_or_next}`);

    // 1.5 Conclude interview via POST /interview/end
    const endRes = await fetch(`${BASE_URL}/interview/end`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId }),
    });
    assert.equal(endRes.status, 200, "POST /interview/end should return 200");
    const endData = await endRes.json();
    assert.equal(endData.session_id, sessionId, "session_id must match");
    assert.equal(endData.status, "completed", "Status must be completed");
    assert.ok(endData.report, "Generated report must be returned on end");
    reportResult("1.5 Interview Conclusion & Report Generation", true);

    // 1.6 Fetch finalized report via GET /interview/report/{session_id}
    const reportRes = await fetch(`${BASE_URL}/interview/report/${sessionId}`);
    assert.equal(reportRes.status, 200, "GET /interview/report/{session_id} must return 200");
    const report = await reportRes.json();

    // 1.7 Assert Rubric Dimensions in [1.0, 10.0] and Normalized Score in [0, 100]
    assert.ok(report.dimension_scores, "Report must include dimension_scores");
    const { relevance, clarity, depth, examples } = report.dimension_scores;

    assert.ok(typeof relevance === "number" && relevance >= 1.0 && relevance <= 10.0, `relevance ${relevance} must be in [1.0, 10.0]`);
    assert.ok(typeof clarity === "number" && clarity >= 1.0 && clarity <= 10.0, `clarity ${clarity} must be in [1.0, 10.0]`);
    assert.ok(typeof depth === "number" && depth >= 1.0 && depth <= 10.0, `depth ${depth} must be in [1.0, 10.0]`);
    assert.ok(typeof examples === "number" && examples >= 1.0 && examples <= 10.0, `examples ${examples} must be in [1.0, 10.0]`);
    assert.ok(typeof report.overall_score === "number" && report.overall_score >= 1.0 && report.overall_score <= 10.0, `overall_score ${report.overall_score} must be in [1.0, 10.0]`);

    // Normalized percentage bounds assertion
    const normOverall = normalizeScore(report.overall_score);
    const normRelevance = normalizeScore(relevance);
    const normClarity = normalizeScore(clarity);
    const normDepth = normalizeScore(depth);
    const normExamples = normalizeScore(examples);

    assert.ok(normOverall >= 0 && normOverall <= 100, `normOverall ${normOverall}% must be in [0, 100]`);
    assert.ok(normRelevance >= 0 && normRelevance <= 100, `normRelevance ${normRelevance}% must be in [0, 100]`);
    assert.ok(normClarity >= 0 && normClarity <= 100, `normClarity ${normClarity}% must be in [0, 100]`);
    assert.ok(normDepth >= 0 && normDepth <= 100, `normDepth ${normDepth}% must be in [0, 100]`);
    assert.ok(normExamples >= 0 && normExamples <= 100, `normExamples ${normExamples}% must be in [0, 100]`);

    assert.ok(Array.isArray(report.strengths) && report.strengths.length > 0, "Strengths must be a non-empty array");
    assert.ok(Array.isArray(report.areas_for_improvement) && report.areas_for_improvement.length > 0, "Areas for improvement must be a non-empty array");
    assert.ok(Array.isArray(report.question_breakdown) && report.question_breakdown.length > 0, "Question breakdown must be non-empty");

    reportResult(
      "1.7 Rubric Dimension Bounds [1.0, 10.0] & Percentage [0, 100]",
      true,
      `Overall: ${report.overall_score} -> ${normOverall}%, Rel: ${relevance}, Clar: ${clarity}, Dep: ${depth}, Ex: ${examples}`
    );
  } catch (err) {
    reportResult("SUITE 1 Full Interview Round", false, err.message);
  }

  // =========================================================================
  // SUITE 2: AI Communication Coach in All 3 Modes
  // =========================================================================
  console.log("\n--------------------------------------------------------------------------------");
  console.log("SUITE 2: AI Communication Coach in All 3 Modes (Error -> Clean -> Summary)");
  console.log("--------------------------------------------------------------------------------");

  const coachModes = [
    {
      mode: "english_improvement",
      flawedAnswer: "Yesterday I was go to the store and buyed some groceries.",
      cleanAnswer: "I usually prepare meals with fresh vegetables and read engineering blogs in the evening.",
    },
    {
      mode: "conversation",
      flawedAnswer: "Last week I was go to a tech conference with my team.",
      cleanAnswer: "I really enjoy building open-source developer tooling and mentoring junior engineers.",
    },
    {
      mode: "answer_training",
      flawedAnswer: "I worked on a software system at my previous job and we held lots of meetings about our progress every single week.",
      cleanAnswer: "In that situation, our API was experiencing high latency. My task was to identify bottlenecks. I took action by indexing database queries and adding Redis caching, and the result was a 60% reduction in response time.",
    },
  ];

  for (const item of coachModes) {
    try {
      console.log(`\nTesting Coach Mode: [${item.mode}]`);
      const userId = `adversarial-user-${Date.now()}-${item.mode}`;

      // 2.1 Start Coach Session
      const startRes = await fetch(`${BASE_URL}/coach/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId, mode: item.mode }),
      });
      assert.equal(startRes.status, 200, `POST /coach/start (${item.mode}) should return 200`);
      const startData = await startRes.json();
      assert.ok(startData.session_id, "Coach session_id must be generated");
      assert.equal(startData.mode, item.mode, "Active mode must match requested mode");
      assert.ok(startData.opening_message, "opening_message must be present");
      const coachSid = startData.session_id;
      reportResult(`2.1 [${item.mode}] Start Session`, true, `session_id: ${coachSid}`);

      // 2.2 Submit Flawed Speech to trigger correction { original, improved, reason }
      const flawedRes = await fetch(`${BASE_URL}/coach/respond`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: coachSid, user_text: item.flawedAnswer }),
      });
      assert.equal(flawedRes.status, 200, `POST /coach/respond (${item.mode} flawed) should return 200`);
      const flawedData = await flawedRes.json();
      assert.ok(flawedData.coach_message, "coach_message must be present");
      assert.ok(flawedData.correction, "correction object MUST be present for flawed speech");
      assert.ok(typeof flawedData.correction.original === "string" && flawedData.correction.original.length > 0, "correction.original must be non-empty string");
      assert.ok(typeof flawedData.correction.improved === "string" && flawedData.correction.improved.length > 0, "correction.improved must be non-empty string");
      assert.ok(typeof flawedData.correction.reason === "string" && flawedData.correction.reason.length > 0, "correction.reason must be non-empty string");
      reportResult(
        `2.2 [${item.mode}] Grammatical / Structural Correction Triggered`,
        true,
        `Original: "${flawedData.correction.original}" -> Improved: "${flawedData.correction.improved}"`
      );

      // 2.3 Submit Clean Speech to verify correction is null
      const cleanRes = await fetch(`${BASE_URL}/coach/respond`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: coachSid, user_text: item.cleanAnswer }),
      });
      assert.equal(cleanRes.status, 200, `POST /coach/respond (${item.mode} clean) should return 200`);
      const cleanData = await cleanRes.json();
      assert.ok(cleanData.coach_message, "coach_message must be present");
      assert.equal(cleanData.correction, null, "correction MUST be null for clean response");
      reportResult(`2.3 [${item.mode}] Clean Speech Evaluated (correction: null)`, true);

      // 2.4 End Coach Session and assert summary & profile
      const endRes = await fetch(`${BASE_URL}/coach/end`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: coachSid }),
      });
      assert.equal(endRes.status, 200, `POST /coach/end (${item.mode}) should return 200`);
      const endData = await endRes.json();
      assert.equal(endData.session_id, coachSid, "session_id must match");
      assert.equal(endData.status, "completed", "status must be 'completed'");
      assert.ok(endData.summary, "Summary must be present");
      assert.ok(endData.profile_updated, "profile_updated must be present");
      assert.ok(
        endData.summary.exchanges_count >= 2,
        `exchanges_count (${endData.summary.exchanges_count}) must be >= 2`
      );
      assert.ok(
        ["beginner", "intermediate", "advanced"].includes(endData.profile_updated.skill_level),
        `skill_level (${endData.profile_updated.skill_level}) must be valid`
      );
      reportResult(
        `2.4 [${item.mode}] Session End & Summary/Profile Assertions`,
        true,
        `Exchanges: ${endData.summary.exchanges_count}, Skill: ${endData.profile_updated.skill_level}`
      );

      // 2.5 Responding to completed coach session must return HTTP 400
      const postEndRes = await fetch(`${BASE_URL}/coach/respond`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: coachSid, user_text: "Can I still speak?" }),
      });
      assert.equal(postEndRes.status, 400, "Responding to completed coach session must return 400");
      reportResult(`2.5 [${item.mode}] Completed Session Rejection Guardrail (400)`, true);

      // 2.6 Repeated /coach/end calls must be idempotent HTTP 200
      const repeatEndRes = await fetch(`${BASE_URL}/coach/end`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: coachSid }),
      });
      assert.equal(repeatEndRes.status, 200, "Repeated /coach/end must return 200 idempotently");
      reportResult(`2.6 [${item.mode}] End Session Idempotency (200)`, true);
    } catch (err) {
      reportResult(`SUITE 2 Coach Mode [${item.mode}]`, false, err.message);
    }
  }

  // =========================================================================
  // SUITE 3: Auth Boundary Rejection
  // =========================================================================
  console.log("\n--------------------------------------------------------------------------------");
  console.log("SUITE 3: Auth Boundary (Duplicate Registration 400, Bad Password 401)");
  console.log("--------------------------------------------------------------------------------");
  try {
    const testEmail = `adversary_${Date.now()}_${Math.floor(Math.random() * 10000)}@voxprep.io`;
    const testPassword = "AdversarialPassword123!";

    // 3.1 Initial clean registration -> 201 Created
    const regRes1 = await fetch(`${BASE_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: testEmail,
        password: testPassword,
        name: "Security Tester",
      }),
    });
    assert.equal(regRes1.status, 201, "First registration must return 201 Created");
    const regData1 = await regRes1.json();
    assert.ok(regData1.user && regData1.user.id, "Registered user must have an id");
    assert.ok(regData1.access_token, "access_token must be returned");
    reportResult("3.1 Initial User Registration", true, `email: ${testEmail}`);

    // 3.2 Duplicate registration attempt -> Clean HTTP 400 rejection
    const regRes2 = await fetch(`${BASE_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: testEmail,
        password: testPassword,
        name: "Duplicate Tester",
      }),
    });
    assert.equal(regRes2.status, 400, "Duplicate registration must return HTTP 400");
    const regErr2 = await regRes2.json();
    assert.ok(
      typeof regErr2.detail === "string" &&
        regErr2.detail.toLowerCase().includes("already registered"),
      `Error detail must state 'already registered', got: ${JSON.stringify(regErr2)}`
    );
    reportResult("3.2 Duplicate Email Rejection (400 Bad Request)", true, regErr2.detail);

    // 3.3 Bad login password -> Clean HTTP 401 rejection
    const badLoginRes = await fetch(`${BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: testEmail,
        password: "CompletelyWrongPassword!#999",
      }),
    });
    assert.equal(badLoginRes.status, 401, "Bad password login must return HTTP 401");
    const badLoginErr = await badLoginRes.json();
    assert.ok(
      typeof badLoginErr.detail === "string" &&
        badLoginErr.detail.toLowerCase().includes("invalid email or password"),
      `Error detail must state 'Invalid email or password', got: ${JSON.stringify(badLoginErr)}`
    );
    reportResult("3.3 Invalid Password Rejection (401 Unauthorized)", true, badLoginErr.detail);

    // 3.4 Invalid email format -> HTTP 400 Bad Request
    const badEmailRes = await fetch(`${BASE_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: "not-a-valid-email-address",
        password: "ValidPassword123!",
      }),
    });
    assert.equal(badEmailRes.status, 400, "Invalid email format must return HTTP 400");
    reportResult("3.4 Invalid Email Syntax Rejection (400 Bad Request)", true);

    // 3.5 Password too short (< 6 chars) -> HTTP 422 Unprocessable Entity
    const shortPassRes = await fetch(`${BASE_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: `short_pass_${Date.now()}@voxprep.io`,
        password: "123",
      }),
    });
    assert.equal(shortPassRes.status, 422, "Short password must fail Pydantic validation with 422");
    reportResult("3.5 Short Password (< 6 chars) Validation Rejection (422)", true);

    // 3.6 Successful login with valid credentials -> 200 OK
    const validLoginRes = await fetch(`${BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: testEmail,
        password: testPassword,
      }),
    });
    assert.equal(validLoginRes.status, 200, "Valid login must return HTTP 200");
    const validLoginData = await validLoginRes.json();
    assert.equal(validLoginData.user.email, testEmail, "Logged-in user email must match");
    assert.ok(validLoginData.access_token, "access_token must be returned");
    reportResult("3.6 Valid Login Authentication (200 OK)", true);
  } catch (err) {
    reportResult("SUITE 3 Auth Boundary Rejection", false, err.message);
  }

  // =========================================================================
  // SUITE 4: Voice Upload (16kHz mono PCM WAV & Response Schema)
  // =========================================================================
  console.log("\n--------------------------------------------------------------------------------");
  console.log("SUITE 4: Voice Upload Pipeline & Guardrails (16kHz Mono PCM WAV)");
  console.log("--------------------------------------------------------------------------------");
  try {
    // 4.1 Valid 16kHz mono 16-bit PCM WAV upload to /voice/process
    const wavBuffer = createWavBuffer(500, 16000);
    assert.equal(wavBuffer.length, 44 + 500 * 16 * 2, "WAV buffer size must be 16044 bytes");

    const formData = new FormData();
    const blob = new Blob([wavBuffer], { type: "audio/wav" });
    formData.append("file", blob, "test_speech_16khz.wav");
    formData.append("agent_type", "interview");
    formData.append("conversation_history", "Introduction question");

    const voiceRes = await fetch(`${BASE_URL}/voice/process`, {
      method: "POST",
      body: formData,
    });
    assert.equal(voiceRes.status, 200, "POST /voice/process must return 200 OK");
    const voiceData = await voiceRes.json();

    // Verify schema contract
    assert.ok(typeof voiceData.transcript === "string", "transcript must be a string");
    assert.ok(typeof voiceData.spoken_response === "string" && voiceData.spoken_response.length > 0, "spoken_response must be non-empty string");
    assert.ok(voiceData.audio_base64 === null || typeof voiceData.audio_base64 === "string", "audio_base64 must be string or null");
    assert.ok(voiceData.session_id === null || typeof voiceData.session_id === "string", "session_id must be string or null");

    reportResult(
      "4.1 16kHz Mono PCM WAV Voice Upload & Schema Conformance",
      true,
      `Transcript: "${voiceData.transcript}", Spoken: "${voiceData.spoken_response.substring(0, 50)}...", Audio: ${voiceData.audio_base64 ? "base64" : "null (Web Speech fallback)"}`
    );

    // 4.2 Adversarial Guardrail: Empty / Truncated audio file (< 12 bytes)
    const emptyForm = new FormData();
    const emptyBlob = new Blob([Buffer.from("EMPTY")], { type: "audio/wav" });
    emptyForm.append("file", emptyBlob, "corrupt.wav");
    emptyForm.append("agent_type", "coach");

    const corruptRes = await fetch(`${BASE_URL}/voice/process`, {
      method: "POST",
      body: emptyForm,
    });
    assert.equal(corruptRes.status, 200, "Corrupt audio must return HTTP 200 without crashing");
    const corruptData = await corruptRes.json();
    assert.equal(corruptData.transcript, "", "Corrupt audio transcript must be empty string");
    assert.equal(corruptData.spoken_response, "Could not understand. Please try again.", "Friendly fallback prompt expected");
    assert.equal(corruptData.audio_base64, null, "audio_base64 must be null on STT failure");
    reportResult("4.2 Empty / Truncated Audio Fallback Guardrail (200 OK)", true);
  } catch (err) {
    reportResult("SUITE 4 Voice Upload Pipeline", false, err.message);
  }

  // =========================================================================
  // SUITE 5: Global Edge Case & Parameter Validation
  // =========================================================================
  console.log("\n--------------------------------------------------------------------------------");
  console.log("SUITE 5: Global Edge Case & Parameter Validation");
  console.log("--------------------------------------------------------------------------------");
  try {
    // 5.1 Invalid interview type -> 422
    const badTrackRes = await fetch(`${BASE_URL}/interview/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        candidate_name: "Test",
        role: "Engineer",
        experience_level: "Mid",
        interview_type: "debate_mastery", // Invalid!
      }),
    });
    assert.equal(badTrackRes.status, 422, "Invalid interview_type must return 422");
    reportResult("5.1 Invalid Interview Type Validation (422)", true);

    // 5.2 Invalid coach mode -> 400
    const badCoachModeRes = await fetch(`${BASE_URL}/coach/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: "user-123",
        mode: "hostile_cross_examination", // Invalid!
      }),
    });
    assert.equal(badCoachModeRes.status, 400, "Invalid coach mode must return 400");
    reportResult("5.2 Invalid Coach Mode Validation (400)", true);

    // 5.3 Empty user_text on coach respond -> 400
    const dummyCoachStart = await (await fetch(`${BASE_URL}/coach/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: "edge-user-999", mode: "conversation" }),
    })).json();

    const emptyTextRes = await fetch(`${BASE_URL}/coach/respond`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: dummyCoachStart.session_id,
        user_text: "   ", // Whitespace only
      }),
    });
    assert.equal(emptyTextRes.status, 400, "Empty user_text must return 400");
    reportResult("5.3 Empty user_text Rejection (400)", true);

    // 5.4 Non-existent interview session -> 404
    const fakeInterviewRes = await fetch(`${BASE_URL}/interview/respond`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: "00000000-0000-0000-0000-000000000000",
        answer_text: "Test answer",
      }),
    });
    assert.equal(fakeInterviewRes.status, 404, "Non-existent interview session must return 404");
    reportResult("5.4 Non-Existent Interview Session Rejection (404)", true);
  } catch (err) {
    reportResult("SUITE 5 Global Edge Cases", false, err.message);
  }

  // --- Final Summary ---
  console.log("\n================================================================================");
  console.log("=== EMPIRICAL CHALLENGE 2 SUMMARY ===");
  console.log(`=== Total Tests Passed: ${passCount} ===`);
  console.log(`=== Total Tests Failed: ${failCount} ===`);
  console.log("================================================================================\n");

  if (failCount > 0) {
    console.error(`VERDICT: REJECT - ${failCount} assertion(s) failed.`);
    process.exit(1);
  } else {
    console.log("VERDICT: APPROVE - All live boundary flows, stress assertions, and schema checks passed.");
    process.exit(0);
  }
}

run().catch((err) => {
  console.error("FATAL RUNNER EXCEPTION:", err);
  process.exit(1);
});
