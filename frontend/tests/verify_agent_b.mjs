import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendDir = path.resolve(__dirname, "..");

console.log("=== Running Agent B Verification Suite ===");

// -----------------------------------------------------------------------------
// 1. Inspect Interview Agent & Lobby Components
// -----------------------------------------------------------------------------
console.log("\n[1/5] Inspecting Interview Agent (frontend/components/sections/InterviewAgent.tsx)...");
const interviewAgentPath = path.join(frontendDir, "components", "sections", "InterviewAgent.tsx");
assert(fs.existsSync(interviewAgentPath), "InterviewAgent.tsx must exist");
const interviewAgentSrc = fs.readFileSync(interviewAgentPath, "utf8");

// WebRTC video self-preview assertions
assert(interviewAgentSrc.includes("autoPlay"), "Candidate video must have autoPlay attribute");
assert(interviewAgentSrc.includes("playsInline"), "Candidate video must have playsInline attribute");
assert(interviewAgentSrc.includes("muted"), "Candidate video must have muted attribute to prevent audio loop");
assert(interviewAgentSrc.includes("track.stop()"), "Must stop media stream tracks on unmount/cleanup");

// API and Store lifecycle assertions
assert(interviewAgentSrc.includes("startInterviewSession"), "Must call startInterviewSession");
assert(interviewAgentSrc.includes("setInterviewSessionId"), "Must update interviewSessionId in Zustand store");
assert(interviewAgentSrc.includes("sendVoiceAudio"), "Must send audio blob to /voice/process");
assert(interviewAgentSrc.includes("submitInterviewAnswer"), "Must submit answer to /interview/respond");
assert(interviewAgentSrc.includes("endInterviewSession"), "Must end session via /interview/end");
assert(interviewAgentSrc.includes("setInterviewReport"), "Must store report via setInterviewReport in Zustand store");
assert(interviewAgentSrc.includes("router.push(\"/analytics/interview\")"), "Must redirect directly to /analytics/interview on end");

// Text fallback & turn-taking
assert(interviewAgentSrc.includes("Direct Text Answer Fallback") || interviewAgentSrc.includes("Type Answer"), "Must support direct text answer fallback");
assert(interviewAgentSrc.includes("speakInterviewer") || interviewAgentSrc.includes("speakText"), "Must support spoken interviewer audio playback");

// No fake/mock bloat
assert(!interviewAgentSrc.includes("ResumeUploadModal"), "Must not import or render ResumeUploadModal");
assert(!interviewAgentSrc.includes("Kafka"), "Must not contain hardcoded fake Kafka questions");
assert(!interviewAgentSrc.includes("thundering herd"), "Must not contain hardcoded fake cache questions");
assert(!interviewAgentSrc.includes("Anish"), "Must not contain hardcoded candidate 'Anish'");
console.log("✔ InterviewAgent.tsx satisfies all WebRTC, API, store, and anti-bloat requirements.");

// -----------------------------------------------------------------------------
// 2. Inspect Interview Lobby Component
// -----------------------------------------------------------------------------
console.log("\n[2/5] Inspecting Interview Lobby (frontend/components/interview/InterviewLobby.tsx)...");
const lobbyPath = path.join(frontendDir, "components", "interview", "InterviewLobby.tsx");
assert(fs.existsSync(lobbyPath), "InterviewLobby.tsx must exist");
const lobbySrc = fs.readFileSync(lobbyPath, "utf8");

assert(lobbySrc.includes("candidate_name"), "Lobby must configure candidate_name");
assert(lobbySrc.includes("role"), "Lobby must configure target role");
assert(lobbySrc.includes("experience_level"), "Lobby must configure experience_level");
assert(lobbySrc.includes("interview_type"), "Lobby must configure interview_type");
assert(lobbySrc.includes("technical"), "Lobby must support technical track");
assert(lobbySrc.includes("hr"), "Lobby must support HR track");
assert(lobbySrc.includes("autoPlay") && lobbySrc.includes("muted"), "Lobby preview video must be autoPlay and muted");
console.log("✔ InterviewLobby.tsx satisfies all parameter configuration & preview requirements.");

