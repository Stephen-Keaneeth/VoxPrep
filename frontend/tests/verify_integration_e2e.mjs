import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendDir = path.resolve(__dirname, "..");
const repoDir = path.resolve(frontendDir, "..");
const backendDir = path.resolve(repoDir, "backend");

const BASE_URL = process.env.API_URL || "http://127.0.0.1:8000";

console.log("=============================================================");
console.log("=== VoxPrep End-to-End Integration Verification Suite ===");
console.log(`=== Target Backend: ${BASE_URL} ===`);
console.log("=============================================================\n");

// Helper: 16kHz mono 16-bit PCM WAV generator
function createDummyWav(durationMs = 250, sampleRate = 16000) {
  const numSamples = Math.floor(sampleRate * (durationMs / 1000));
  const dataSize = numSamples * 2;
  const buffer = Buffer.alloc(44 + dataSize);

  // RIFF header
  buffer.write("RIFF", 0);
  buffer.writeUInt32LE(36 + dataSize, 4);
  buffer.write("WAVE", 8);

  // fmt chunk
  buffer.write("fmt ", 12);
  buffer.writeUInt32LE(16, 16);
  buffer.writeUInt16LE(1, 20); // PCM
  buffer.writeUInt16LE(1, 22); // Mono
  buffer.writeUInt32LE(sampleRate, 24);
  buffer.writeUInt32LE(sampleRate * 2, 28);
  buffer.writeUInt16LE(2, 32);
  buffer.writeUInt16LE(16, 34);

  // data chunk
  buffer.write("data", 36);
  buffer.writeUInt32LE(dataSize, 40);
  // Zero samples fill remaining bytes

  return buffer;
}

// Helper: Score normalizer
function normalizeScore(score, fallback = 0) {
  if (score === undefined || score === null || isNaN(score)) return fallback;
  return score <= 10 ? Math.round(score * 10) : Math.round(score);
}

// Helper: Ensure backend is running
let spawnedProcess = null;
async function ensureBackendRunning() {
  try {
    const res = await fetch(`${BASE_URL}/health`, { signal: AbortSignal.timeout(2000) });
    if (res.ok) {
      console.log("✔ Backend is already running on " + BASE_URL);
      return;
    }
  } catch {
    // Need to spawn
  }

  console.log("Backend not detected on " + BASE_URL + ". Spawning uvicorn process...");
  const uvicornBin = process.platform === "win32"
    ? path.join(backendDir, ".venv", "Scripts", "uvicorn.exe")
    : path.join(backendDir, ".venv", "bin", "uvicorn");

  spawnedProcess = spawn(
    uvicornBin,
    ["app.main:app", "--host", "127.0.0.1", "--port", "8000"],
    {
      cwd: backendDir,
      stdio: "ignore",
      detached: false,
    }
  );

  // Poll until healthy
  let attempts = 0;
  while (attempts < 20) {
    await new Promise((r) => setTimeout(r, 500));
    attempts++;
    try {
      const res = await fetch(`${BASE_URL}/health`, { signal: AbortSignal.timeout(1000) });
      if (res.ok) {
        console.log("✔ Spawning complete. Backend is ready.\n");
        return;
      }
    } catch {
      // Keep waiting
    }
  }
  throw new Error("Failed to start or connect to backend at " + BASE_URL);
}

