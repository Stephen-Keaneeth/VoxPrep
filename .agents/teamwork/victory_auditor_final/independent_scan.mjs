import fs from "fs";
import path from "path";

function walk(dir) {
  let results = [];
  for (const item of fs.readdirSync(dir)) {
    if (item === "node_modules" || item === ".next") continue;
    const p = path.join(dir, item);
    const s = fs.statSync(p);
    if (s.isDirectory()) {
      results = results.concat(walk(p));
    } else if (/\.(ts|tsx|js|mjs|json|css)$/.test(item)) {
      results.push(p);
    }
  }
  return results;
}

const files = walk("frontend");
const patterns = [
  { name: "Anish", regex: /\bAnish\b/i },
  { name: "AnishResume", regex: /Anish_Senior_Engineer_Resume\.pdf/i },
  { name: "SimulatedVoice", regex: /getSimulatedVoiceResponse/ },
  { name: "MockInterviewSessionId", regex: /int-sess-/ },
  { name: "MockCoachSessionId", regex: /coa-sess-/ },
  { name: "SupabaseImport", regex: /from ['"]@supabase\/supabase-js['"]/ },
  { name: "HardcodedScore86", regex: /avgInterviewScore\s*=\s*86/ },
  { name: "HardcodedKafkaPrompt", regex: /architecting event-driven systems using Kafka/i },
];

const matches = [];
for (const file of files) {
  const content = fs.readFileSync(file, "utf8");
  for (const p of patterns) {
    if (p.regex.test(content)) {
      matches.push({
        file: file.replace(/\\/g, "/"),
        pattern: p.name,
        isTest: file.includes("tests"),
      });
    }
  }
}

console.log("Total scanned files:", files.length);
console.log("Total matches:", matches.length);
console.log("Matches in application code:", matches.filter((m) => !m.isTest));
console.log("Matches in test code (assertions of non-existence):", matches.filter((m) => m.isTest));
