---
name: VoxPrep Stitch System
version: 1.0.0
author: Member B (Frontend & Voice UX)
colors:
  canvas: "#0B1120"
  sidebar: "#0A101D"
  header: "#0E1627"
  surface: "#111A2E"
  surface-hover: "#16223B"
  border: "rgba(255, 255, 255, 0.08)"
  primary: "#2563EB"
  primary-light: "#3B82F6"
  accent-emerald: "#10B981"
  accent-amber: "#F59E0B"
  text-primary: "#F8FAFC"
  text-secondary: "#94A3B8"
  text-muted: "#64748B"
typography:
  fontFamily: "Inter, system-ui, -apple-system, sans-serif"
  fontMono: "JetBrains Mono, monospace"
  headline: "font-semibold tracking-tight text-white"
  label: "font-mono text-xs uppercase tracking-wider text-slate-400"
rounded:
  card: "8px"
  button: "6px"
  pill: "9999px"
---

# VOXPREP — Design System & Architecture Specification

## Overview
A minimal, restrained, professional SaaS interface for AI-driven mock interviews and communication coaching. Avoids vibe-coded / AI-template tropes (no harsh purple neon, no bloated decorative cards, no distracting animations).

## Core Architecture (5 Main Sections)
1. **Home Dashboard** (`/dashboard`): Overall readiness, interview readiness score, communication score, and recent mock sessions table.
2. **Interview Agent** (`/interview`): Dedicated video call interface featuring user camera preview (`getUserMedia`), AI interviewer presence, live closed-captions, question progression, and call controls (Mute, Camera toggle, End Call).
3. **Communication Agent** (`/coach`): Dedicated verbal fluency practice with real-time grammar suggestions, speaking pace metrics (WPM), and filler word detection.
4. **Interview Dashboard** (`/analytics/interview`): 4-rubric scoring breakdown (Relevance, Technical Depth, Clarity, Concrete Examples), strengths, and targeted improvement areas.
5. **Communication Dashboard** (`/analytics/communication`): Speaking pace, filler frequency reduction progress, grammar accuracy, and 5-week progress curves.