async function runSuite() {
  try {
    await ensureBackendRunning();

    // -------------------------------------------------------------------------
    // 1. GET /health
    // -------------------------------------------------------------------------
    console.log("[1/11] Testing GET /health...");
    const healthRes = await fetch(`${BASE_URL}/health`);
    assert.equal(healthRes.status, 200, "Health check must return 200");
    const healthJson = await healthRes.json();
    assert.equal(healthJson.status, "ok", 'Health status must be "ok"');
    console.log("✔ Health probe passed:", JSON.stringify(healthJson));

    // -------------------------------------------------------------------------
    // 2. POST /auth/register
    // -------------------------------------------------------------------------
    console.log("\n[2/11] Testing POST /auth/register...");
    const testEmail = `integration_tester_${Date.now()}_${Math.floor(Math.random() * 1000)}@voxprep.internal`;
    const testPassword = "SecurePassword123!";
    const testName = "Morgan Dev";

    const regRes = await fetch(`${BASE_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: testEmail,
        password: testPassword,
        name: testName,
      }),
    });
    assert([200, 201].includes(regRes.status), `Register must return 200/201, got ${regRes.status}`);
    const regJson = await regRes.json();
    assert(regJson.user, "Register response must contain user object");
    assert.equal(regJson.user.email, testEmail, "Registered email must match");
    assert.equal(regJson.user.name, testName, "Registered name must match");
    assert(regJson.user.id, "Registered user must have an id");
    assert(regJson.access_token, "Register response must contain access_token");
    console.log(`✔ User registered: id=${regJson.user.id}, email=${regJson.user.email}`);

    // -------------------------------------------------------------------------
    // 3. POST /auth/login
    // -------------------------------------------------------------------------
    console.log("\n[3/11] Testing POST /auth/login...");
    const loginRes = await fetch(`${BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: testEmail,
        password: testPassword,
      }),
    });
    assert.equal(loginRes.status, 200, "Login must return 200 for valid credentials");
    const loginJson = await loginRes.json();
    assert(loginJson.user, "Login response must contain user object");
    assert.equal(loginJson.user.email, testEmail);
    assert(loginJson.access_token, "Login response must contain access_token");

    // Negative check: wrong password returns 401
    const badLoginRes = await fetch(`${BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: testEmail,
        password: "WrongPassword999!",
      }),
    });
    assert.equal(badLoginRes.status, 401, "Bad password must return HTTP 401");
    console.log("✔ Authentication credentials verified successfully.");

    // -------------------------------------------------------------------------
    // 4. POST /interview/start (supports guest or authenticated candidate)
    // -------------------------------------------------------------------------
    console.log("\n[4/11] Testing POST /interview/start...");
    const startInterviewRes = await fetch(`${BASE_URL}/interview/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        candidate_name: testName,
        role: "Principal Infrastructure Architect",
        experience_level: "Lead",
        interview_type: "technical",
        user_id: regJson.user.id,
      }),
    });
    assert.equal(startInterviewRes.status, 200, "Interview start must return 200");
    const startInterviewJson = await startInterviewRes.json();
    assert(startInterviewJson.session_id, "Interview start must return session_id");
    assert(startInterviewJson.opening_message, "Interview start must return opening_message");
    const interviewSessionId = startInterviewJson.session_id;
    console.log(`✔ Interview started: session_id=${interviewSessionId}`);
    console.log(`  Opening prompt preview: "${startInterviewJson.opening_message.slice(0, 60)}..."`);

    // Also verify guest start (user_id = null)
    const guestStartRes = await fetch(`${BASE_URL}/interview/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        candidate_name: "Guest Candidate",
        role: "Software Engineer",
        experience_level: "Mid-level",
        interview_type: "hr",
        user_id: null,
      }),
    });
    assert.equal(guestStartRes.status, 200, "Guest interview start must return 200");
    const guestStartJson = await guestStartRes.json();
    assert(guestStartJson.session_id, "Guest interview must receive session_id");
    console.log("✔ Guest candidate access verified.");

    // -------------------------------------------------------------------------
    // 5. POST /interview/respond
    // -------------------------------------------------------------------------
    console.log("\n[5/11] Testing POST /interview/respond...");
    const interviewRespondRes = await fetch(`${BASE_URL}/interview/respond`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: interviewSessionId,
        answer_text: "In my previous role, I designed multi-region failover using Apache Kafka and Envoy service meshes, maintaining 99.999% SLA during zero-downtime database migrations.",
      }),
    });
    assert.equal(interviewRespondRes.status, 200, "Interview respond must return 200");
    const respondJson = await interviewRespondRes.json();
    assert(respondJson.spoken_response, "Interview respond must return spoken_response");
    assert(typeof respondJson.is_complete === "boolean", "is_complete must be boolean");
    assert(respondJson.follow_up_or_next, "follow_up_or_next must be present");
    console.log("✔ Interview response handled. Next prompt preview:", `"${respondJson.spoken_response.slice(0, 60)}..."`);

    // -------------------------------------------------------------------------
    // 6. POST /interview/end
    // -------------------------------------------------------------------------
    console.log("\n[6/11] Testing POST /interview/end...");
    const endInterviewRes = await fetch(`${BASE_URL}/interview/end`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: interviewSessionId }),
    });
    assert.equal(endInterviewRes.status, 200, "Interview end must return 200");
    const endInterviewJson = await endInterviewRes.json();
    assert.equal(endInterviewJson.session_id, interviewSessionId);
    assert.equal(endInterviewJson.status, "completed");
    assert(endInterviewJson.report, "Must return InterviewReport object");

    const report = endInterviewJson.report;
    assert(typeof report.overall_score === "number", "overall_score must be number");
    assert(report.dimension_scores, "Must include dimension_scores");
    assert(typeof report.dimension_scores.relevance === "number", "relevance must be number");
    assert(typeof report.dimension_scores.clarity === "number", "clarity must be number");
    assert(typeof report.dimension_scores.depth === "number", "depth must be number");
    assert(typeof report.dimension_scores.examples === "number", "examples must be number");
    assert(Array.isArray(report.question_breakdown), "question_breakdown must be array");
    assert(Array.isArray(report.strengths), "strengths must be array");
    assert(Array.isArray(report.action_items), "action_items must be array");
    assert(report.coach_recommendation, "coach_recommendation must be present");
    assert(report.summary, "summary must be present");
    console.log(`✔ Interview ended. Report overall_score=${report.overall_score} (Normalized: ${normalizeScore(report.overall_score)}%)`);

    // -------------------------------------------------------------------------
    // 7. GET /interview/report/{session_id}
    // -------------------------------------------------------------------------
    console.log("\n[7/11] Testing GET /interview/report/{session_id}...");
    const getReportRes = await fetch(`${BASE_URL}/interview/report/${interviewSessionId}`);
    assert.equal(getReportRes.status, 200, "GET report must return 200");
    const retrievedReport = await getReportRes.json();
    assert.equal(retrievedReport.overall_score, report.overall_score, "Retrieved score must match generated report");
    assert.equal(retrievedReport.summary, report.summary, "Retrieved summary must match");
    console.log("✔ GET /interview/report/{session_id} verified.");

    // -------------------------------------------------------------------------
    // 8. POST /coach/start (across modes: conversation, answer_training, english_improvement)
    // -------------------------------------------------------------------------
    console.log("\n[8/11] Testing POST /coach/start across all 3 modes...");
    const modes = ["conversation", "answer_training", "english_improvement"];
    let coachSessionId = null;

    for (const mode of modes) {
      const coachStartRes = await fetch(`${BASE_URL}/coach/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: regJson.user.id,
          mode: mode,
        }),
      });
      assert.equal(coachStartRes.status, 200, `Coach start for mode ${mode} must return 200`);
      const coachStartJson = await coachStartRes.json();
      assert(coachStartJson.session_id, "Coach start must return session_id");
      assert(coachStartJson.opening_message, "Coach start must return opening_message");
      assert.equal(coachStartJson.mode, mode, "Returned mode must match requested mode");
      console.log(`✔ Coach mode "${mode}" started successfully: session_id=${coachStartJson.session_id}`);
      coachSessionId = coachStartJson.session_id;
    }

    // -------------------------------------------------------------------------
    // 9. POST /coach/respond
    // -------------------------------------------------------------------------
    console.log("\n[9/11] Testing POST /coach/respond...");
    const coachRespondRes = await fetch(`${BASE_URL}/coach/respond`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: coachSessionId,
        user_text: "Me and my colleague was discussing how to optimize our SQL queries yesterday.",
      }),
    });
    assert.equal(coachRespondRes.status, 200, "Coach respond must return 200");
    const coachRespondJson = await coachRespondRes.json();
    assert(coachRespondJson.coach_message, "Coach respond must return coach_message");
    assert(coachRespondJson.next_prompt, "Coach respond must return next_prompt");
    // correction is either CoachCorrection or null
    if (coachRespondJson.correction) {
      assert(coachRespondJson.correction.original, "Correction must have original");
      assert(coachRespondJson.correction.improved, "Correction must have improved");
      assert(coachRespondJson.correction.reason, "Correction must have reason");
      console.log(`  Linguistic refinement: "${coachRespondJson.correction.original}" -> "${coachRespondJson.correction.improved}"`);
    }
    console.log("✔ Coach response processed successfully.");

    // -------------------------------------------------------------------------
    // 10. POST /coach/end
    // -------------------------------------------------------------------------
    console.log("\n[10/11] Testing POST /coach/end...");
    const coachEndRes = await fetch(`${BASE_URL}/coach/end`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: coachSessionId }),
    });
    assert.equal(coachEndRes.status, 200, "Coach end must return 200");
    const coachEndJson = await coachEndRes.json();
    assert.equal(coachEndJson.session_id, coachSessionId);
    assert.equal(coachEndJson.status, "completed");
    assert(coachEndJson.summary, "Coach end must return summary");
    assert(coachEndJson.profile_updated, "Coach end must return profile_updated");
    console.log("✔ Coach session concluded successfully.");

    // -------------------------------------------------------------------------
    // 11. POST /voice/process & Score Normalization
    // -------------------------------------------------------------------------
    console.log("\n[11/11] Testing POST /voice/process & score normalization...");
    const wavBytes = createDummyWav(300, 16000);
    const formData = new FormData();
    formData.append("file", new Blob([wavBytes], { type: "audio/wav" }), "test_recording.wav");
    formData.append("agent_type", "interview");
    formData.append("session_id", interviewSessionId);

    const voiceRes = await fetch(`${BASE_URL}/voice/process`, {
      method: "POST",
      body: formData,
    });
    assert.equal(voiceRes.status, 200, "Voice process must return 200");
    const voiceJson = await voiceRes.json();
    assert("transcript" in voiceJson, "Voice process must return transcript");
    assert("spoken_response" in voiceJson, "Voice process must return spoken_response");
    assert(voiceJson.spoken_response.length > 0, "Spoken response must be non-empty");
    console.log(`✔ Voice upload processed: spoken_response="${voiceJson.spoken_response.slice(0, 50)}..."`);

    // Verify Score Normalization
    console.log("\nVerifying score normalization boundary mathematics...");
    assert.equal(normalizeScore(1.0), 10);
    assert.equal(normalizeScore(6.1), 61);
    assert.equal(normalizeScore(7.5), 75);
    assert.equal(normalizeScore(8.8), 88);
    assert.equal(normalizeScore(9.2), 92);
    assert.equal(normalizeScore(10.0), 100);
    assert.equal(normalizeScore(85), 85);
    assert.equal(normalizeScore(100), 100);
    assert.equal(normalizeScore(null, 0), 0);
    assert.equal(normalizeScore(undefined, 70), 70);
    console.log("✔ Normalization logic verified on 1.0-10.0 rubric and 0-100 scales.");

    // -------------------------------------------------------------------------
    // Summary
    // -------------------------------------------------------------------------
    console.log("\n=============================================================");
    console.log("✔ ALL END-TO-END INTEGRATION TESTS PASSED CLEANLY (11/11)");
    console.log("=============================================================");
  } finally {
    if (spawnedProcess) {
      console.log("Cleaning up spawned uvicorn process...");
      try {
        spawnedProcess.kill();
      } catch {
        // ignore
      }
    }
  }
}

runSuite().catch((err) => {
  console.error("\n❌ E2E INTEGRATION TEST SUITE FAILED:");
  console.error(err);
  process.exit(1);
});