// -----------------------------------------------------------------------------
// 3. Inspect Communication Coach Component
// -----------------------------------------------------------------------------
console.log("\n[3/5] Inspecting Communication Coach (frontend/components/sections/CommunicationAgent.tsx)...");
const coachAgentPath = path.join(frontendDir, "components", "sections", "CommunicationAgent.tsx");
assert(fs.existsSync(coachAgentPath), "CommunicationAgent.tsx must exist");
const coachAgentSrc = fs.readFileSync(coachAgentPath, "utf8");

// Exact 3 backend modes
assert(coachAgentSrc.includes('"conversation"'), 'Coach must support mode "conversation"');
assert(coachAgentSrc.includes('"answer_training"'), 'Coach must support mode "answer_training"');
assert(coachAgentSrc.includes('"english_improvement"'), 'Coach must support mode "english_improvement"');

// Session endpoints & Store integration
assert(coachAgentSrc.includes("startCoachSession"), "Must call startCoachSession");
assert(coachAgentSrc.includes("setCoachSessionId"), "Must update coachSessionId in Zustand store");
assert(coachAgentSrc.includes("submitCoachResponse"), "Must call submitCoachResponse (/coach/respond)");
assert(coachAgentSrc.includes("endCoachSession"), "Must call endCoachSession (/coach/end)");
assert(coachAgentSrc.includes("setCoachReport"), "Must store report via setCoachReport in Zustand store");
assert(coachAgentSrc.includes("router.push(\"/analytics/communication\")"), "Must redirect directly to /analytics/communication on finish");

// Real-time refinement & live metrics
assert(coachAgentSrc.includes("activeCorrection.original"), "Must render original phrase for correction");
assert(coachAgentSrc.includes("activeCorrection.improved"), "Must render improved alternative for correction");
assert(coachAgentSrc.includes("activeCorrection.reason"), "Must render explanation reason for correction");
assert(coachAgentSrc.includes("calculatedWpm"), "Must track live/authoritative WPM");
assert(coachAgentSrc.includes("detectedFillers"), "Must detect filler words");
assert(coachAgentSrc.includes("Type Practice Response") || coachAgentSrc.includes("Type Response"), "Must support direct text input fallback");
console.log("✔ CommunicationAgent.tsx satisfies all 3 modes, refinement cards, metrics, and API contracts.");

// -----------------------------------------------------------------------------
// 4. Inspect Pages Routing
// -----------------------------------------------------------------------------
console.log("\n[4/5] Checking Next.js route wrappers...");
const interviewPage = fs.readFileSync(path.join(frontendDir, "app", "interview", "page.tsx"), "utf8");
assert(interviewPage.includes("<InterviewAgent"), "app/interview/page.tsx must render InterviewAgent");

const coachPage = fs.readFileSync(path.join(frontendDir, "app", "coach", "page.tsx"), "utf8");
assert(coachPage.includes("<CommunicationAgent"), "app/coach/page.tsx must render CommunicationAgent");
console.log("✔ Route wrappers for /interview and /coach verified.");

// -----------------------------------------------------------------------------
// 5. Verify Store Actions Integrity
// -----------------------------------------------------------------------------
console.log("\n[5/5] Verifying Zustand useStore methods...");
const storeSrc = fs.readFileSync(path.join(frontendDir, "store", "useStore.ts"), "utf8");
assert(storeSrc.includes("setInterviewSessionId:"), "useStore must declare setInterviewSessionId");
assert(storeSrc.includes("setCoachSessionId:"), "useStore must declare setCoachSessionId");
assert(storeSrc.includes("setInterviewReport:"), "useStore must declare setInterviewReport");
assert(storeSrc.includes("setCoachReport:"), "useStore must declare setCoachReport");
console.log("✔ Zustand store action signatures verified.");

console.log("\n==============================================");
console.log("✔ ALL AGENT B INTERACTION ROOM CHECKS PASSED!");
console.log("==============================================");
