# Job Application Agent v3: Full Specification & Prompting Suite

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Profile Document Schema](#2-profile-document-schema)
3. [Style Guide & Voice Calibration](#3-style-guide--voice-calibration)
4. [Agent Definitions & System Prompts](#4-agent-definitions--system-prompts)
5. [Programmatic Verification Suite](#5-programmatic-verification-suite)
6. [Verification Loops](#6-verification-loops)
7. [Orchestration Logic](#7-orchestration-logic)
8. [Review Interface](#8-review-interface)
9. [Resume Rendering Pipeline](#9-resume-rendering-pipeline)
10. [Cost Control & Token Budget](#10-cost-control--token-budget)
11. [Feedback Loop & Calibration](#11-feedback-loop--calibration)
12. [Testing Strategy](#12-testing-strategy)
13. [File Structure](#13-file-structure)
14. [Configuration](#14-configuration)

**v3 changes from v2 (summary):**
- Source mapping moved from LLM to code (Claim Extractor + Source Mapper)
- Application Questions Agent handles custom form fields
- Posting expiration checks at queue time and approval time
- Crash recovery via checkpointing
- Best-version tracking uses fact-checker quality_score (issue counts), not LLM self-score
- API-level rate limiter separate from task semaphore
- Structural AI detection uses spaCy NLP, not handwaved "syntax analysis"
- Number checker is context-aware with allowlists
- Blacklist has context-dependent exceptions (e.g. "robust" in statistical context)
- Duplicate application prevention at submission time
- Simplified calibration for small sample sizes
- Dashboard wireframes with tech stack specified
- Cover Letter Agent receives resume fact-checker flags
- Retry with exponential backoff on all LLM calls

---

## 1. Architecture Overview

### System Design

```
┌──────────────────────────────────────────────────────────────────────┐
│                     ORCHESTRATOR (async, checkpointed)                │
│    schedules agents, manages state, rate limits, budgets, recovery    │
└──┬───────┬───────┬───────┬───────┬───────┬───────┬──────────────────┘
   │       │       │       │       │       │       │
   ▼       ▼       ▼       ▼       ▼       ▼       ▼
┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌───────────────────┐
│SCOUT ││MATCH ││RESUME││COVER ││VERIFY││APP Q ││ PROGRAMMATIC      │
│Agent ││Agent ││Agent ││LETTER││Agent ││Agent ││ VERIFICATION      │
│(LLM) ││(LLM) ││(LLM) ││(LLM) ││(LLM) ││(LLM) ││ SUITE (code only) │
└──────┘└──────┘└──────┘└──────┘└──────┘└──────┘└───────────────────┘
                                                  Includes:
                                                  - Claim Extractor
                                                  - Source Mapper
                                                  - Number Checker
                                                  - Blacklist Scanner
                                                  - Structural NLP Detector
                                                  - Posting Checker
                                                  - Dedup Engine
                                                  - Application Dedup
Queue Agent = deterministic code (not LLM)
```

**Data Flow:**

1. Scout Agent → discovers jobs (APIs + research), captures application questions
2. Dedup Engine → filters discovery-time duplicates
3. Match Agent → scores + filters → ranked shortlist
4. Resume Agent → tailors resume → content + coarse entry IDs (NO source map)
5. Programmatic Verification Suite → extracts claims, builds source map, fact-checks → issues
6. If HIGH issues: back to Resume Agent with flags. If clean: continue.
7. Cover Letter Agent → drafts (receives resume fact-checker flags to avoid borderline claims)
8. Programmatic Verification Suite → same on cover letter + company claim check
9. Application Questions Agent → generates form field answers
10. Programmatic Verification Suite → fact-checks answers
11. Verify Agent (LLM) → semantic accuracy, voice, strategy
12. Posting Expiration Check → URL still live?
13. Queue Agent (code) → packages for review
14. Human reviews → approve / edit / skip
15. On approve: duplicate application check + posting re-check
16. Feedback loop → tracks outcomes, recalibrates

### Core Invariants

- **No hallucinated credentials.** Source maps built by code, not LLM self-reporting.
- **No AI fingerprints.** Blacklist (regex) + structural NLP (spaCy) + LLM review (gestalt).
- **Human-in-the-loop.** Nothing submitted without approval.
- **Iterative generation.** Draft → code verify → revise → LLM verify.
- **Budget-aware.** Token costs tracked per call. Hard ceilings.
- **Best-version by evidence.** Quality measured by fact-checker issue counts, not self-assessment.
- **Crash-resilient.** Checkpointed at every stage. Recoverable on restart.

---

## 2. Profile Document Schema

```json
{
  "meta": {
    "last_updated": "ISO-8601",
    "version": "1.0.0",
    "profile_completeness": {
      "has_writing_samples": false,
      "has_accomplishments": false,
      "has_publications": false,
      "sparse_fields": []
    }
  },
  "identity": {
    "name": "", "email": "", "phone": "",
    "location": {
      "city": "", "state": "", "country": "",
      "willing_to_relocate": true, "relocation_preferences": [],
      "remote_preference": "remote | hybrid | onsite | flexible"
    },
    "visa_status": {
      "current_authorization": "", "requires_sponsorship": true,
      "relevant_documentation": []
    },
    "links": {
      "linkedin": "", "github": "", "google_scholar": "",
      "personal_site": "", "other": []
    }
  },
  "summary": {
    "elevator_pitch": "",
    "keywords": [],
    "target_roles": [
      { "title_patterns": [], "industry": "", "priority": 1, "search_queries": [] }
    ]
  },
  "education": [
    {
      "id": "edu_001", "degree": "", "field": "", "institution": "",
      "year_completed": "", "honors": "", "thesis_title": "",
      "relevant_coursework": [], "notes": ""
    }
  ],
  "experience": [
    {
      "id": "exp_001", "title": "", "organization": "",
      "start_date": "", "end_date": "", "is_current": false, "contract": false,
      "responsibilities": [], "accomplishments": [], "tools_used": [], "keywords": []
    }
  ],
  "publications": [
    {
      "id": "pub_001", "title": "", "authors": [], "journal": "", "year": "",
      "doi": "", "type": "peer-reviewed | preprint | book | book-chapter | conference",
      "impact_factor": null, "citation_count": null, "summary": ""
    }
  ],
  "book": {
    "title": "", "publisher": "", "expected_publication": "",
    "status": "in-progress | submitted | in-review | published",
    "summary": "", "key_contributions": []
  },
  "skills": {
    "programming": { "expert": [], "proficient": [], "familiar": [] },
    "statistical_methods": [], "domain_expertise": [],
    "tools_and_platforms": [], "soft_skills": []
  },
  "presentations": [
    { "id": "pres_001", "title": "", "venue": "", "date": "", "type": "talk | poster | workshop | invited" }
  ],
  "certifications": [],
  "other": { "martial_arts": "", "music_background": "", "languages": [], "interests": [] },
  "application_preferences": {
    "salary_range": { "min": null, "max": null, "currency": "USD" },
    "deal_breakers": [], "strong_preferences": [],
    "companies_to_avoid": [], "companies_of_interest": []
  },
  "application_question_answers": {
    "sponsorship_required": null,
    "willing_to_relocate": null,
    "salary_expectation": "",
    "years_of_experience": "",
    "highest_education": "",
    "custom_answers": {}
  }
}
```

### Normalized Index (Auto-Generated at Load Time)

NOT stored in profile.json. Built in memory at startup by `ProfileIndex`:

```python
class ProfileIndex:
    def __init__(self, profile):
        self.profile = profile
        self.experience_text = {}  # id → concatenated lowercase text
        for exp in profile["experience"]:
            self.experience_text[exp["id"]] = " ".join([
                exp["title"], exp["organization"],
                " ".join(exp["responsibilities"]),
                " ".join(exp["accomplishments"]),
                " ".join(exp["tools_used"]),
                " ".join(exp["keywords"])
            ]).lower()
        self.legitimate_numbers = self._extract_all_numbers()
        self.dates = self._extract_all_dates()
        self.titles = {e["id"]: e["title"] for e in profile["experience"]}
        self.orgs = {e["id"]: e["organization"] for e in profile["experience"]}
        self.skills_flat = self._flatten_skills()
        self.pub_titles = {p["id"]: p["title"] for p in profile["publications"]}
        self.derived_counts = {
            "num_publications": str(len(profile["publications"])),
            "num_presentations": str(len(profile["presentations"])),
        }
```

### Handling Sparse Profiles

| Missing Data | Behavior |
|---|---|
| No writing samples | CL Agent uses conservative register. Verify skips voice. Warns user. |
| No accomplishments | Resume uses responsibilities only. Never invents metrics. Flags user. |
| No publications | Omit section. |
| No app question answers | App Questions Agent generates from profile, flags ALL for human review. |
| No salary range | Match Agent skips salary in feasibility. |

---

## 3. Style Guide & Voice Calibration

Writing samples stored in JSON are insufficient for reliable voice matching. The system uses a **Style Guide** — a dedicated document engineered through human review.

### Style Guide Schema

Stored as `profile/style_guide.md` (not in profile.json).

```markdown
# Candidate Voice Style Guide

## Overview
[2-3 sentences describing overall writing personality]

## Sentence Structure
- Average sentence length: [short/medium/long]
- Subordinate clauses: [rarely/sometimes/frequently]
- Variety pattern: [description]
- Example characteristic sentence: "[actual sentence]"

## Vocabulary
- Register: [academic formal / professional / conversational / direct]
- Contractions: [yes/no/sometimes]
- First person: [frequently/sparingly]
- Jargon level: [defines terms / uses without explanation]
- Words the candidate ACTUALLY uses: [list]
- Words the candidate NEVER uses: [list]

## Tone
- Directness: [very direct / somewhat hedged / diplomatic]
- Humor: [none / dry / occasional]
- Confidence: [understated / matter-of-fact / assertive]
- Uncertainty handling: [acknowledges directly / hedges / omits]

## Characteristic Patterns
- [e.g., "Starts paragraphs with context before claims"]
- [e.g., "Uses em-dashes frequently"]
- [e.g., "Favors active voice almost exclusively"]

## Anti-Patterns (Things This Candidate Would Never Write)
- [Anti-pattern 1]
- [Anti-pattern 2]

## Few-Shot Examples

### Example 1: Professional/Cover Letter Register
Source: [where this came from]
> [2-3 paragraphs of actual candidate writing]

### Example 2: Technical/Academic Register
Source: [where this came from]
> [2-3 paragraphs of actual candidate writing]

### Example 3: Informal Professional Register
Source: [where this came from]
> [1-2 paragraphs of actual candidate writing]
```

### Calibration Process

Not auto-generated. Created through a one-time interactive session:

1. User uploads 5+ writing samples across registers
2. LLM analyzes samples and produces draft Style Guide
3. User reviews and corrects
4. User provides 2-3 "sounds like me" and 2-3 "doesn't sound like me" examples
5. Style Guide finalized

Cover Letter Agent and Verify Agent receive the full Style Guide as context.

---

## 4. Agent Definitions & System Prompts

### 4.1 Scout Agent

**Purpose:** Discover relevant job postings through APIs, aggregators, and structured market research.

**Model tier:** Sonnet. **Token budget:** ~4K in, ~2K out per cycle.

**Access methods:**
- **Tier 1 (API):** SerpAPI/Apify for board results; Greenhouse/Lever public JSON APIs; Adzuna/The Muse/Remotive
- **Tier 2 (Web search):** Parameterized queries for market research
- **Tier 3 (Watchlists):** config/watchlist.yaml with company career pages, RSS feeds, YC batches, arXiv queries

```
SYSTEM PROMPT — SCOUT AGENT
============================

You are a job discovery agent. You find opportunities through structured data sources — NOT by scraping job boards directly.

## Available Tools

1. **job_search_api(query, location, platform)** — SerpAPI/Apify. Structured listings from LinkedIn, Indeed, Glassdoor. Max 10 calls/cycle.
2. **greenhouse_api(company_slug)** — Open positions + application form fields at Greenhouse companies.
3. **lever_api(company_slug)** — Same for Lever companies.
4. **web_search(query)** — General web search for market research. Max 15 calls/cycle.
5. **watchlist_check()** — Polls all watchlist URLs. Returns new postings since last check.

## Mode 1: Structured Job Search

Construct queries from profile.target_roles and profile.skills. Vary across:
- Title-based: each title pattern
- Skill-based: 2-3 keyword combinations
- Industry-specific: pharma, quant finance, AI variants
- Use pre-built queries from profile.target_roles[].search_queries

Deduplicate at coarse level (exact URL match). Dedup Engine handles the rest.

## Mode 2: Active Market Research (daily cycle)

Execute in order:
1. watchlist_check()
2. web_search for recently funded companies in relevant domains
3. web_search for accelerator portfolio companies
4. Propose watchlist additions for user approval:
   { "company": "", "career_url": "", "reason": "", "platform": "greenhouse|lever|workday|other" }

## Output Format

Per opportunity:
{
  "job_id": "scout_{timestamp}_{hash}",
  "source": "serpapi_linkedin | serpapi_indeed | greenhouse_api | lever_api | web_search | watchlist",
  "source_url": "direct URL",
  "company": {
    "name": "", "industry": "",
    "size": "startup | small | mid | large | enterprise",
    "stage": "pre-seed | seed | series-a | series-b | growth | public | unknown",
    "description": "1-2 sentences", "why_relevant": ""
  },
  "role": {
    "title": "", "url": "", "description_raw": "full text",
    "location": "", "remote_policy": "", "posted_date": "",
    "application_deadline": null, "requires_cover_letter": null,
    "salary_range": null, "visa_sponsorship": null
  },
  "application_questions": [
    {
      "question_text": "", "question_type": "free_text | multiple_choice | yes_no | numeric",
      "required": true, "max_length": null, "options": null
    }
  ],
  "discovery_method": "api_search | market_research | watchlist",
  "discovery_reasoning": "", "search_query_used": ""
}

## Rules

- Do NOT filter. Match Agent handles that.
- CAPTURE APPLICATION QUESTIONS from Greenhouse/Lever APIs and job posting text.
- Record source, query, reasoning. Pipeline must be auditable.
- Respect rate limits. If a career page URL errors, log and move on.
- Flag visa sponsorship when visible. Null if unlisted.
- Include full raw job description.
```

### 4.2 Match Agent

**Purpose:** Score and rank discovered jobs against the candidate profile.

**Model tier:** Sonnet default, Opus for MARGINAL re-scoring. **Token budget:** ~6K in, ~1K out per job.

```
SYSTEM PROMPT — MATCH AGENT
=============================

You score job-candidate match quality. You receive a candidate profile and job opportunities.

## Scoring Dimensions (1-10 each)

1. **Skills Match (0.30)** — % of required/preferred skills present. Missing required >> missing nice-to-have.
2. **Experience Match (0.25)** — Level, domain, track record. Academic at discount for industry unless directly relevant.
3. **Growth/Impact Potential (0.20)** — Would this use strengths? Overqualified = low. Outsized impact = high.
4. **Practical Feasibility (0.15)** — Location/remote, visa, salary. If visa_sponsorship is null: score ≤ 6 with note.
5. **Strategic Value (0.10)** — Career trajectory, network, domain doors opened.

## Composite Score

composite = (skills × 0.30) + (experience × 0.25) + (growth × 0.20) + (feasibility × 0.15) + (strategic × 0.10)

## Classification

- STRONG (≥ 7.5): auto-proceed to generation
- GOOD (6.0-7.4): auto-proceed
- MARGINAL (4.5-5.9): queue for human triage
- WEAK (< 4.5): archive with reasoning

## Output

Per job:
{
  "job_id": "",
  "classification": "STRONG | GOOD | MARGINAL | WEAK",
  "composite_score": 0.0,
  "dimension_scores": {
    "skills_match": { "score": 0, "reasoning": "" },
    "experience_match": { "score": 0, "reasoning": "" },
    "growth_potential": { "score": 0, "reasoning": "" },
    "feasibility": { "score": 0, "reasoning": "" },
    "strategic_value": { "score": 0, "reasoning": "" }
  },
  "key_selling_points": [],
  "gaps": [],
  "tailoring_notes": "Guidance for Resume/CL agents"
}

## Rules

- Brutally honest about gaps.
- Score transferable skills, don't inflate.
- Flag visa risks.
- Every scoring decision references specific profile entries.
- If config/scoring_weights.yaml exists with calibrated weights, use those instead of defaults.
```

Passes `application_questions` through to downstream agents.

### 4.3 Resume Agent (REVISED — No Source Map)

**Critical change:** The Resume Agent outputs ONLY resume content + a coarse list of profile entry IDs it drew from. The Programmatic Verification Suite builds the source map independently.

Model: Opus. Budget: ~8K in, ~3K out per iteration, up to 6 iterations.

```
SYSTEM PROMPT — RESUME AGENT
==============================

You are a resume tailoring specialist. Produce a resume grounded strictly in the Profile Document.

## Process

Iterative draft → programmatic verification → revise loop.

### Drafting

1. Select relevant content from Profile Document for THIS role.
2. Order strategically per job posting priorities.
3. Mirror job language where genuine. NEVER claim unsupported experience.
4. Quantify from profile only. No invented metrics.
5. ATS-friendly format. Standard headers. 1-2 pages.

### What You Output

1. Full resume content in markdown
2. List of profile entry IDs you drew from (coarse: ["exp_001", "pub_002", ...])

You do NOT generate a source map. Code handles that.

### Handling Fact-Checker Feedback

The Programmatic Verification Suite will send specific issues:
- "Line 'Led development of...' — no matching text found in any experience entry"
- "Number '40%' not found in profile"
- "Blacklisted phrase: 'leveraged'"
- "4 consecutive bullets with identical syntactic pattern"

Address each:
- Fix the claim to match profile
- Remove ungroundable claims
- Replace blacklisted vocabulary
- Vary sentence structure where flagged

Do NOT invent new claims to replace removed ones. Cut if needed.

### Handling Verify Agent Feedback

Verify Agent catches semantic issues:
- "You wrote 'led' but profile says 'contributed to'"
- "This role emphasizes X but your resume buries it"
- "Structural AI fingerprint: ..."

Address without regressing previously fixed issues.

## Output Format

{
  "resume_content": "Full markdown",
  "profile_entries_used": ["exp_001", "exp_003", "pub_002"],
  "iterations_completed": 2,
  "iteration_log": [...],
  "remaining_concerns": [],
  "profile_version": "1.0.0"
}

## Rules

- NEVER fabricate. No claim without profile support.
- NEVER invent metrics.
- NEVER keyword-stuff.
- When fact-checker flags something: FIX or REMOVE. Do not argue.
```

### 4.4 Cover Letter Agent (REVISED — Receives Fact-Checker Flags)

Model: Opus. Budget: ~10K in, ~2K out per iteration.

**Change:** Receives fact-checker results from the resume so it avoids repeating borderline claims.

```
SYSTEM PROMPT — COVER LETTER AGENT
====================================

You write cover letters that sound like the candidate. Use the Style Guide for voice calibration.

## Awareness of Resume Fact-Check Results

You receive the fact-checker's resume findings. Pay attention to:
- MEDIUM severity issues (borderline claims) — do NOT repeat or amplify
- Claims removed during resume revision — do not reintroduce
- Final resume content — do not contradict

## Process

1. Opening: specific hook, no "I am writing to express my interest"
2. Body: 1-2 accomplishments with narrative the resume can't provide
3. "Why this company": specific, verifiable, non-transferable
4. Closing: confident, brief
5. Length: 250-400 words

Same output structure as Resume Agent: content + coarse entry IDs + company facts. No source map.

## Output Format

{
  "cover_letter_content": "Full text",
  "profile_entries_used": ["exp_001", "pub_003"],
  "company_facts_used": [
    {"claim": "...", "source": "job_posting", "source_text": "..."}
  ],
  "voice_match_confidence": "high | medium | low | not_assessed",
  "iterations_completed": 2,
  "iteration_log": [...],
  "remaining_concerns": [],
  "profile_version": "1.0.0"
}

## Rules

- NEVER fabricate.
- NEVER sound like AI.
- Style Guide > conventions.
- Do not repeat claims flagged borderline on the resume.
```

### 4.5 Application Questions Agent (NEW)

Model: Sonnet. Budget: ~4K in, ~1K out per application.

```
SYSTEM PROMPT — APPLICATION QUESTIONS AGENT
=============================================

Generate answers to application form questions.

## Priority Order

1. profile.application_question_answers — pre-approved. Use verbatim or adapt minimally.
2. Profile Document fields — for questions not pre-approved.
3. Job posting — for "why this company" questions.

## Handling

| Pattern | Source | Notes |
|---|---|---|
| Sponsorship | profile.visa_status | Exact value |
| Salary | profile.application_preferences | Range or "negotiable" |
| Relocate | profile.identity.location | Direct |
| Years experience | Compute from experience dates | Calculate |
| Why here | job posting + pre-approved | Adapt with specifics |
| Custom/unusual | Profile + context | Flag for human review |

## Output

Per question:
{
  "question_text": "...",
  "answer": "...",
  "source": "pre_approved | profile_derived | job_posting_derived",
  "profile_entries_used": [],
  "confidence": "high | medium | low",
  "needs_human_review": false
}

## Rules

- Pre-approved answers first.
- Yes/no: answer directly.
- Free-text: 50-150 words.
- Low confidence → needs_human_review: true.
- NEVER fabricate. Same grounding rules.
- No AI-telltale language.
```

### 4.6 Verify Agent (LLM)

**Purpose:** Catches subtle issues that code can't: semantic inflation, voice mismatch, strategic quality.

**Model tier:** Opus. **Token budget:** ~14K in, ~2K out.

Runs AFTER Programmatic Suite. Does NOT re-check code-verifiable items.

```
SYSTEM PROMPT — VERIFY AGENT
==============================

You are an adversarial quality reviewer. Documents you receive have ALREADY passed programmatic fact-checking. Your job is to catch what code can't.

## What's Already Been Checked (Don't Repeat)

The Programmatic Verification Suite has verified:
- Every claim traced to a profile entry (code-generated source map)
- Job titles, dates, org names letter-perfect
- No unverified metrics/numbers
- No skills above proficiency level
- Vocabulary blacklist (regex + context-dependent exceptions)
- Structural patterns: parallel bullets, tricolons, paragraph balance, connectors, sentence uniformity (spaCy NLP)
- Application question answers grounded in profile

These passed. Focus on what code can't catch.

## What You CHECK

### 1. Semantic Accuracy

- Accomplishments inflated through paraphrase? ("contributed to" → "led"?)
- Responsibilities from one role attributed to another?
- Time periods misrepresented?
- Skills claimed in context implying deeper expertise than profile supports?
- CL "why this company" accurate or mischaracterizing?
- App question answers technically correct but misleading?

### 2. AI Fingerprint Detection (gestalt)

NLP caught mechanical patterns. You look for:
- Overall "feel" — does this read like a human?
- Technically varied but still synthetic passages
- Vocabulary correct but weirdly elevated
- Suspiciously perfect argumentation flow

### 3. Voice Match (CL only, if Style Guide available)

- Matches Style Guide voice?
- Characteristic patterns present? Anti-patterns absent?
- Resume and CL sound like the same person?

### 4. Strategic Quality

- Resume emphasizes right things for this role?
- CL adds value beyond resume?
- Profile strengths left on the table?
- Gaps addressed honestly?
- App question answers strengthen the application?
- Would a hiring manager for THIS role find these compelling?

## Output Format

{
  "verdict": "PASS | FAIL",
  "resume_review": {
    "semantic_issues": [],
    "ai_fingerprints": [],
    "strategic_issues": [],
    "status": "PASS | FAIL"
  },
  "cover_letter_review": {
    "semantic_issues": [],
    "ai_fingerprints": [],
    "voice_issues": [],
    "strategic_issues": [],
    "status": "PASS | FAIL | N/A"
  },
  "app_questions_review": {
    "issues": [],
    "status": "PASS | FAIL | N/A"
  },
  "revision_instructions": {
    "resume": [],
    "cover_letter": [],
    "app_questions": []
  },
  "notes": ""
}

## Rules

- You are the last LLM. After you, it goes to the human.
- Err on FAIL. Revision is cheap; bad applications are not.
- Be specific. Line-level citations, not vague complaints.
- If you PASS: "I would submit this under my own name."
```

### 4.7 Queue Agent

Deterministic code. Not LLM. Packages, sorts (deadline first then score), notifies. Now includes `application_questions` in package and `posting_verified_live` flag.

---

## 5. Programmatic Verification Suite

All code, no LLM. This is the critical infrastructure.

### 5.1 Claim Extractor

**Design principle:** Each resume bullet or cover letter sentence is one claim unit. We do NOT decompose into atomic facts.

```python
class ClaimExtractor:
    def extract_from_resume(self, markdown_content):
        """
        Returns list of claim dicts. Each has:
        - text: the claim content
        - line_number: position in source
        - section: which resume section
        - type: "bullet" | "structural" | "content"
        """
        claims = []
        lines = markdown_content.strip().split('\n')
        current_section = None
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith('#'):
                current_section = stripped.lstrip('#').strip().lower()
                continue
            if re.match(r'^[-*•]\s+', stripped):
                claims.append({
                    "text": re.sub(r'^[-*•]\s+', '', stripped),
                    "line_number": i + 1,
                    "section": current_section,
                    "type": "bullet"
                })
            elif current_section in ("experience", "education", "publications", "skills"):
                claim_type = "structural" if self._is_structural(stripped) else "content"
                claims.append({
                    "text": stripped, "line_number": i + 1,
                    "section": current_section, "type": claim_type
                })
        return claims

    def extract_from_cover_letter(self, text):
        """Each sentence is one claim unit."""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [
            {"text": s.strip(), "sentence_index": i, "type": "sentence"}
            for i, s in enumerate(sentences) if s.strip()
        ]

    def _is_structural(self, line):
        """Company/title/date headers rather than claims."""
        if '|' in line or '—' in line or '–' in line:
            return True
        if re.match(r'^[\d]{4}\s*[-–—]\s*([\d]{4}|present)', line, re.I):
            return True
        if len(line.split()) <= 4 and not any(c in line for c in '.!?'):
            return True
        return False
```

### 5.2 Source Mapper (Code-Generated)

**The key v3 change.** Source maps built by code, not LLM.

```python
from difflib import SequenceMatcher

class SourceMapper:
    """
    Threshold tuning guidance:
    - Start at 0.30 for resume, 0.25 for cover letters
    - Run against test fixtures, count false positives vs false negatives
    - Adjust in config.yaml without code changes
    - CL threshold is lower because CL sentences mix candidate claims with
      company claims in the same sentence, deflating SequenceMatcher scores
    """

    def __init__(self, profile_index, config=None):
        self.index = profile_index
        config = config or {}
        self.resume_threshold = config.get("source_mapper_resume_threshold", 0.30)
        self.cover_letter_threshold = config.get("source_mapper_cover_letter_threshold", 0.25)

    def map_claims(self, claims, claimed_entry_ids=None, content_type="resume"):
        """
        For each claim, find best matching profile entry.
        claimed_entry_ids: coarse IDs from LLM (prioritizes search, not trusted blindly)
        content_type: "resume" or "cover_letter" — selects threshold
        """
        threshold = self.resume_threshold if content_type == "resume" else self.cover_letter_threshold
        results = []
        for claim in claims:
            if claim["type"] == "structural":
                results.append({"claim": claim, "match": self._match_structural(claim), "status": "structural"})
                continue

            # For CL sentences that contain the company name, skip source mapping
            # (these are company claims, not candidate claims — verified separately)
            if content_type == "cover_letter" and self._is_company_claim(claim["text"]):
                results.append({"claim": claim, "match": None, "status": "company_claim_skipped"})
                continue

            best = self._find_best_match(claim["text"], claimed_entry_ids)
            status = "matched" if best["score"] >= threshold else "unmatched"
            entry = {"claim": claim, "match": best, "status": status}
            if status == "unmatched":
                entry["issue"] = {
                    "type": "UNGROUNDED_CLAIM", "severity": "HIGH",
                    "message": f"Line {claim.get('line_number', '?')}: '{claim['text'][:80]}' — "
                               f"best match: {best['entry_id']} at {best['score']:.2f}"
                }
            results.append(entry)
        return results

    def _is_company_claim(self, text):
        """
        Heuristic: if a CL sentence is primarily about the company (contains
        'your', 'the company', 'the team', or the company name) and doesn't
        contain first-person claims ('I', 'my', 'we'), skip source mapping.
        Company claims are verified separately against the job posting.
        """
        text_lower = text.lower()
        company_signals = any(w in text_lower for w in ["your ", "the company", "the team",
                                                         "the role", "this position"])
        candidate_signals = any(w in text_lower for w in [" i ", "i've", "i'd", " my ", " we "])
        # Pure company claim = has company signals, no candidate signals
        return company_signals and not candidate_signals

    def _find_best_match(self, claim_text, priority_ids=None):
        claim_lower = claim_text.lower()
        best = {"entry_id": None, "score": 0, "matched_field": None, "matched_text": ""}

        # Search experience accomplishments + responsibilities
        for exp in self.index.profile["experience"]:
            eid = exp["id"]
            for field, items in [("accomplishments", exp["accomplishments"]),
                                  ("responsibilities", exp["responsibilities"])]:
                for i, item in enumerate(items):
                    score = SequenceMatcher(None, claim_lower, item.lower()).ratio()
                    if score > best["score"]:
                        best = {"entry_id": eid, "score": score,
                                "matched_field": f"{field}[{i}]", "matched_text": item}

        # Publications
        for pid, ptitle in self.index.pub_titles.items():
            score = SequenceMatcher(None, claim_lower, ptitle.lower()).ratio()
            if score > best["score"]:
                best = {"entry_id": pid, "score": score, "matched_field": "title", "matched_text": ptitle}

        # Education
        for edu in self.index.profile["education"]:
            edu_text = f"{edu['degree']} {edu['field']} {edu['institution']}".lower()
            score = SequenceMatcher(None, claim_lower, edu_text).ratio()
            if score > best["score"]:
                best = {"entry_id": edu["id"], "score": score, "matched_field": "education", "matched_text": edu_text}

        return best
```

### 5.3 Number Checker (Context-Aware)

```python
class NumberChecker:
    def __init__(self, profile_index):
        self.index = profile_index

    def check(self, content):
        issues = []
        for match in re.finditer(r'\b(\d+(?:\.\d+)?%?)\b', content):
            number = match.group(1)
            start, end = max(0, match.start()-60), min(len(content), match.end()+60)
            context = content[start:end].lower()
            classification = self._classify(number, context)
            if classification == "needs_verification" and not self._in_profile(number):
                issues.append({
                    "type": "UNVERIFIED_METRIC", "severity": "HIGH",
                    "number": number, "context": context.strip(),
                    "message": f"Metric '{number}' not in profile. Context: {context.strip()}"
                })
        return issues

    def _classify(self, number, context):
        num_val = int(float(number.rstrip('%'))) if number.rstrip('%').replace('.','').isdigit() else None
        # Dates
        if num_val and 1950 <= num_val <= 2030: return "exempt_date"
        if number in self.index.dates: return "exempt_date"
        # Derived counts
        if re.search(rf'{number}\s+publications?', context):
            if number == self.index.derived_counts.get("num_publications"): return "exempt_derived"
        if re.search(rf'{number}\s+presentations?', context):
            if number == self.index.derived_counts.get("num_presentations"): return "exempt_derived"
        # Experience years
        if re.search(rf'{number}\+?\s+years?\s+of\s+(experience|expertise)', context): return "exempt_structural"
        return "needs_verification"

    def _in_profile(self, number):
        return number in self.index.legitimate_numbers or number in self.index.derived_counts.values()
```

### 5.4 Structural AI Detector (spaCy NLP)

```python
import spacy
nlp = spacy.load("en_core_web_sm")

class StructuralAIDetector:
    def __init__(self, config):
        self.max_parallel = config.get("max_consecutive_parallel_bullets", 3)
        self.max_tricolons = config.get("max_tricolon_lists", 1)
        self.max_connectors = config.get("max_connector_words_per_document", 2)
        self.connectors = set(w.lower() for w in config.get("connector_words", []))

    def check(self, content, content_type="resume"):
        issues = []
        if content_type == "resume":
            issues.extend(self._parallel_bullets(content))
        issues.extend(self._tricolons(content))
        issues.extend(self._connector_excess(content))
        issues.extend(self._paragraph_balance(content))
        issues.extend(self._sentence_uniformity(content))
        return issues

    def _parallel_bullets(self, content):
        """Consecutive bullets with identical POS opening pattern."""
        issues = []
        bullets = re.findall(r'^[-*•]\s+(.+)$', content, re.MULTILINE)
        if len(bullets) < 3: return issues
        patterns = [tuple(t.pos_ for t in nlp(b)[:4]) for b in bullets]
        run = 1
        for i in range(1, len(patterns)):
            if patterns[i] == patterns[i-1]:
                run += 1
                if run > self.max_parallel:
                    issues.append({"type": "PARALLEL_BULLETS", "severity": "MEDIUM",
                        "message": f"{run} consecutive bullets with pattern {' '.join(patterns[i])}"})
            else:
                run = 1
        return issues

    def _tricolons(self, content):
        issues = []
        count = len(re.findall(r'(\w+),\s+(\w+),\s+and\s+(\w+)', content))
        if count > self.max_tricolons:
            issues.append({"type": "TRICOLON_EXCESS", "severity": "LOW",
                "message": f"{count} tricolon patterns (max {self.max_tricolons})"})
        return issues

    def _connector_excess(self, content):
        found = []
        for w in self.connectors:
            found.extend([w] * len(re.findall(rf'\b{w}\b', content, re.I)))
        if len(found) > self.max_connectors:
            return [{"type": "CONNECTOR_EXCESS", "severity": "MEDIUM",
                "message": f"{len(found)} connectors (max {self.max_connectors}): {', '.join(found)}"}]
        return []

    def _paragraph_balance(self, content):
        paras = [p for p in content.split('\n\n') if p.strip() and not p.strip().startswith('#')]
        if len(paras) < 3: return []
        lengths = [len(p.split()) for p in paras]
        mean = sum(lengths)/len(lengths)
        if mean == 0: return []
        cv = (sum((l-mean)**2 for l in lengths)/len(lengths))**0.5 / mean
        if cv < 0.15:
            return [{"type": "PARAGRAPH_BALANCE", "severity": "LOW",
                "message": f"Paragraph lengths uniform (CV={cv:.2f}): {lengths}"}]
        return []

    def _sentence_uniformity(self, content):
        sents = list(nlp(content).sents)
        if len(sents) < 5: return []
        lengths = [len(s) for s in sents]
        mean = sum(lengths)/len(lengths)
        if mean == 0: return []
        cv = (sum((l-mean)**2 for l in lengths)/len(lengths))**0.5 / mean
        if cv < 0.20:
            return [{"type": "SENTENCE_UNIFORMITY", "severity": "LOW",
                "message": f"Sentence lengths uniform (CV={cv:.2f})"}]
        return []
```

### 5.5 Blacklist Scanner (Context-Dependent)

```python
class BlacklistScanner:
    def __init__(self, path="config/ai_blacklist.yaml"):
        config = yaml.safe_load(open(path))
        self.words = config["words"]
        self.phrases = config["phrases"]
        self.context_dependent = config.get("context_dependent", {})

    def check(self, content):
        issues = []
        cl = content.lower()
        for phrase in self.phrases:
            if phrase.lower() in cl:
                issues.append({"type": "AI_PHRASE", "severity": "HIGH", "text": phrase,
                    "message": f"Blacklisted phrase: '{phrase}'"})
        for word in self.words:
            if word.lower() not in cl: continue
            if word.lower() in self.context_dependent:
                exceptions = self.context_dependent[word.lower()]
                for m in re.finditer(rf'\b{re.escape(word)}\b', content, re.I):
                    window = content[max(0,m.start()-80):min(len(content),m.end()+80)].lower()
                    if not any(t.lower() in window for t in exceptions):
                        issues.append({"type": "AI_VOCABULARY", "severity": "MEDIUM",
                            "text": word, "message": f"Blacklisted: '{word}' (no exception context)"})
            else:
                issues.append({"type": "AI_VOCABULARY", "severity": "MEDIUM",
                    "text": word, "message": f"Blacklisted: '{word}'"})
        return issues
```

Blacklist YAML adds `context_dependent` section:
```yaml
context_dependent:
  robust:
    - regression
    - estimator
    - standard error
    - variance
    - statistical
    - inference
    - model
    - heteroscedastic
```

### 5.6 Posting Checker + Application Dedup

```python
class PostingChecker:
    async def is_live(self, url):
        """Returns (is_live, status_code, notes)"""
        # HEAD/GET request, check for 404/410, scan body for expired signals
        ...

class ApplicationDeduplicator:
    def check(self, job, application_history):
        """Checks if we already applied to similar role at same company."""
        for past in application_history:
            if past["status"] in ("skipped", "error"): continue
            if SequenceMatcher(None, job.company.name.lower(), past["company"].lower()).ratio() < 0.80: continue
            title_sim = SequenceMatcher(None, job.role.title.lower(), past["title"].lower()).ratio()
            if title_sim > 0.75:
                return (True, past, title_sim)
        return (False, None, 0.0)
```

### 5.7 Unified Verification Runner

```python
class VerificationRunner:
    def __init__(self, profile_index, config):
        self.claims = ClaimExtractor()
        self.mapper = SourceMapper(profile_index, config)
        self.numbers = NumberChecker(profile_index)
        self.blacklist = BlacklistScanner()
        self.structural = StructuralAIDetector(config["structural_rules"])

    def verify_resume(self, content, claimed_ids):
        issues = []
        claims = self.claims.extract_from_resume(content)
        source_map = self.mapper.map_claims(claims, claimed_ids, content_type="resume")
        issues.extend([r["issue"] for r in source_map if r["status"] == "unmatched"])
        issues.extend(self.numbers.check(content))
        issues.extend(self.blacklist.check(content))
        issues.extend(self.structural.check(content, "resume"))
        return {
            "status": "PASS" if not any(i["severity"]=="HIGH" for i in issues) else "FAIL",
            "issues": issues, "source_map": source_map,
            "quality_score": self._score(issues),
            "high_count": sum(1 for i in issues if i["severity"]=="HIGH"),
            "medium_count": sum(1 for i in issues if i["severity"]=="MEDIUM"),
            "low_count": sum(1 for i in issues if i["severity"]=="LOW"),
        }

    def verify_cover_letter(self, content, claimed_ids, company_facts, job_text):
        issues = []
        claims = self.claims.extract_from_cover_letter(content)
        source_map = self.mapper.map_claims(claims, claimed_ids, content_type="cover_letter")
        # Only flag unmatched claims that aren't company-claim sentences
        issues.extend([r["issue"] for r in source_map
                       if r["status"] == "unmatched"])
        for fact in company_facts:
            if fact["source"]=="job_posting" and fact["source_text"].lower() not in job_text.lower():
                issues.append({"type":"UNVERIFIED_COMPANY_CLAIM","severity":"HIGH",
                    "message":f"Company claim not in posting: '{fact['claim'][:80]}'"})
        issues.extend(self.numbers.check(content))
        issues.extend(self.blacklist.check(content))
        issues.extend(self.structural.check(content, "cover_letter"))
        return {"status": "PASS" if not any(i["severity"]=="HIGH" for i in issues) else "FAIL",
                "issues": issues, "source_map": source_map,
                "quality_score": self._score(issues)}

    def _score(self, issues):
        """Objective quality score. Higher = better. Replaces LLM self-score."""
        s = 100
        for i in issues:
            s -= {"HIGH":15,"MEDIUM":5,"LOW":1}.get(i["severity"],0)
        return max(0, s)
```
## 6. Verification Loops

### 6.1 Resume Generation Loop

```
START
  │
  ▼
[Resume Agent: Draft] ─── content + coarse entry IDs
  │
  ▼
[Verification Suite] ─── claim extract → source map (code) → numbers → blacklist → structural NLP
  │                       → quality_score = X
  │
  ├── HIGH issues? ──► [Resume Agent: Revise with issue list]
  │                          │
  │                          ▼
  │                    [Verification Suite] → quality_score = Y
  │                          │
  │                          └── (loop max 4 times)
  │
  └── No HIGH issues? ──► [Verify Agent (LLM)] ── semantic, voice, strategy
                                │
                                ├── PASS ──► continue
                                └── FAIL ──► [Resume Agent: Revise with LLM feedback]
                                                   └── back to Verification Suite (max 2 LLM rejections)

BEST-VERSION TRACKING:
- quality_score from Verification Suite (code), NOT LLM self-score
- After each iteration: keep version with highest quality_score
- Verify Agent reviews best_version, not latest

CHECKPOINTING:
- After each iteration: save to data/checkpoints/{job_id}/resume_iter_{n}.json
- Contains: content, entry_ids, verification_result, quality_score
- On crash: detect status="generating", resume from last checkpoint

ESCAPE:
- After max iterations: package best_version + issues → Queue with "needs_human_help"
```

### 6.2 Cover Letter Loop

Same structure. Additionally receives resume fact-checker flags.

### 6.3 Application Questions

Simpler: one draft → verification → one revision if needed → flag low-confidence for human. No LLM verify pass.

### 6.4 AI Fingerprint Detection — Division of Labor

| Check | Handler | Implementation |
|---|---|---|
| Blacklisted words/phrases | BlacklistScanner | Regex + context windows |
| Parallel bullets | StructuralAIDetector | spaCy POS tag comparison |
| Tricolons | StructuralAIDetector | Regex + group counting |
| Connector overuse | StructuralAIDetector | Regex counting |
| Paragraph balance | StructuralAIDetector | Word count CV |
| Sentence uniformity | StructuralAIDetector | spaCy sentence length CV |
| Voice mismatch | Verify Agent (LLM) | Style Guide judgment |
| Semantic inflation | Verify Agent (LLM) | Meaning understanding |
| Gestalt "feels AI" | Verify Agent (LLM) | Irreducibly subjective |

---

## 7. Orchestration Logic

### 7.1 Async Orchestrator with Checkpointing + Retry

Key design decisions:
- **Task semaphore** limits concurrent generation pipelines (default 3)
- **API rate limiter** limits concurrent LLM API calls (default 5) and per-minute rate — SEPARATE from task semaphore
- **All LLM calls** go through `_call_llm()` which handles retry with exponential backoff
- **Checkpoints** saved after each pipeline stage to disk
- **Crash recovery** on startup: detect incomplete pipelines, resume from last checkpoint
- **Circuit breaker**: 5 failures per agent → pause pipeline, alert user

```python
class Orchestrator:
    def __init__(self, config):
        self.task_semaphore = asyncio.Semaphore(config["scheduling"]["max_concurrent_generations"])
        self.api_limiter = APIRateLimiter(config["rate_limits"]["anthropic_api"])
        # ... load profile, index, verifier, agents, budget ...

    async def run(self):
        await self._recover_incomplete()  # crash recovery
        while True:
            if self.state.get("paused"): await asyncio.sleep(60); continue
            if self._should_scrape(): await self._run_discovery("board_scrape")
            if self._should_research(): await self._run_discovery("market_research")
            await asyncio.sleep(60)

    async def _call_llm(self, agent, **kwargs):
        """All LLM calls route here. Handles rate limiting + retry."""
        for attempt in range(3):
            await self.api_limiter.acquire()
            try:
                result = await agent.call(**kwargs)
                self.budget.record(result.token_usage)
                return result
            except (RateLimitError, TimeoutError, APIError) as e:
                wait = (2 ** attempt) + random.uniform(0, 1)
                if attempt == 2: raise
                await asyncio.sleep(wait)
            finally:
                self.api_limiter.release()

    async def generate_application(self, match_result):
        async with self.task_semaphore:
            job = match_result.job
            jid = job.job_id

            # Budget check
            if not self.budget.can_afford(self.budget.estimate(job)): return

            # Resume loop
            resume = await self._resume_loop(match_result)
            self._checkpoint(jid, "resume", resume)

            # Cover letter loop
            cl = None
            if job.role.requires_cover_letter:
                cl = await self._cl_loop(match_result, resume)
                self._checkpoint(jid, "cover_letter", cl)

            # App questions
            aq = None
            if job.application_questions:
                aq = await self._aq_loop(match_result)
                self._checkpoint(jid, "app_questions", aq)

            # LLM verify
            verify = await self._llm_verify(resume, cl, aq, match_result)
            if verify["verdict"] == "FAIL":
                resume, cl = await self._revision_round(resume, cl, verify, match_result)

            # Posting still live?
            live, _, notes = await self.posting_checker.is_live(job.role.url)
            if not live:
                self._mark(jid, "posting_expired"); return

            # Already applied to similar role?
            dup, past, sim = self.app_dedup.check(job)
            if dup:
                self._queue_flag(match_result, "possible_duplicate",
                    f"Similar to: {past['title']} (sim={sim:.2f})"); return

            # Package + queue
            self._queue(match_result, resume, cl, aq, verify)

    async def _resume_loop(self, match_result):
        best, best_score = None, -1
        jid = match_result.job.job_id
        resume = await self._call_llm(self.resume_agent, mode="draft",
            profile=self.profile, job=match_result.job,
            tailoring_notes=match_result.tailoring_notes)

        for iteration in range(4):
            v = self.verifier.verify_resume(resume.resume_content, resume.profile_entries_used)
            resume.quality_score = v["quality_score"]

            # Per-iteration checkpoint (matches §6.1 diagram)
            self._checkpoint(jid, f"resume_iter_{iteration}", {
                "content": resume.resume_content,
                "entry_ids": resume.profile_entries_used,
                "verification": v,
                "quality_score": v["quality_score"]
            })

            if v["quality_score"] > best_score:
                best_score, best = v["quality_score"], resume
                best._verification = v
            if v["status"] == "PASS": break
            resume = await self._call_llm(self.resume_agent, mode="revise",
                previous=resume, issues=v["issues"])

        return best

    def _checkpoint(self, job_id, stage, data):
        os.makedirs(f"data/checkpoints/{job_id}", exist_ok=True)
        with open(f"data/checkpoints/{job_id}/{stage}.json", 'w') as f:
            json.dump({"stage": stage, "data": serialize(data), "ts": now_iso()}, f)

    async def _recover_incomplete(self):
        for jid in os.listdir("data/checkpoints"):
            if self.state["applications"].get(jid, {}).get("status") == "generating":
                cp = self._load_checkpoint(jid)
                if cp: await self._resume_from(jid, cp)
```

### 7.2 API Rate Limiter

```python
class APIRateLimiter:
    def __init__(self, config):
        self._semaphore = asyncio.Semaphore(config["concurrent_max"])
        self._rpm = config["requests_per_minute"]
        self._times = []

    async def acquire(self):
        await self._semaphore.acquire()
        now = time.monotonic()
        self._times = [t for t in self._times if now - t < 60]
        if len(self._times) >= self._rpm:
            await asyncio.sleep(60 - (now - self._times[0]))
        self._times.append(time.monotonic())

    def release(self):
        self._semaphore.release()
```

---

## 8. Review Interface

### Tech Stack

- **FastAPI** + **Jinja2** templates + **htmx** for interactivity
- **marked.js** for markdown preview
- **CodeMirror** (markdown mode) for inline editing

### Queue View (GET /)

```
┌────────────────────────────────────────────────────────────┐
│  Job Application Queue                    Budget: $14/$20  │
├────────────────────────────────────────────────────────────┤
│  🟢 Adaptive Bio • Senior Statistician     8.2  Feb 15    │
│     Strong fit — causal + clinical trials  [Review] [Skip] │
│                                                            │
│  🔵 Citadel • Quant Researcher             6.8  —         │
│     Good fit with gap: no finance exp      [Review] [Skip] │
│                                                            │
│  🟡 StartupXYZ • ML Engineer               5.1  —         │
│     MARGINAL — needs triage        [Approve gen] [Skip]    │
│                                                            │
│  🔴 Pfizer • Biostatistician               7.0  Feb 20    │
│     ⚠ needs_human_help                [Review+Edit] [Skip] │
└────────────────────────────────────────────────────────────┘
```

### Detail View (GET /application/{id})

```
┌────────────────────────┬───────────────────────────────────┐
│     JOB POSTING        │         RESUME (markdown preview) │
│  [scrollable]          │  Quality: 92/100 | Iters: 3       │
│                        │  [Edit] → CodeMirror overlay       │
│                        ├───────────────────────────────────┤
│                        │         COVER LETTER               │
│                        │  Voice: high | Quality: 88/100     │
│                        │  [Edit] → CodeMirror overlay       │
├────────────────────────┼───────────────────────────────────┤
│  MATCH ANALYSIS        │  APPLICATION QUESTIONS              │
│  Skills: 9 Exp: 8      │  Sponsorship: Yes ✅               │
│  Growth: 7 Feas: 6 ⚠   │  Why here: [editable] ⚠review     │
│  Strat: 8               │  Salary: $X-$Y ✅                  │
│  Gaps: [list]           │                                    │
├────────────────────────┴───────────────────────────────────┤
│  Cost: $1.82 | 7 calls | 34K tokens                        │
│  [✅ Approve] [✏️ Edit+Approve] [⏭ Skip ▼reason] [🔄 Regen] │
└────────────────────────────────────────────────────────────┘
```

**On Approve:** posting re-check (spinner) → dup check → if pass: render PDF/DOCX, open app URL, mark approved.

**Human Edit Policy:** When the user edits documents via CodeMirror, the edited version is NOT re-run through the Programmatic Verification Suite. The human is the final authority — their edits are trusted. The original quality_score is retained for logging purposes but marked as `pre_edit_score`. If the user wants to verify their edits, a manual "Re-verify" button runs the suite and shows results without blocking approval.

### History (GET /history) & Stats (GET /stats)

History: table with outcome dropdown per row. Filterable.
Stats: cards (total, rate, cost), charts (apps over time, score distribution, conversion funnel).

---

## 9. Resume Rendering Pipeline

The Resume Agent outputs markdown. Submission requires PDF or DOCX. Rendering is deterministic — no LLM involved.

```python
# rendering/renderer.py
from weasyprint import HTML
import markdown

class ResumeRenderer:
    def __init__(self, css_path):
        self.css = open(css_path).read()

    def to_pdf(self, md_content, output_path):
        html = markdown.markdown(md_content)
        HTML(string=f"<html><head><style>{self.css}</style></head><body>{html}</body></html>").write_pdf(output_path)

    def to_docx(self, md_content, output_path):
        # pandoc --from markdown --to docx --reference-doc=templates/resume_reference.docx -o output.docx
        ...
```

Templates in `rendering/templates/`: `resume.css`, `resume_reference.docx`, `cover_letter.css`, `cover_letter_reference.docx`. Candidate customizes these. Rendering is separate from content generation.

---

## 10. Cost Control & Token Budget

### Model Tiers

| Agent | Model | Rationale |
|---|---|---|
| Scout | Sonnet | Query construction |
| Match | Sonnet (Opus for MARGINAL) | Structured scoring |
| Resume | Opus | Core deliverable |
| Cover Letter | Opus | Voice + creativity |
| App Questions | Sonnet | Short answers |
| Verify | Opus | Adversarial review |
| Code layers | No LLM | Free |

### Per-Application Estimate

~$1.50 with CL, ~$0.75 without. App questions add ~$0.02.
10 apps/day: $7.50-$15. Worst case (max iterations): ~$25/day.

### Controls

```yaml
budget:
  daily_limit_usd: 20.00
  per_application_limit_usd: 5.00
  warning_threshold: 0.80
  hard_stop: true
```

---

## 11. Feedback Loop & Calibration (REVISED)

### 11.1 Outcome Tracking

Through dashboard History View. Status dropdown per application:
`no_response | rejection | phone_screen | interview | offer | withdrawn`

### 11.2 Simplified Calibration

**Problem with v2:** Tried to re-weight 5 dimensions + 3 thresholds from ~20 data points distributed across 3 buckets. That's noise-fitting.

**v3 approach:** Single-variable threshold adjustment. Don't re-weight dimensions until you have 100+ outcomes.

```python
def simple_recalibrate(outcomes, current_thresholds):
    """
    Phase 1 (< 50 outcomes): Only adjust the GOOD threshold.
    If GOOD-classified apps are converting well, leave it.
    If GOOD apps never convert but STRONG apps do, raise the threshold.
    If MARGINALs that the user approved convert, lower it.

    Phase 2 (50-100 outcomes): Also adjust STRONG and MARGINAL thresholds.

    Phase 3 (100+ outcomes): Re-weight dimension scores.
    """
    positive = {"phone_screen", "interview", "offer"}

    # Compute conversion rate by bucket
    buckets = {}
    for o in outcomes:
        b = o["classification"]
        buckets.setdefault(b, {"total": 0, "positive": 0})
        buckets[b]["total"] += 1
        if o["outcome"] in positive:
            buckets[b]["positive"] += 1

    total_outcomes = sum(b["total"] for b in buckets.values())

    if total_outcomes < 20:
        return {"action": "insufficient_data", "message": "Need 20+ outcomes to calibrate."}

    if total_outcomes < 50:
        # Phase 1: single threshold adjustment
        good_rate = buckets.get("GOOD", {}).get("positive", 0) / max(1, buckets.get("GOOD", {}).get("total", 1))
        strong_rate = buckets.get("STRONG", {}).get("positive", 0) / max(1, buckets.get("STRONG", {}).get("total", 1))

        adjustment = 0
        if good_rate < 0.05 and strong_rate > 0.10:
            adjustment = 0.5  # raise bar
        elif good_rate > 0.15:
            adjustment = -0.3  # lower bar (goods are converting well)

        return {
            "action": "threshold_adjust",
            "good_threshold": current_thresholds["good"] + adjustment,
            "analysis": f"STRONG rate: {strong_rate:.0%}, GOOD rate: {good_rate:.0%}. "
                        f"Adjusting GOOD threshold by {adjustment:+.1f}",
            "phase": 1
        }

    if total_outcomes < 100:
        # Phase 2: adjust all three thresholds
        # ... similar logic for STRONG and MARGINAL ...
        return {"action": "threshold_adjust", "phase": 2, ...}

    # Phase 3: dimension re-weighting (enough data)
    # Logistic regression: which dimensions predict positive outcomes?
    return {"action": "full_recalibrate", "phase": 3, ...}
```

---

## 12. Testing Strategy

### Test Fixtures

```
tests/
├── fixtures/
│   ├── profile_complete.json
│   ├── profile_sparse.json
│   ├── style_guide_sample.md
│   ├── job_postings/
│   │   ├── strong_match.json       # Score >= 7.5
│   │   ├── good_match.json         # Score 6.0-7.4
│   │   ├── marginal_match.json     # Score 4.5-5.9
│   │   ├── weak_match.json         # Score < 4.5
│   │   ├── no_visa.json            # Feasibility test
│   │   ├── overqualified.json      # Growth test
│   │   └── with_app_questions.json # App questions test
│   ├── resumes/
│   │   ├── good_resume.md          # Should PASS
│   │   ├── hallucinated.md         # Fabricated claims → FAIL
│   │   ├── ai_fingerprint.md       # AI tells → flags
│   │   └── inflated.md             # "led" when profile says "contributed" → Verify catch
│   └── cover_letters/
│       ├── good_cl.md
│       ├── generic_cl.md           # Transferable "why company" → FAIL
│       └── wrong_voice.md          # Style mismatch → Verify catch
├── test_claim_extractor.py         # NEW
├── test_source_mapper.py           # NEW
├── test_number_checker.py          # NEW (context-aware)
├── test_structural_detector.py     # NEW (spaCy-based)
├── test_blacklist.py               # Updated (context-dependent)
├── test_fact_checker_integration.py # End-to-end verification suite
├── test_dedup.py
├── test_app_dedup.py               # NEW
├── test_posting_checker.py         # NEW
├── test_match_scoring.py
├── test_rendering.py
├── test_budget.py
├── test_rate_limiter.py            # NEW
└── results/                        # Prompt regression results
```

### Key Test Cases

**Claim Extractor:**
- Bullet points extracted as individual claims
- Section headers skipped
- Structural lines (company|title|date) tagged correctly
- Cover letter sentences split properly

**Source Mapper:**
- Direct match: profile accomplishment → resume bullet (score > 0.8)
- Paraphrase: same meaning different words (score 0.4-0.8)
- Ungrounded: fabricated claim (score < 0.4 → HIGH issue)
- Education and publication matching works

**Number Checker:**
- Years (2022, 2024) → exempt_date
- "5+ years of experience" → exempt_structural
- "3 publications" when profile has 3 → exempt_derived
- "40%" not in profile → UNVERIFIED_METRIC (HIGH)
- Page numbers → exempt

**Structural Detector:**
- 4 bullets starting with VBD+NN → PARALLEL_BULLETS
- 3 bullets → no flag (within limit)
- "X, Y, and Z" appearing 3 times → TRICOLON_EXCESS
- 3 paragraphs of identical length → PARAGRAPH_BALANCE

**Blacklist:**
- "robust regression" → no flag (context exception)
- "robust approach to leadership" → flag (no statistical context)
- All phrase matches caught

**Posting Checker:**
- 200 with live content → True
- 404 → False
- 200 with "this job is no longer available" → False

**Application Dedup:**
- Same company + "Sr. Statistician" vs "Senior Statistician" → duplicate
- Same company + "Statistician" vs "ML Engineer" → not duplicate

### Prompt Regression

Each prompt file has:
```
# VERSION: 1.2.0
# LAST_TESTED: 2026-02-09
# TEST_RESULTS: tests/results/resume_agent_v1.2.0.json
```

Process: generate on all fixtures → run verification suite → compare quality_scores to baseline → human sample review.

---

## 13. File Structure

```
job-agent/
├── config/
│   ├── config.yaml
│   ├── rate_limits.yaml
│   ├── budget.yaml
│   ├── ai_blacklist.yaml
│   ├── notifications.yaml
│   ├── scoring_weights.yaml       # auto-calibrated
│   └── watchlist.yaml
├── profile/
│   ├── profile.json
│   └── style_guide.md
├── prompts/
│   ├── scout_agent.md
│   ├── match_agent.md
│   ├── resume_agent.md
│   ├── cover_letter_agent.md
│   ├── app_questions_agent.md     # NEW
│   └── verify_agent.md
├── agents/
│   ├── orchestrator.py
│   ├── scout.py
│   ├── match.py
│   ├── resume.py
│   ├── cover_letter.py
│   ├── app_questions.py           # NEW
│   ├── verify.py
│   ├── queue.py                   # deterministic code
│   ├── dedup.py
│   └── rate_limiter.py            # NEW
├── verification/
│   ├── runner.py                  # unified orchestration
│   ├── claim_extractor.py         # NEW
│   ├── source_mapper.py           # NEW (replaces LLM source maps)
│   ├── number_checker.py          # REVISED (context-aware)
│   ├── blacklist_scanner.py       # REVISED (context-dependent)
│   ├── structural_detector.py     # NEW (spaCy NLP)
│   ├── posting_checker.py         # NEW
│   ├── application_dedup.py       # NEW
│   └── profile_index.py           # NEW
├── rendering/
│   ├── renderer.py
│   └── templates/
│       ├── resume.css
│       ├── resume_reference.docx
│       ├── cover_letter.css
│       └── cover_letter_reference.docx
├── dashboard/
│   ├── app.py                     # FastAPI
│   ├── templates/                 # Jinja2
│   │   ├── queue.html
│   │   ├── detail.html
│   │   ├── history.html
│   │   └── stats.html
│   └── static/
│       ├── htmx.min.js
│       ├── marked.min.js
│       └── codemirror/
├── calibration/
│   ├── recalibrate.py             # REVISED (phased approach)
│   └── outcome_analyzer.py
├── data/
│   ├── state.json
│   ├── seen_jobs.db
│   ├── checkpoints/               # NEW (crash recovery)
│   │   └── {job_id}/
│   │       ├── resume.json
│   │       ├── cover_letter.json
│   │       └── app_questions.json
│   └── queue/
│       └── {queue_entry_id}.json
├── output/
│   ├── resumes/
│   ├── cover_letters/
│   └── logs/
├── tests/
│   ├── fixtures/
│   ├── test_claim_extractor.py
│   ├── test_source_mapper.py
│   ├── test_number_checker.py
│   ├── test_structural_detector.py
│   ├── test_blacklist.py
│   ├── test_fact_checker_integration.py
│   ├── test_dedup.py
│   ├── test_app_dedup.py
│   ├── test_posting_checker.py
│   ├── test_match_scoring.py
│   ├── test_rendering.py
│   ├── test_budget.py
│   ├── test_rate_limiter.py
│   └── results/
├── requirements.txt
└── README.md
```

---

## 14. Configuration

```yaml
# config/config.yaml

scheduling:
  board_scrape:
    interval_hours: 6
    jitter_minutes: 30
  market_research:
    interval_hours: 24
    preferred_time: "09:00"
  max_concurrent_generations: 3
  max_applications_per_day: 10

generation:
  max_programmatic_iterations: 4
  max_llm_verify_rejections: 2
  resume_format: "markdown"
  cover_letter_max_words: 400
  source_mapper_resume_threshold: 0.30
  source_mapper_cover_letter_threshold: 0.25

model_tiers:
  scout: "claude-sonnet-4-5-20250929"
  match_default: "claude-sonnet-4-5-20250929"
  match_marginal: "claude-opus-4-6"
  resume: "claude-opus-4-6"
  cover_letter: "claude-opus-4-6"
  app_questions: "claude-sonnet-4-5-20250929"
  verify: "claude-opus-4-6"

dashboard:
  host: "127.0.0.1"
  port: 8080

logging:
  level: "INFO"
  save_all_iterations: true
  log_token_usage: true

cleanup:
  checkpoint_retention: "until_queued"  # delete checkpoints after entry is approved/skipped
  log_retention_days: 30               # delete logs older than 30 days
  queue_retention_days: 90             # archive queue entries older than 90 days
  run_cleanup_on_startup: true
```

---

## Appendix A: Dependencies

```
# requirements.txt
anthropic
fastapi
uvicorn
jinja2
aiohttp
pyyaml
spacy
sentence-transformers
weasyprint
python-markdown
numpy
```

Plus: `python -m spacy download en_core_web_sm`

## Appendix B: Known Limitations

1. **API costs.** SerpAPI ~$50-100/month + LLM ~$200-450/month at 10 apps/day.
2. **Greenhouse/Lever APIs undocumented.** May change. Build resilient parsers.
3. **AI fingerprint detection is an arms race.** Update blacklist + structural rules regularly.
4. **Source Mapper uses SequenceMatcher.** Good for exact/near matches, weaker for deep paraphrases. Thresholds are configurable (resume: 0.30, CL: 0.25). Tune empirically against test fixtures. Could upgrade to embedding similarity if false positives persist, at cost of adding inference to the programmatic layer.
5. **Posting checker can't detect all expirations.** Some sites return 200 with generic pages. Maintain the expired_signals list.
6. **Voice matching is inherently limited.** The human review step is the real quality gate.
7. **Single-user tool.** Profile, Style Guide, and calibrated weights are user-specific.
8. **spaCy en_core_web_sm is the minimum.** Upgrade to en_core_web_md/lg for better POS accuracy.
9. **Two dedup systems serve different purposes.** The Dedup Engine (discovery time, embedding-based) answers "is this the same job posting?" — catches cross-platform reposts. The Application Dedup (submission time, title-based) answers "have we already applied to a similar role at this company?" — catches refreshed/reposted roles. Different questions require different matching strategies.
10. **Disk usage grows over time.** Log files, checkpoints, and queue entries accumulate. The cleanup config (§14) handles retention, but monitor disk usage monthly.

## Appendix C: Migration from v2

- Remove source map generation from Resume Agent and Cover Letter Agent prompts
- Add Claim Extractor, Source Mapper, Number Checker (revised), Structural Detector to verification/
- Add Application Questions Agent + prompt
- Add posting_checker.py and application_dedup.py
- Add checkpoints/ directory and checkpoint logic to orchestrator
- Replace self_score tracking with quality_score from VerificationRunner
- Add API rate limiter separate from task semaphore
- Add retry logic to all LLM call sites
- Update blacklist YAML with context_dependent section
- Add application_question_answers to profile schema
- Update dashboard to show app questions, use htmx + CodeMirror
- Replace recalibrate.py with phased approach
- Add new test files for new components

### v3.1 updates (within v3)

- Source Mapper threshold is now configurable in config.yaml (resume: 0.30, CL: 0.25)
- CL Source Mapper skips company-claim sentences (`_is_company_claim` heuristic)
- `_call_llm` uses try/finally for semaphore release (fixes resource leak)
- Per-iteration checkpointing inside `_resume_loop` (matches §6.1 diagram)
- All agent prompts inlined (no more "see v2" back-references)
- Style Guide schema inlined
- Human-edit bypass policy documented (edits trusted, verification optional)
- Cleanup/retention config added (checkpoints, logs, queue entries)
- Dedup design rationale documented (discovery vs submission dedup serve different purposes)
