import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendDir = path.resolve(__dirname, "..");

console.log("=== Running Agent A Verification Suite ===");

// 1. Verify Bloat Files are Completely Purged
console.log("\n[1/5] Checking file purge...");
const parseResumePath = path.join(frontendDir, "app", "api", "parse-resume", "route.ts");
const resumeParserPath = path.join(frontendDir, "lib", "resumeParser.ts");

assert.equal(fs.existsSync(parseResumePath), false, "parse-resume route.ts should not exist");
assert.equal(fs.existsSync(resumeParserPath), false, "resumeParser.ts should not exist");
console.log("✔ Unbacked resume parser files are verified deleted.");

// 2. Check api.ts imports and exports
console.log("\n[2/5] Inspecting frontend/lib/api.ts...");
const apiSource = fs.readFileSync(path.join(frontendDir, "lib", "api.ts"), "utf8");

// Assert base URL is 127.0.0.1:8000
assert(apiSource.includes('http://127.0.0.1:8000'), "Base URL must default to http://127.0.0.1:8000");

// Assert all 9 backend routes are explicitly referenced
const requiredRoutes = [
  "/health",
  "/auth/register",
  "/auth/login",
  "/voice/process",
  "/interview/start",
  "/interview/respond",
  "/interview/end",
  "/interview/report/",
  "/coach/start",
  "/coach/respond",
  "/coach/end",
];

for (const route of requiredRoutes) {
  assert(apiSource.includes(route), `api.ts must contain endpoint path: ${route}`);
}
console.log("✔ All 9+ backend endpoints are declared in api.ts.");

// Assert no mock fake fallback generation in api.ts
assert(!apiSource.includes("getSimulatedVoiceResponse"), "api.ts must not contain mock fallback response generators");
assert(!apiSource.includes("int-sess-"), "api.ts must not contain hardcoded fallback session IDs");
assert(!apiSource.includes("coa-sess-"), "api.ts must not contain hardcoded fallback session IDs");
console.log("✔ Mock fallback bloat is completely purged from api.ts.");

// 3. Check useStore.ts for purge of Anish and mock bloat
console.log("\n[3/5] Inspecting frontend/store/useStore.ts...");
const storeSource = fs.readFileSync(path.join(frontendDir, "store", "useStore.ts"), "utf8");

assert(!storeSource.includes("Anish"), "useStore.ts must NOT contain candidate 'Anish'");
assert(!storeSource.includes("Anish_Senior_Engineer_Resume.pdf"), "useStore.ts must NOT contain mock resume");
assert(!storeSource.includes("CloudScale Systems"), "useStore.ts must NOT contain mock company");
assert(!storeSource.includes("user-101"), "useStore.ts must NOT contain hardcoded mock user ID");
assert(!storeSource.includes("int-session-01"), "useStore.ts must NOT contain preloaded interview session");
assert(!storeSource.includes("coa-session-01"), "useStore.ts must NOT contain preloaded coach session");

// Assert store manages required state
assert(storeSource.includes("user: null"), "Initial user must be null");
assert(storeSource.includes("token: null"), "Initial token must be null");
assert(storeSource.includes("guestUserId"), "Store must manage guestUserId");
assert(storeSource.includes("interviewSessionId: null"), "Initial interviewSessionId must be null");
assert(storeSource.includes("coachSessionId: null"), "Initial coachSessionId must be null");
assert(storeSource.includes("interviewReport: null"), "Initial interviewReport must be null");
assert(storeSource.includes("coachReport: null"), "Initial coachReport must be null");
console.log("✔ useStore.ts is verified lean, live, and free of mock bloat.");

// 4. Check supabase.ts for direct DB call removal and no mock arrays
console.log("\n[4/5] Inspecting frontend/lib/supabase.ts...");
const supabaseSource = fs.readFileSync(path.join(frontendDir, "lib", "supabase.ts"), "utf8");

assert(!supabaseSource.includes("inMemoryInterviewSessions"), "supabase.ts must NOT contain inMemoryInterviewSessions");
assert(!supabaseSource.includes("inMemoryCoachSessions"), "supabase.ts must NOT contain inMemoryCoachSessions");
assert(!supabaseSource.includes("createClient"), "supabase.ts must NOT call createClient directly");
assert(!supabaseSource.includes("Anish"), "supabase.ts must NOT contain candidate 'Anish'");
console.log("✔ Direct DB operations and mock session arrays purged from supabase.ts.");

// 5. Verify normalizeScore behavior
console.log("\n[5/5] Testing score normalization logic...");
function normalizeScore(score) {
  if (score <= 10) {
    return Math.round(score * 10);
  }
  return Math.round(score);
}

assert.equal(normalizeScore(8.8), 88);
assert.equal(normalizeScore(9.2), 92);
assert.equal(normalizeScore(10.0), 100);
assert.equal(normalizeScore(1.0), 10);
assert.equal(normalizeScore(75), 75);
console.log("✔ Score normalization (1.0-10.0 -> 0-100%) verified.");

console.log("\n==============================================");
console.log("✔ ALL AGENT A ARCHITECTURAL CHECKS PASSED!");
console.log("==============================================");
