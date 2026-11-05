/**
 * VOXPREP Deep Resume Parsing & Dynamic Question Generation Engine
 * Uses server-side pdf-parse for real PDF extraction + client fallback.
 */

export interface ParsedResumeAnalysis {
  candidateName: string;
  targetRole: string;
  experienceLevel: "Entry-Level" | "Mid-Level" | "Senior" | "Lead / Staff";
  skills: string[];
  recentCompany: string;
  summary: string;
  customQuestions: string[];
  extractedRawText?: string;
  projectHighlights?: string[];
}

const EXTENSIVE_SKILL_TAXONOMY: { category: string; skills: string[] }[] = [
  {
    category: "Languages",
    skills: [
      "JavaScript", "TypeScript", "Python", "Java", "C++", "C#", "C", "Go", "Golang", "Rust",
      "PHP", "Ruby", "Swift", "Kotlin", "Dart", "Scala", "R", "SQL", "HTML5", "CSS3", "Bash", "Shell",
    ],
  },
  {
    category: "Frontend",
    skills: [
      "React", "Next.js", "Vue", "Nuxt", "Angular", "Svelte", "Redux", "Tailwind CSS", "Bootstrap",
      "Material-UI", "Webpack", "Vite", "GraphQL", "REST APIs", "WebSockets", "Responsive Design",
    ],
  },
  {
    category: "Backend & Systems",
    skills: [
      "Node.js", "Express", "NestJS", "FastAPI", "Django", "Flask", "Spring Boot", "Spring",
      "ASP.NET", ".NET Core", "Ruby on Rails", "Laravel", "Microservices", "gRPC", "Serverless",
    ],
  },
  {
    category: "Databases & Storage",
    skills: [
      "PostgreSQL", "MySQL", "MongoDB", "Redis", "SQLite", "DynamoDB", "Cassandra", "Elasticsearch",
      "Supabase", "Firebase", "Prisma", "TypeORM", "SQLAlchemy", "Oracle",
    ],
  },
  {
    category: "Cloud, DevOps & Containers",
    skills: [
      "AWS", "Amazon Web Services", "Azure", "GCP", "Google Cloud", "Docker", "Kubernetes",
      "Terraform", "Ansible", "CI/CD", "GitHub Actions", "GitLab CI", "Linux", "Nginx",
    ],
  },
  {
    category: "Messaging & Streaming",
    skills: [
      "Kafka", "RabbitMQ", "Apache Kafka", "Celery", "SQS", "Pub/Sub", "Event-Driven",
    ],
  },
  {
    category: "AI, ML & Data",
    skills: [
      "PyTorch", "TensorFlow", "Scikit-Learn", "Pandas", "NumPy", "OpenCV", "NLP",
      "LLM", "LangChain", "OpenAI", "Spark", "Airflow", "Data Modeling",
    ],
  },
  {
    category: "Testing & Quality",
    skills: [
      "Jest", "Cypress", "Playwright", "JUnit", "PyTest", "Mocha", "Selenium", "TDD",
    ],
  },
];

const TARGET_ROLE_RULES: { role: string; triggers: string[] }[] = [
  {
    role: "Frontend Engineer",
    triggers: ["frontend", "front-end", "ui developer", "react developer", "vue developer", "angular developer", "web developer", "ui/ux engineer"],
  },
  {
    role: "Full-Stack Software Engineer",
    triggers: ["full stack", "fullstack", "full-stack", "mern", "mean stack", "web application developer"],
  },
  {
    role: "DevOps & Cloud Infrastructure Engineer",
    triggers: ["devops", "sre", "site reliability", "cloud engineer", "infrastructure engineer", "kubernetes administrator"],
  },
  {
    role: "Machine Learning / Data Scientist",
    triggers: ["machine learning", "data scientist", "deep learning", "ai engineer", "data engineer", "nlp engineer", "computer vision"],
  },
  {
    role: "Mobile Application Developer",
    triggers: ["ios developer", "android developer", "flutter", "react native", "mobile engineer", "swift developer"],
  },
  {
    role: "Backend & Systems Architect",
    triggers: ["backend", "back-end", "distributed systems", "microservices", "api engineer", "systems engineer"],
  },
  {
    role: "Software Development Engineer",
    triggers: ["software engineer", "software developer", "sde", "programmer", "application developer"],
  },
];

/**
 * Extracts plain text from an uploaded resume file using the Next.js /api/parse-resume endpoint.
 */
