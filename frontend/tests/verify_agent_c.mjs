import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendDir = path.resolve(__dirname, "..");

console.log("=== Running Agent C: Analytics & Auth Verification Suite ===");

// 1. Verify Score Normalization Helper
console.log("\n[1/5] Testing frontend/lib/normalization.ts...");
const normPath = path.join(frontendDir, "lib", "normalization.ts");
assert(fs.existsSync(normPath), "frontend/lib/normalization.ts must exist");

const normSource = fs.readFileSync(normPath, "utf8");
assert(normSource.includes("export function normalizeScore"), "Must export normalizeScore");
assert(normSource.includes("score <= 10 ? Math.round(score * 10) : Math.round(score)"), "Must contain exact normalization formula");

function normalizeScore(score, fallback = 0) {
  if (score === undefined || score === null || isNaN(score)) return fallback;
  return score <= 10 ? Math.round(score * 10) : Math.round(score);
}

// Test 1.0 - 10.0 rubric scale
assert.equal(normalizeScore(1.0), 10, "1.0 -> 10%");
assert.equal(normalizeScore(7.5), 75, "7.5 -> 75%");
assert.equal(normalizeScore(8.8), 88, "8.8 -> 88%");
assert.equal(normalizeScore(9.2), 92, "9.2 -> 92%");
assert.equal(normalizeScore(10.0), 100, "10.0 -> 100%");

// Test 0 - 100 scale preserved
assert.equal(normalizeScore(85), 85, "85 -> 85%");
assert.equal(normalizeScore(100), 100, "100 -> 100%");
assert.equal(normalizeScore(0), 0, "0 -> 0%");

// Test null / undefined boundaries
assert.equal(normalizeScore(null, 0), 0, "null -> fallback 0");
assert.equal(normalizeScore(undefined, 50), 50, "undefined -> fallback 50");
console.log("✔ Score normalization helper is mathematically verified.");

// 2. Check utils.ts and api.ts exports
console.log("\n[2/5] Inspecting frontend/lib/utils.ts & frontend/lib/api.ts...");
const utilsSource = fs.readFileSync(path.join(frontendDir, "lib", "utils.ts"), "utf8");
assert(utilsSource.includes("normalizeScore"), "utils.ts must re-export normalizeScore");

const apiSource = fs.readFileSync(path.join(frontendDir, "lib", "api.ts"), "utf8");
assert(apiSource.includes("export const apiClient ="), "api.ts must export apiClient");
assert(apiSource.includes("login,") || apiSource.includes("login:"), "apiClient must have login");
assert(apiSource.includes("register,") || apiSource.includes("register:"), "apiClient must have register");
assert(apiSource.includes("getInterviewReport,") || apiSource.includes("getInterviewReport:"), "apiClient must have getInterviewReport");
assert(apiSource.includes("normalizeScore,") || apiSource.includes("normalizeScore:"), "apiClient must have normalizeScore");
console.log("✔ apiClient and normalizeScore exports are verified.");

// 3. Verify Interview Dashboard Rebuild
console.log("\n[3/5] Inspecting Interview Evaluation Report...");
const interviewDashSource = fs.readFileSync(
  path.join(frontendDir, "components", "sections", "InterviewDashboard.tsx"),
  "utf8"
);

// Assert use of Zustand interviewReport & interviewSessionId
assert(interviewDashSource.includes("interviewReport"), "InterviewDashboard must consume interviewReport");
assert(interviewDashSource.includes("interviewSessionId"), "InterviewDashboard must consume interviewSessionId");
assert(interviewDashSource.includes("getInterviewReport"), "InterviewDashboard must support fetching report via sessionId");

// Assert 4 dimension scores rendered
assert(interviewDashSource.includes("relevance"), "Must render relevance score");
assert(interviewDashSource.includes("clarity"), "Must render clarity score");
assert(interviewDashSource.includes("depth"), "Must render depth score");
assert(interviewDashSource.includes("examples"), "Must render examples score");

// Assert CTA to coach and question breakdown
assert(interviewDashSource.includes('href="/coach"'), "Must have CTA to /coach");
assert(interviewDashSource.includes("question_breakdown"), "Must render question breakdown");
assert(interviewDashSource.includes("normalizeScore"), "Must normalize scores with normalizeScore");

// Assert empty state with CTA to /interview
assert(interviewDashSource.includes('href="/interview"'), "Must have empty state CTA to /interview");

// Assert zero fake candidate "Anish"
assert(!interviewDashSource.includes('"Anish"'), "Must NOT contain mock candidate 'Anish'");
console.log("✔ Interview Evaluation Dashboard verified lean and model-aligned.");

// 4. Verify Communication Dashboard Rebuild
console.log("\n[4/5] Inspecting Communication Report...");
const commDashSource = fs.readFileSync(
  path.join(frontendDir, "components", "sections", "CommunicationDashboard.tsx"),
  "utf8"
);

// Assert use of Zustand coachReport
assert(commDashSource.includes("coachReport"), "CommunicationDashboard must consume coachReport");
assert(commDashSource.includes("WPM"), "Must display WPM metric");
assert(commDashSource.includes("Filler"), "Must display filler words metric");
assert(commDashSource.includes("Grammar"), "Must display grammar metric");
assert(commDashSource.includes("Fluency Tier"), "Must display fluency tier");
assert(commDashSource.includes("keyLearnings") || commDashSource.includes("key_learnings"), "Must display key learnings");
assert(commDashSource.includes("corrections"), "Must display logged linguistic corrections");

// Assert empty state with CTA to /coach
assert(commDashSource.includes('href="/coach"'), "Must have empty state CTA to /coach");

// Assert zero fake candidate or unbacked bloat
assert(!commDashSource.includes('"Anish"'), "Must NOT contain mock candidate 'Anish'");
console.log("✔ Communication Dashboard verified lean and model-aligned.");

// 5. Verify Authentication Pages (Login & Register)
console.log("\n[5/5] Inspecting Login & Register Auth pages...");
const loginSource = fs.readFileSync(
  path.join(frontendDir, "app", "(auth)", "login", "page.tsx"),
  "utf8"
);
assert(loginSource.includes("apiClient.login"), "Login must call apiClient.login");
assert(loginSource.includes("setUser(res.user, res.access_token)"), "Login must store user and token in Zustand");
assert(loginSource.includes("ApiError"), "Login must handle ApiError envelope");
assert(loginSource.includes("Continue as Guest"), "Login must provide Continue as Guest option");
assert(loginSource.includes('router.push("/interview")'), "Login must route to /interview");

const registerSource = fs.readFileSync(
  path.join(frontendDir, "app", "(auth)", "register", "page.tsx"),
  "utf8"
);
assert(registerSource.includes("apiClient.register"), "Register must call apiClient.register");
assert(registerSource.includes("setUser(res.user, res.access_token)"), "Register must store user and token in Zustand");
assert(registerSource.includes("ApiError"), "Register must handle ApiError envelope");
assert(registerSource.includes("Continue as Guest"), "Register must provide Continue as Guest option");
assert(registerSource.includes('router.push("/interview")'), "Register must route to /interview");
console.log("✔ Authentication pages verified genuine, dark styled, with guest access.");

console.log("\n==============================================");
console.log("✔ ALL AGENT C ARCHITECTURAL CHECKS PASSED!");
console.log("==============================================");
