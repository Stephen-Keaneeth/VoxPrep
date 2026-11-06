import fs from 'fs';
import path from 'path';

const projectRoot = 'c:\\Project\\VoxPrep';
const frontendDir = path.join(projectRoot, 'frontend');

const patterns = [
  { name: 'Fake candidate Anish', regex: /\bAnish\b/i },
  { name: 'Fake resume PDF', regex: /Anish_Senior_Engineer_Resume\.pdf/i },
  { name: 'Kafka question', regex: /architecting event-driven systems using Kafka/i },
  { name: 'Simulated voice response', regex: /getSimulatedVoiceResponse/i },
  { name: 'Fake session prefix', regex: /(int-sess-|coa-sess-)/i },
  { name: 'Direct supabase auth/rest call in frontend', regex: /from ['"]@supabase\/supabase-js['"]/i },
  { name: 'Hardcoded evaluation score constants', regex: /avgInterviewScore\s*=\s*86/i },
];

const matches = [];

function scanDir(dir) {
  const files = fs.readdirSync(dir);
  for (const file of files) {
    if (file === 'node_modules' || file === '.next' || file === '.git') continue;
    const fullPath = path.join(dir, file);
    const stat = fs.statSync(fullPath);
    if (stat.isDirectory()) {
      scanDir(fullPath);
    } else {
      // only check text files (ts, tsx, js, mjs, json, css, html, md)
      const ext = path.extname(file);
      if (['.ts', '.tsx', '.js', '.mjs', '.json', '.css', '.html', '.md'].includes(ext)) {
        const content = fs.readFileSync(fullPath, 'utf8');
        for (const p of patterns) {
          if (p.regex.test(content)) {
            // Check if match is in a test assertion asserting absence
            const lines = content.split('\n');
            lines.forEach((line, idx) => {
              if (p.regex.test(line)) {
                matches.push({
                  file: path.relative(projectRoot, fullPath),
                  lineNum: idx + 1,
                  pattern: p.name,
                  line: line.trim()
                });
              }
            });
          }
        }
      }
    }
  }
}

scanDir(frontendDir);

console.log(`Scan completed across frontend. Total hits: ${matches.length}`);
for (const m of matches) {
  console.log(`[${m.pattern}] ${m.file}:${m.lineNum} -> ${m.line}`);
}