export async function extractTextFromFile(file: File): Promise<string> {
  const extension = file.name.split(".").pop()?.toLowerCase() || "";

  // Direct text reading for text, markdown, json, csv
  if (["txt", "md", "json", "csv"].includes(extension)) {
    try {
      const text = await file.text();
      if (text.trim().length > 10) return text.trim();
    } catch {
      // Continue to API
    }
  }

  // Send to server-side parser for deep PDF / DOCX text extraction
  try {
    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch("/api/parse-resume", {
      method: "POST",
      body: formData,
    });

    if (res.ok) {
      const data = await res.json();
      if (data.text && data.text.trim().length > 20) {
        return data.text.trim();
      }
    }
  } catch (err) {
    console.warn("Server-side PDF parse API call error:", err);
  }

  // Fallback to client-side direct text
  try {
    const fallbackText = await file.text();
    if (fallbackText.trim().length > 20) return fallbackText.trim();
  } catch {
    // Return empty
  }

  return "";
}

/**
 * Analyzes resume content and extracts candidate identity, actual skills, project highlights,
 * and dynamically synthesizes 5 hyper-tailored, realistic interview questions.
 */
export function analyzeResumeText(rawText: string, fileName: string = "Resume.pdf"): ParsedResumeAnalysis {
  const clean = rawText.replace(/\r\n/g, "\n").trim();
  const lower = clean.toLowerCase();
  const lines = clean.split("\n").map((l) => l.trim()).filter((l) => l.length > 0);

  // 1. Detect Candidate Name from top lines
  let candidateName = "Candidate";
  for (let i = 0; i < Math.min(lines.length, 5); i++) {
    const line = lines[i];
    // Exclude header words, URLs, emails, phone numbers
    if (
      line.length >= 3 &&
      line.length <= 35 &&
      !line.includes("@") &&
      !line.includes("http") &&
      !line.includes("www") &&
      !line.toLowerCase().includes("resume") &&
      !line.toLowerCase().includes("curriculum") &&
      !/[0-9]/.test(line) &&
      /^[A-Za-z\s.'-]+$/.test(line)
    ) {
      candidateName = line;
      break;
    }
  }

  // 2. Detect Skills across all 8 taxonomy categories
  const detectedSkills: string[] = [];
  for (const group of EXTENSIVE_SKILL_TAXONOMY) {
    for (const skill of group.skills) {
      const escaped = skill.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const regex = new RegExp(`(?:^|[\\s,;()|/])${escaped}(?:[\\s,;()|/.]|$)`, "i");
      if (regex.test(clean)) {
        if (!detectedSkills.includes(skill)) {
          detectedSkills.push(skill);
        }
      }
    }
  }

  // 3. Detect Target Role from text triggers
  let targetRole = "Software Development Engineer";
  for (const rule of TARGET_ROLE_RULES) {
    const matched = rule.triggers.some((trigger) => lower.includes(trigger));
    if (matched) {
      targetRole = rule.role;
      break;
    }
  }

  // If specific strong skills detected, refine target role
  if (targetRole === "Software Development Engineer") {
    if (detectedSkills.includes("React") || detectedSkills.includes("Vue") || detectedSkills.includes("Next.js") || detectedSkills.includes("Angular")) {
      if (detectedSkills.includes("Node.js") || detectedSkills.includes("Python") || detectedSkills.includes("PostgreSQL") || detectedSkills.includes("MongoDB")) {
        targetRole = "Full-Stack Software Engineer";
      } else {
        targetRole = "Frontend Engineer";
      }
    } else if (detectedSkills.includes("Kubernetes") || detectedSkills.includes("Docker") || detectedSkills.includes("Terraform") || detectedSkills.includes("AWS")) {
      targetRole = "DevOps & Cloud Engineer";
    } else if (detectedSkills.includes("PyTorch") || detectedSkills.includes("TensorFlow") || detectedSkills.includes("Pandas")) {
      targetRole = "Machine Learning / AI Engineer";
    } else if (detectedSkills.includes("PostgreSQL") || detectedSkills.includes("Kafka") || detectedSkills.includes("FastAPI") || detectedSkills.includes("Spring Boot") || detectedSkills.includes("Go")) {
      targetRole = "Backend & Systems Engineer";
    }
  }

  // 4. Detect Experience Level
  let experienceLevel: "Entry-Level" | "Mid-Level" | "Senior" | "Lead / Staff" = "Mid-Level";
  if (
    lower.includes("lead") ||
    lower.includes("staff") ||
    lower.includes("principal") ||
    lower.includes("architect") ||
    lower.includes("engineering manager")
  ) {
    experienceLevel = "Lead / Staff";
  } else if (
    lower.includes("senior") ||
    lower.includes("sr.") ||
    lower.includes("5+ years") ||
    lower.includes("6+ years") ||
    lower.includes("7+ years") ||
    lower.includes("8+ years") ||
    lower.includes("10+ years")
  ) {
    experienceLevel = "Senior";
  } else if (
    lower.includes("junior") ||
    lower.includes("entry") ||
    lower.includes("intern") ||
    lower.includes("student") ||
    lower.includes("graduate") ||
    lower.includes("fresher")
  ) {
    experienceLevel = "Entry-Level";
  }

  // 5. Detect Company / Context
  let recentCompany = "your most recent organization";
  const companyPattern = /(?:at|company|team|employer|experience at)\s+([A-Z][A-Za-z0-9&]+(?:\s+[A-Z][A-Za-z0-9&]+)?)/i;
  const companyMatch = clean.match(companyPattern);
  if (companyMatch && companyMatch[1] && companyMatch[1].length < 30) {
    recentCompany = companyMatch[1].trim();
  }

  // 6. Extract Actual Project / Work Accomplishment Sentences
  const projectHighlights: string[] = [];
  const actionSentencePattern = /(?:built|developed|designed|implemented|engineered|created|optimized|migrated|architected|led|deployed)\s+[^.!?\n]{15,140}/gi;
  const matches = clean.match(actionSentencePattern);
  if (matches) {
    for (const match of matches.slice(0, 4)) {
      const trimmed = match.trim().replace(/^[-•*]\s*/, "");
      if (trimmed.length > 20 && !projectHighlights.includes(trimmed)) {
        projectHighlights.push(trimmed);
      }
    }
  }

  // Ensure default skills if resume is very brief
  if (detectedSkills.length === 0) {
    detectedSkills.push("Software Engineering", "System Design", "Problem Solving", "APIs");
  }

  // Primary technologies for direct question citation
  const primaryLang = detectedSkills[0] || "modern software stacks";
  const primaryFramework = detectedSkills[1] || detectedSkills[0] || "service frameworks";
  const primaryDataOrCloud = detectedSkills[2] || detectedSkills[1] || "data storage";
  const secondaryTool = detectedSkills[3] || detectedSkills[2] || "production tooling";

  const projectContext1 = projectHighlights[0]
    ? `where you ${projectHighlights[0]}`
    : `involving ${primaryLang} and ${primaryFramework}`;

  const projectContext2 = projectHighlights[1]
    ? `In your project where you ${projectHighlights[1]}`
    : `When building and maintaining services using ${primaryDataOrCloud}`;

  // 7. Synthesize 5 Deeply Personalized, Contextual Interview Questions
  const customQuestions: string[] = [
    // Question 1: Real Project Architecture & Tech Stack
    `"I reviewed your resume highlighting your experience as a ${targetRole}. You emphasized your work ${projectContext1}. Could you walk me through the end-to-end architecture of this system and the key technical trade-offs you evaluated during design?"`,

    // Question 2: Deep Dive into Core Technology & Edge-Cases
    `"Under your core competencies, you showcased extensive experience with ${primaryFramework} and ${primaryDataOrCloud}. Can you describe a critical performance bottleneck, concurrency issue, or architectural failure you diagnosed and resolved when using them?"`,

    // Question 3: Real Accomplishment & Resilience
    `"${projectContext2}, what were the main challenges you faced regarding scalability, error handling, or backward compatibility, and how did you verify that the solution met production standards?"`,

    // Question 4: Operational Readiness, Testing & Infrastructure
    `"In your stack utilizing ${secondaryTool}, how do you structure your automated testing, CI/CD pipeline, and observability (metrics/logs) to catch regressions before they impact end-users?"`,

    // Question 5: Situational & Engineering Decision-Making
    `"Tell me about a time when you had to balance strict feature delivery deadlines against code quality and technical debt in a team setting. How did you negotiate scope and align with other engineers?"`,
  ];

  return {
    candidateName,
    targetRole,
    experienceLevel,
    skills: detectedSkills,
    recentCompany,
    summary: `Tailored interview plan synthesized for ${candidateName} (${targetRole} · ${experienceLevel}) based on ${detectedSkills.length} identified competencies and real project experience.`,
    customQuestions,
    extractedRawText: clean.slice(0, 1500),
    projectHighlights,
  };
}
