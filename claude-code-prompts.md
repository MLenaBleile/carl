# Job Application Agent: Claude Code Implementation Prompts

## How to Use This Document

This is a sequenced set of prompts for Claude Code. Execute them **in order** — each step builds on the previous one. After each step, run the tests before proceeding.

**Principles:**
- Each prompt produces testable, working code
- Tests come WITH the code, not after
- Fix review findings (from v3.1 review) during implementation, not as a separate pass
- Pure Python code (verification suite, orchestrator) is built before LLM-dependent code (agents)
- The spec file (`job-agent-spec-v3.md`) should be in the repo root for reference

**Prerequisites:**
- Python 3.11+
- The spec file at `./job-agent-spec-v3.md`

---

## PHASE 1: Foundation (no LLM calls, no external APIs)

### Prompt 1: Project Scaffolding + Profile Index + Test Fixtures

```
I'm building a job application agent system. The full specification is in ./job-agent-spec-v3.md — read it first.

Create the project scaffolding and foundational data layer:

1. **Project structure**: Create all directories matching §13 of the spec. Add __init__.py files to make them proper Python packages. Create requirements.txt per Appendix A.

2. **Config files**: Create config/config.yaml, config/ai_blacklist.yaml, config/budget.yaml, and config/rate_limits.yaml per §14. For ai_blacklist.yaml, include the full blacklist from §5.5 including the context_dependent section with "robust" exceptions.

3. **Profile schema + ProfileIndex**: Implement verification/profile_index.py per §2 and §5. ProfileIndex takes a profile dict and builds:
   - experience_text: id → concatenated lowercase text
   - legitimate_numbers: all numbers extracted from all string fields (walk the entire dict recursively)
   - dates: all date components (years, months) from experience and education
   - titles, orgs: id → string maps
   - skills_flat: flattened skill dict with proficiency levels
   - pub_titles: id → title
   - derived_counts: computed counts (num_publications, num_presentations, etc.)

   IMPORTANT: The _extract_all_numbers method must recursively walk the entire profile JSON and extract numbers from every string value. The _flatten_skills method should produce a dict mapping skill_name → proficiency_level.

4. **Test fixtures**: Create tests/fixtures/ with:
   - profile_complete.json: A realistic, populated profile for a PhD biostatistician (based on the profile schema in §2). Include 4-5 experience entries with accomplishments and responsibilities, 3-4 publications, education, skills at various proficiency levels, application_question_answers section. Use realistic but fictional data. Every field should be populated.
   - profile_sparse.json: Same schema but only name, 1 experience entry, 1 education entry. All optional fields empty/null.
   - style_guide_sample.md: A filled-in Style Guide matching the schema in §3.

5. **Tests**: Create tests/test_profile_index.py:
   - test_experience_text_built_correctly: verify all experience entries indexed
   - test_legitimate_numbers_extracted: verify numbers from accomplishments (e.g., "40%" in an accomplishment) appear in legitimate_numbers
   - test_dates_extracted: verify years from start_date/end_date/year_completed
   - test_derived_counts: verify num_publications matches actual count
   - test_skills_flattened: verify expert/proficient/familiar levels preserved
   - test_sparse_profile_doesnt_crash: verify ProfileIndex works with profile_sparse.json

Run pytest and confirm all tests pass.
```

### Prompt 2: Claim Extractor

```
Read §5.1 of ./job-agent-spec-v3.md for the ClaimExtractor spec.

Implement verification/claim_extractor.py:

The ClaimExtractor extracts claim units from markdown resumes and cover letters.

Key design decisions:
- Each bullet point = one claim unit. Do NOT decompose sentences into atomic facts.
- Section headers (lines starting with #) are skipped — they're not claims.
- Lines within experience/education/publications/skills sections that aren't bullets are classified as either "structural" (company|title|date headers) or "content" (actual claims).
- Cover letter extraction splits on sentence boundaries.

For the _is_structural heuristic, the spec has a known issue: lines with <= 4 words and no punctuation get tagged structural, but legitimate claims like "Published in Nature Communications" (4 words) get misclassified. Fix this by:
- Reducing the short-line threshold to <= 3 words (most structural headers like "Sanofi" or "2022-2024" are 1-2 words with a separator)
- Adding positive structural indicators: contains pipe (|) or em-dash (— or –), OR is a date range pattern, OR has <= 3 words with no punctuation

Also create tests/fixtures/resumes/ with:
- good_resume.md: A realistic tailored resume in markdown for the profile_complete.json person applying to a biostatistician role. Include proper sections (Experience, Education, Skills, Publications), bullets under each experience entry, company|title|date structural lines. ~40 lines.
- hallucinated.md: Same structure but with 3 fabricated claims not in the profile (e.g., an invented metric "reduced analysis time by 60%", a tool not in the profile, a role title that doesn't match).
- ai_fingerprint.md: Same structure but with AI tells — 5 consecutive bullets starting with "Spearheaded...", "Leveraged...", "Championed...", plus "Moreover" and "Furthermore" connectors, and two "X, Y, and Z" tricolons.

Create tests/test_claim_extractor.py:
- test_bullets_extracted: good_resume.md should have >= 10 bullet-type claims
- test_headers_skipped: no claims with type == "section_header"
- test_structural_detected: company|title|date lines tagged structural
- test_content_detected: actual accomplishment lines tagged bullet or content
- test_short_content_not_misclassified: "Published in Nature Communications" (if present) should be content, not structural
- test_cover_letter_sentences: a 5-sentence paragraph should produce 5 claim units
- test_empty_input: empty string returns empty list
- test_no_section_context: bullets before any header have section=None

Run pytest tests/test_claim_extractor.py and confirm all pass.
```

### Prompt 3: Source Mapper

```
Read §5.2 of ./job-agent-spec-v3.md for the SourceMapper spec.

Implement verification/source_mapper.py:

The SourceMapper matches claim units from the ClaimExtractor against the ProfileIndex to find the best source for each claim. This is the KEY v3 change — source maps are built by code, not by the LLM.

Design from spec + v3.1 review fixes:
- Thresholds are CONFIGURABLE: resume default 0.30, cover letter default 0.25. Read from config dict, not hardcoded.
- Uses difflib.SequenceMatcher for similarity scoring.
- For cover letters: skip pure company-claim sentences via _is_company_claim heuristic. This checks for company signals ("your ", "the company", "the team", "the role", "this position") WITHOUT candidate signals (" i ", "i've", "i'd", " my ", " we "). Mixed sentences (both signals) are NOT skipped — they contain candidate claims that need verification.
- The claimed_entry_ids from the LLM are used to PRIORITIZE search order, not to blindly trust. Search priority entries first, then all entries.
- _find_best_match searches: experience accomplishments, experience responsibilities, publication titles, education entries. Returns the best match with score, entry_id, matched_field, matched_text.
- _match_structural verifies company names and job titles against ProfileIndex.

Create tests/test_source_mapper.py using profile_complete.json and good_resume.md:
- test_direct_match: a bullet that closely mirrors a profile accomplishment → status "matched", score > 0.5
- test_paraphrase_match: a bullet that rephrases a profile accomplishment → status "matched", score 0.25-0.60
- test_fabricated_claim_flagged: a bullet not in the profile at all → status "unmatched", issue with severity HIGH
- test_structural_match: company name line → matched structural
- test_education_match: education claim matched to edu entry
- test_publication_match: publication reference matched to pub entry
- test_cover_letter_company_claim_skipped: pure company sentence → status "company_claim_skipped"
- test_cover_letter_mixed_sentence_not_skipped: sentence with both "your team" and "I developed" → NOT skipped, goes through matching
- test_threshold_configurable: passing different config thresholds changes match/unmatch boundary
- test_empty_claims: empty list returns empty results

Run pytest tests/test_source_mapper.py and confirm all pass.
```

### Prompt 4: Number Checker

```
Read §5.3 of ./job-agent-spec-v3.md for the NumberChecker spec.

Implement verification/number_checker.py:

The NumberChecker finds all numbers in generated documents and classifies them. Only numbers that need verification AND aren't in the profile get flagged.

Classification categories:
- exempt_date: 4-digit years (1950-2030), date components from profile, numbers near month names
- exempt_derived: "N publications" where N matches profile count, same for presentations
- exempt_structural: "N+ years of experience/expertise", page numbers
- needs_verification: everything else — must be in profile's legitimate_numbers or derived_counts

Context-aware: uses a 60-character window around each number to determine classification.

The regex is: r'\b(\d+(?:\.\d+)?%?)\b'

Handle edge cases:
- "40%" should be found as "40%"
- "3.5" should be found as "3.5"
- Numbers inside URLs or email addresses should ideally be skipped (but this is a nice-to-have, not critical)

Create tests/test_number_checker.py using profile_complete.json:
- test_year_exempt: "2022" in resume → no flag
- test_date_from_profile_exempt: a year that appears in profile experience dates → no flag
- test_derived_count_exempt: "3 publications" when profile has 3 pubs → no flag
- test_experience_years_exempt: "5+ years of experience" → no flag
- test_unverified_metric_flagged: "reduced costs by 40%" where 40 is NOT in profile → HIGH flag
- test_number_in_profile_passes: a number that IS in the profile (e.g., from an accomplishment) → no flag
- test_percentage_found: "improved accuracy by 15.5%" → number "15.5%" extracted
- test_no_numbers: text with no numbers → empty issues list

Run pytest tests/test_number_checker.py and confirm all pass.
```

### Prompt 5: Blacklist Scanner

```
Read §5.5 of ./job-agent-spec-v3.md for the BlacklistScanner spec.

Implement verification/blacklist_scanner.py:

The BlacklistScanner checks for AI-telltale vocabulary and phrases.

Key features:
- Phrases (HIGH severity): exact substring match, case-insensitive. E.g., "I am writing to express my interest"
- Words (MEDIUM severity): word-boundary match (\b), case-insensitive. E.g., "leverage", "utilize"
- Context-dependent exceptions: for words like "robust", check an 80-character window around each occurrence. If any exception term (e.g., "regression", "estimator", "statistical") appears in the window, skip the flag. If no exception term found, flag it.

Load config from config/ai_blacklist.yaml (created in Prompt 1).

Handle the edge case: a word that appears multiple times in the document, some occurrences with context exceptions and some without. Each occurrence should be checked independently — flag only the ones without context.

Create tests/test_blacklist.py:
- test_phrase_detected: "I am writing to express my interest" → HIGH flag
- test_phrase_case_insensitive: "i am writing to Express My Interest" → still flagged
- test_word_detected: "leveraged the platform" → MEDIUM flag for "leverage" (wait — should "leveraged" match "leverage"? Use word boundary regex carefully. The blacklist contains "leverage" — should it match "leveraged"? Spec says word boundary match. \bleverage\b would NOT match "leveraged". You need to decide: either put both forms in the blacklist, or use a stem-matching approach. DECISION: add common inflected forms to the blacklist in the YAML, or match on r'\bleverage[ds]?\b'. Go with the regex approach — for each blacklist word, match the word plus common suffixes [sd]?.)
- test_robust_with_stats_context_exempt: "robust regression methods" → no flag
- test_robust_without_context_flagged: "a robust approach to leadership" → MEDIUM flag
- test_robust_multiple_occurrences_mixed: text with "robust regression" AND "robust approach" → only 1 flag
- test_clean_text: professional text with no blacklisted terms → empty issues
- test_all_phrases_caught: iterate through all phrases in YAML, verify each is caught

Run pytest tests/test_blacklist.py and confirm all pass.
```

### Prompt 6: Structural AI Detector

```
Read §5.4 of ./job-agent-spec-v3.md for the StructuralAIDetector spec.

Implement verification/structural_detector.py:

This uses spaCy for NLP-based detection of structural patterns that signal AI-generated text. First make sure spacy and en_core_web_sm are installed (pip install spacy && python -m spacy download en_core_web_sm).

Load the spaCy model ONCE at module level: nlp = spacy.load("en_core_web_sm")

Checks:
1. **Parallel bullets** (resume only): Extract all bullets, get POS tags for first 4 tokens of each, find consecutive runs with identical patterns. Flag if run > max_consecutive_parallel_bullets (default 3).

   v3.1 review fix: bullets should be partitioned by section BEFORE checking runs. A section break (non-bullet line, or a header) resets the run counter. Currently the spec extracts all bullets globally — fix this by splitting on section headers first, then checking runs within each section independently.

2. **Tricolons**: Count "X, Y, and Z" patterns. v3.1 review noted the regex r'(\w+),\s+(\w+),\s+and\s+(\w+)' only matches single-word items. Use a broader pattern: r'([^,]+),\s+([^,]+),\s+and\s+([^,.]+)' to catch multi-word tricolons like "statistical modeling, causal inference, and reinforcement learning". BUT — also reconsider severity. In resumes, listing 3 skills is natural. Keep as LOW severity.

3. **Connector excess**: Count connector words (Moreover, Furthermore, Additionally, etc.) via case-insensitive word boundary regex.

4. **Paragraph balance**: Split on double newlines (excluding headers), compute word count per paragraph, calculate coefficient of variation. CV < 0.15 → flag.

5. **Sentence length uniformity**: Use spaCy's sentence segmentation. Compute token count per sentence, calculate CV. CV < 0.20 → flag. Require minimum 5 sentences.

Config comes from config/ai_blacklist.yaml under structural_rules.

Create the ai_fingerprint.md test fixture (if not already created in Prompt 2) with deliberate AI patterns.

Create tests/test_structural_detector.py:
- test_parallel_bullets_detected: 5 bullets all starting with VBD+NN pattern → MEDIUM flag
- test_parallel_bullets_within_threshold: 3 bullets with same pattern (at limit) → no flag
- test_parallel_bullets_section_boundary_resets: 3 same-pattern bullets in section A, 3 in section B → no flag (run resets at section break)
- test_tricolons_detected: 3 "X, Y, and Z" patterns → LOW flag (max is 1)
- test_multiword_tricolons_detected: "statistical modeling, causal inference, and reinforcement learning" counted
- test_connector_excess: 4 "Moreover"/"Furthermore" → MEDIUM flag (max 2)
- test_paragraph_balance_flagged: 3 paragraphs of exactly 50 words each → LOW flag
- test_natural_paragraph_variation: paragraphs of 30, 80, 45 words → no flag
- test_sentence_uniformity_flagged: 6 sentences all 15 tokens → LOW flag
- test_short_content_skipped: 2 sentences → no sentence uniformity check

Run pytest tests/test_structural_detector.py and confirm all pass.
```

### Prompt 7: Skill Level Checker + Verification Runner

```
Read §5.7 of ./job-agent-spec-v3.md for the VerificationRunner.

There is a gap identified in the v3.1 review: the Verify Agent prompt says "No skills above proficiency level" was already checked by code, but no code does this. Fix it.

1. **Create verification/skill_checker.py**:

   SkillLevelChecker takes a ProfileIndex and checks whether skills claimed in a resume exceed the proficiency level in the profile.

   Logic:
   - Extract skill mentions from resume text (look for skills that appear in profile.skills_flat)
   - For each mentioned skill, check if the resume context implies a higher level than the profile states:
     - "expert in X" or "advanced X" or "deep expertise in X" when profile says "familiar" → HIGH flag
     - "proficient in X" when profile says "familiar" → MEDIUM flag
     - Exact match or understatement → no flag
   - Context detection: check 10-word window around each skill mention for level-indicating words:
     - Expert indicators: "expert", "advanced", "deep expertise", "extensive experience", "mastery"
     - Proficient indicators: "proficient", "experienced", "strong", "solid"
     - Familiar indicators: "familiar", "exposure", "basic", "some experience"
   - If no level indicator is found near the skill mention, skip it (no flag — the skill is just listed).

   Create tests/test_skill_checker.py:
   - test_expert_claim_on_familiar_skill: "Expert in Julia" when profile has Julia as familiar → HIGH
   - test_proficient_claim_matches: "proficient in R" when profile has R as proficient → no flag
   - test_skill_listed_without_level: "R, Python, Julia" with no level words → no flag
   - test_skill_not_in_profile: "experienced in Rust" when Rust not in profile → no flag (this is a Source Mapper concern, not skill level)

2. **Create verification/runner.py**: The unified VerificationRunner that orchestrates all checks.

   Methods:
   - verify_resume(content, claimed_ids) → runs ClaimExtractor, SourceMapper, NumberChecker, BlacklistScanner, StructuralAIDetector, SkillLevelChecker. Returns dict with status, issues, source_map, quality_score, high/medium/low counts.
   - verify_cover_letter(content, claimed_ids, company_facts, job_text) → same pipeline adapted for CL (sentence extraction, company-claim skipping, company fact verification).
   - verify_app_questions(answers, profile) → simplified verification for app question answers: check each answer against profile for grounding, run blacklist scanner, skip structural detection. Flag answers with source="profile_derived" that can't be matched to profile entries. (This addresses the v3.1 review finding that verify_app_questions was missing.)
   - _score(issues) → quality score: 100 minus (HIGH×15 + MEDIUM×5 + LOW×1), floor 0.

   Create tests/test_fact_checker_integration.py:
   - test_good_resume_passes: good_resume.md against profile_complete.json → status PASS, quality_score >= 80
   - test_hallucinated_resume_fails: hallucinated.md → status FAIL, has UNGROUNDED_CLAIM issues
   - test_ai_fingerprint_detected: ai_fingerprint.md → has PARALLEL_BULLETS and AI_VOCABULARY issues
   - test_cover_letter_verification: a simple CL → runs without error, returns valid structure
   - test_app_questions_verification: simple Q&A set → runs, flags ungrounded answers
   - test_quality_score_math: 2 HIGH + 3 MEDIUM + 1 LOW = 100 - 30 - 15 - 1 = 54

Run pytest tests/ and confirm ALL tests from prompts 1-7 pass.
```

### Prompt 8: Posting Checker + Dedup Engines

```
Read §5.6 of ./job-agent-spec-v3.md.

1. **Implement verification/posting_checker.py**:
   PostingChecker.is_live(url) → async method that:
   - Makes GET request with 10-second timeout
   - Checks status code (404/410 → dead, non-200 → dead)
   - Scans response body for expired signals: "this job is no longer available", "this position has been filled", "this listing has expired", "no longer accepting applications", "this job has been closed", "position closed"
   - Returns tuple: (is_live: bool, status_code: int, notes: str)
   - Handles connection errors, timeouts gracefully
   - v3.1 review fix: define timeout behavior explicitly. On timeout: return (False, 0, "Connection timed out — treat as potentially expired")

2. **Implement agents/dedup.py**:
   JobDeduplicator for discovery-time dedup. Uses sentence-transformers for embedding similarity.
   - add_seen(job) → adds to seen set
   - is_duplicate(job) → checks URL exact match first, then embedding similarity on title+company+description if URLs differ. Threshold 0.90.
   - Uses a SQLite database (data/seen_jobs.db) for persistence.

3. **Implement verification/application_dedup.py**:
   ApplicationDeduplicator for submission-time dedup. Uses SequenceMatcher on company name + title.
   - check(job, application_history) → returns (is_dup, past_app, similarity)
   - Company similarity threshold: 0.80
   - Title similarity threshold: 0.75
   - Skip past applications with status "skipped" or "error"

4. **Tests**:
   tests/test_posting_checker.py (use unittest.mock to mock aiohttp):
   - test_live_posting: mock 200 response with normal content → (True, 200, "Live")
   - test_404: mock 404 → (False, 404, ...)
   - test_expired_signal: mock 200 with "this job is no longer available" in body → (False, 200, ...)
   - test_timeout: mock timeout → (False, 0, "Connection timed out...")

   tests/test_dedup.py:
   - test_exact_url_duplicate
   - test_different_url_same_job (high embedding similarity)
   - test_different_jobs_not_duplicate

   tests/test_app_dedup.py:
   - test_same_company_similar_title: "Sr. Statistician" vs "Senior Statistician" at same company → duplicate
   - test_same_company_different_role: "Statistician" vs "ML Engineer" → not duplicate
   - test_different_company: same title at different companies → not duplicate
   - test_skipped_apps_ignored: past app with status "skipped" shouldn't trigger dup

Run pytest tests/ and confirm all pass.
```

---

## PHASE 2: Infrastructure (rate limiting, budget, state, rendering)

### Prompt 9: Rate Limiter + Budget Manager + Token Tracking

```
Read §7.2 and §10 of ./job-agent-spec-v3.md.

1. **Implement agents/rate_limiter.py**:
   APIRateLimiter with:
   - Async semaphore for max concurrent API calls
   - Per-minute rate limiting with sliding window
   - acquire() → async, blocks until a slot is available
   - release() → frees the semaphore
   Thread-safe (asyncio-based).

2. **Implement agents/budget.py** (new file, not in spec file structure but needed):
   TokenBudget with:
   - Load config from config/budget.yaml
   - estimate(job) → estimated cost based on whether job needs CL and app questions
   - can_afford(estimate) → checks against daily limit and per-application limit
   - record(token_usage) → tracks tokens and computes cost. Use approximate pricing: Opus input $15/MTok, output $75/MTok; Sonnet input $3/MTok, output $15/MTok.
   - get_run_cost() → returns cost of current application
   - get_daily_spend() → returns total spend today
   - reset_daily() → called when day rolls over

3. **Tests**:
   tests/test_rate_limiter.py:
   - test_semaphore_limits_concurrency: launch 10 concurrent acquires with max_concurrent=3, verify max 3 run simultaneously
   - test_rpm_limiting: verify that requests_per_minute is enforced (use mock time)

   tests/test_budget.py:
   - test_estimate_with_cover_letter: should be ~$1.50
   - test_estimate_without_cover_letter: should be ~$0.75
   - test_can_afford_within_budget: returns True
   - test_can_afford_over_daily_limit: returns False after spending too much
   - test_record_accumulates: multiple records sum correctly
   - test_daily_reset: spend resets to 0

Run pytest tests/ and confirm all pass.
```

### Prompt 10: State Manager + Checkpoint System

```
Read §7.1 and §7.3 of ./job-agent-spec-v3.md.

1. **Implement agents/state.py** (new file):
   StateManager handles persistent state in data/state.json:
   - load() → reads from disk, returns default state if file doesn't exist
   - save() → writes to disk (atomic write via temp file + rename)
   - Default state structure per §7.3 of spec
   - update_application(job_id, **fields) → update application entry
   - get_application(job_id) → returns application dict or None
   - add_to_queue(package) → appends to queue list
   - get_queue() → returns pending queue entries sorted by deadline-first-then-score
   - record_error(agent_name) → increments error count, checks circuit breaker (5 failures → paused)

2. **Implement agents/checkpoint.py** (new file):
   CheckpointManager handles crash recovery:
   - save(job_id, stage, data) → writes to data/checkpoints/{job_id}/{stage}.json
   - load_latest(job_id) → reads the most recent checkpoint file for a job
   - list_incomplete() → scans checkpoint dir for jobs that have checkpoints but state shows "generating"
   - cleanup(job_id) → removes all checkpoints for a completed job
   - cleanup_old(retention_policy) → implements the cleanup config from §14

3. **Tests**:
   tests/test_state.py:
   - test_load_creates_default: when no file exists, returns valid default state
   - test_save_and_reload: save state, reload, verify identical
   - test_update_application: update fields, verify persisted
   - test_queue_sorting: entries with deadlines sort before entries without; within same deadline status, higher scores first
   - test_circuit_breaker: 5 errors → state.paused = True

   tests/test_checkpoint.py:
   - test_save_and_load: save checkpoint, load it back
   - test_load_latest: save 3 checkpoints for same job, load_latest returns the last one
   - test_list_incomplete: create checkpoints + state with "generating" status, verify listed
   - test_cleanup: cleanup removes checkpoint directory
   - test_atomic_write: verify save uses temp file (check implementation)

Run pytest tests/ and confirm all pass.
```

### Prompt 11: Resume Renderer + Queue Agent

```
Read §9 and §4.7 of ./job-agent-spec-v3.md.

1. **Implement rendering/renderer.py**:
   ResumeRenderer:
   - to_pdf(md_content, output_path) → converts markdown to PDF via WeasyPrint
   - to_docx(md_content, output_path) → converts markdown to DOCX via subprocess call to pandoc with reference doc
   - to_html(md_content) → intermediate step, returns HTML string
   Uses rendering/templates/resume.css for PDF styling.

   Create rendering/templates/resume.css with clean, professional, ATS-friendly styling:
   - Simple fonts (system sans-serif stack)
   - Clean spacing
   - No colors except black
   - Proper heading hierarchy

   CoverLetterRenderer: same but with cover_letter.css.

2. **Implement agents/queue.py**:
   The Queue Agent is deterministic code. Functions:
   - package_for_review(job, match_result, resume, cover_letter, app_questions, verification, cost_summary) → returns the queue package dict per §4.7
   - generate_one_liner(match_result) → produces the queue card summary line
   - sort_queue(entries) → deadline first, then score descending

3. **Tests**:
   tests/test_rendering.py:
   - test_markdown_to_html: verify markdown converts to valid HTML
   - test_pdf_generation: generate PDF from good_resume.md, verify file exists and is > 0 bytes
   - test_css_applied: verify the CSS file is referenced in the HTML

   tests/test_queue.py:
   - test_package_structure: verify all required keys present
   - test_sort_deadline_first: entry with deadline sorts before entry without
   - test_sort_score_within_deadline: same deadline, higher score first
   - test_one_liner_generated: verify non-empty summary

Run pytest tests/ and confirm all pass.
```

---

## PHASE 3: LLM Agent Wrappers

### Prompt 12: Base Agent Class + LLM Client

```
Read §4 and §7.1 of ./job-agent-spec-v3.md.

Create the base agent infrastructure that all LLM agents inherit from.

1. **Implement agents/base.py**:
   BaseAgent abstract class:
   - __init__(self, prompt_path, model, config) → loads system prompt from prompts/{name}.md
   - async call(self, **kwargs) → abstract method
   - _build_messages(self, **kwargs) → constructs the messages list with system prompt + user content
   - _parse_json_response(self, text) → extracts JSON from LLM response (handles markdown code fences, partial JSON)
   - model: string (from config)
   - prompt_version: extracted from VERSION comment in prompt file

2. **Implement agents/llm_client.py**:
   LLMClient wraps the Anthropic API:
   - __init__(api_key, rate_limiter, budget)
   - async complete(model, messages, max_tokens) → calls anthropic API, returns response + token_usage
   - Handles: retry with exponential backoff (3 attempts), rate limiting (via APIRateLimiter), budget recording
   - The try/finally pattern from the v3.1 fix: acquire() before try, release() in finally
   - Returns a structured result with: content (str), token_usage (dict with input_tokens, output_tokens, model)

3. **Create all prompt files** in prompts/:
   - prompts/scout_agent.md: Full Scout Agent prompt from §4.1
   - prompts/match_agent.md: Full Match Agent prompt from §4.2
   - prompts/resume_agent.md: Full Resume Agent prompt from §4.3
   - prompts/cover_letter_agent.md: Full Cover Letter Agent prompt from §4.4
   - prompts/app_questions_agent.md: Full App Questions Agent prompt from §4.5
   - prompts/verify_agent.md: Full Verify Agent prompt from §4.6 — but REMOVE "No skills above proficiency level" from the "What's Already Been Checked" list (since SkillLevelChecker now handles it, per v3.1 review fix)

   Each prompt file should start with:
   ```
   # VERSION: 1.0.0
   # LAST_TESTED: 2026-02-10
   ```

4. **Tests**:
   tests/test_base_agent.py:
   - test_prompt_loading: verify prompt file loaded correctly
   - test_prompt_version_extracted: verify version parsed
   - test_json_parsing_clean: '{"key": "value"}' → parsed correctly
   - test_json_parsing_with_fences: '```json\n{"key": "value"}\n```' → parsed
   - test_json_parsing_with_preamble: 'Here is the result:\n{"key": "value"}' → parsed

   (LLM client tests will be integration tests — mock for now)
   tests/test_llm_client.py:
   - test_retry_on_rate_limit: mock API to raise rate limit once, then succeed → should succeed
   - test_retry_exhausted: mock API to always fail → should raise
   - test_budget_recorded: mock successful call → verify budget.record called
   - test_semaphore_released_on_error: mock API error → verify release() called (the try/finally fix)

Run pytest tests/ and confirm all pass.
```

### Prompt 13: Individual Agent Implementations

```
Read §4.1-4.6 of ./job-agent-spec-v3.md.

Implement each LLM agent as a subclass of BaseAgent.

1. **agents/scout.py** — ScoutAgent:
   - call(profile, mode) → builds messages with profile target_roles and skills, returns list of discovered jobs
   - Integrates with: job_search_api, greenhouse_api, lever_api, web_search (these are tool calls — for now, define the interfaces as abstract methods that will be implemented with real APIs later)
   - For now, implement the output parsing: expects JSON array of job objects matching the Scout output format

2. **agents/match.py** — MatchAgent:
   - call(profile, jobs) → scores each job, returns list of MatchResult objects
   - MatchResult dataclass: job, composite_score, classification, dimension_scores, key_selling_points, gaps, tailoring_notes

3. **agents/resume.py** — ResumeAgent:
   - call(profile, job, tailoring_notes, mode="draft", previous=None, issues=None) → returns ResumeResult
   - ResumeResult dataclass: resume_content, profile_entries_used, iterations_completed, iteration_log, quality_score (set later by verifier)
   - "draft" mode: sends profile + job + tailoring notes
   - "revise" mode: sends previous resume + specific issue list from fact-checker

4. **agents/cover_letter.py** — CoverLetterAgent:
   - call(profile, style_guide, job, tailoring_notes, resume_content, resume_fact_check_flags, mode="draft", previous=None, issues=None)
   - CoverLetterResult dataclass: cover_letter_content, profile_entries_used, company_facts_used, voice_match_confidence, etc.

5. **agents/app_questions.py** — AppQuestionsAgent:
   - call(profile, job, questions) → returns list of AppQuestionAnswer
   - AppQuestionAnswer dataclass: question_text, answer, source, profile_entries_used, confidence, needs_human_review

6. **agents/verify.py** — VerifyAgent:
   - call(profile, style_guide, resume, cover_letter, app_questions, match_result, fact_check_results) → returns VerifyResult
   - VerifyResult dataclass: verdict, resume_review, cover_letter_review, app_questions_review, revision_instructions

For each agent, define the dataclasses in a shared agents/models.py file.

Testing: These agents require LLM calls, so create tests that mock the LLM client:
tests/test_agents_mock.py:
- test_resume_agent_draft_mode: mock LLM response with valid JSON → verify ResumeResult parsed
- test_resume_agent_revise_mode: verify issues are included in the prompt
- test_cover_letter_receives_fact_check_flags: verify the flags appear in the constructed messages
- test_app_questions_uses_pre_approved: verify pre-approved answers are referenced in prompt
- test_verify_agent_excludes_code_checks: verify "No skills above proficiency level" is NOT in the "already checked" list (v3.1 fix)
- test_match_agent_classification_boundaries: mock responses at score boundaries, verify STRONG/GOOD/MARGINAL/WEAK classification

Run pytest tests/ and confirm all pass.
```

---

## PHASE 4: Orchestration

### Prompt 14: Orchestrator Core

```
Read §7.1 of ./job-agent-spec-v3.md.

Implement agents/orchestrator.py — the central coordinator.

This is the most complex file. Build it incrementally.

1. **Orchestrator.__init__**: Load config, profile, profile_index, style_guide. Initialize all agents, verifier, rate limiter, budget, state manager, checkpoint manager, posting checker, dedup engines.

2. **Orchestrator.run()**: Main async loop per spec. Check paused state, run discovery on schedule, sleep between cycles. Handle exceptions at top level.

3. **Orchestrator._call_llm()**: The centralized LLM call wrapper with try/finally for semaphore release, retry logic, budget recording. MUST use the v3.1 fix pattern:
   ```python
   await self.api_limiter.acquire()
   try:
       result = await agent.call(**kwargs)
       self.budget.record(result.token_usage)
       return result
   except ...:
       ...
   finally:
       self.api_limiter.release()
   ```

4. **Orchestrator.generate_application(match_result)**: Full pipeline:
   a. Budget check (v3.1 fix: log + set status "budget_skipped" on failure, don't silently return)
   b. Resume loop (_resume_loop)
   c. Cover letter loop (_cl_loop) if required
   d. App questions loop (_aq_loop) if questions exist
   e. LLM verify
   f. Posting expiration check
   g. Application dedup check
   h. Package and queue

5. **Orchestrator._resume_loop(match_result)**: Per §6.1:
   - Draft → verify → revise loop (max 4 iterations)
   - Best-version tracking by quality_score (NOT self-score)
   - Per-iteration checkpointing
   - Returns best version

6. **Orchestrator._cl_loop(match_result, resume, resume_verification)**: Same structure, passes resume fact-check flags.

7. **Orchestrator._aq_loop(match_result)**: Simpler — one draft → verify → one revision.

8. **Orchestrator._recover_incomplete()**: On startup, scan checkpoints for jobs with status="generating", resume from last checkpoint.

Testing: This requires extensive mocking.
tests/test_orchestrator.py:
- test_budget_skip_logged: mock budget.can_afford → False, verify state updated to "budget_skipped" (not silently dropped)
- test_resume_loop_best_version: mock 3 iterations with scores [60, 85, 70] → returns iteration 2 (score 85)
- test_resume_loop_passes_on_first_try: mock first iteration PASS → returns immediately
- test_resume_loop_max_iterations: mock all FAIL → returns best + "needs_human_help" flag
- test_posting_expired_skips: mock posting_checker.is_live → False → status "posting_expired"
- test_duplicate_flagged: mock app_dedup → duplicate → queued with flag
- test_checkpoint_saved_per_iteration: verify _checkpoint called during _resume_loop
- test_recovery_on_startup: create fake checkpoint + "generating" state → verify _recover_incomplete finds it

Run pytest tests/ and confirm all pass.
```

---

## PHASE 5: Dashboard

### Prompt 15: FastAPI Dashboard

```
Read §8 of ./job-agent-spec-v3.md.

Implement the review dashboard using FastAPI + Jinja2 + htmx.

1. **dashboard/app.py**: FastAPI application with routes:
   - GET / → Queue view (list of pending applications, sorted by deadline then score)
   - GET /application/{id} → Detail view (job posting, resume, CL, app questions, match analysis)
   - POST /application/{id}/approve → Approve flow: posting re-check → dup check → render PDF/DOCX → update state
   - POST /application/{id}/skip → Skip with reason (form field), update state
   - POST /application/{id}/edit → Accept edited content (resume/CL/app answers), save. Mark quality_score as pre_edit_score per human edit policy.
   - POST /application/{id}/reverify → Optional re-verification of edited content (v3.1 human edit policy: runs suite, shows results, doesn't block)
   - POST /application/{id}/regenerate → Re-run generation pipeline
   - GET /history → History view with filterable table
   - GET /stats → Stats view with summary cards
   - GET /api/queue → JSON API for queue data (used by htmx)

2. **dashboard/templates/**: Jinja2 templates per the wireframes in §8:
   - base.html: common layout, htmx script, marked.js, basic CSS
   - queue.html: queue card list per wireframe. Color coding: 🟢 STRONG, 🔵 GOOD, 🟡 MARGINAL, 🔴 needs_human_help. Shows budget in header.
   - detail.html: side-by-side layout per wireframe. Left: job posting (scrollable). Right top: resume (markdown rendered via marked.js). Right middle: cover letter. Bottom left: match analysis scores. Bottom right: app questions (editable). Action buttons at bottom.
   - history.html: table with columns: date, company, title, score, status, outcome dropdown. Outcome dropdown uses htmx POST to update.
   - stats.html: summary cards. Totals, rates, costs.

   For editing: use a textarea (not CodeMirror for v1 — that can be upgraded later). The Edit button shows/hides the textarea. Markdown preview updates live via marked.js.

3. **dashboard/static/**: Download and include htmx.min.js and marked.min.js. Add a basic styles.css.

4. **Tests**:
   tests/test_dashboard.py (using FastAPI TestClient):
   - test_queue_loads: GET / returns 200
   - test_queue_shows_entries: populate state with 2 queue entries, verify they appear in response
   - test_detail_loads: GET /application/{id} returns 200 for valid id
   - test_approve_checks_posting: POST approve → verify posting check was called
   - test_skip_updates_state: POST skip → verify state updated
   - test_edit_preserves_pre_edit_score: POST edit with new content → verify pre_edit_score field set
   - test_history_loads: GET /history returns 200
   - test_stats_loads: GET /stats returns 200

Run pytest tests/ and confirm all pass.
```

---

## PHASE 6: Calibration + Cleanup

### Prompt 16: Calibration + Cleanup + Final Integration

```
Read §11 and §14 (cleanup section) of ./job-agent-spec-v3.md.

1. **Implement calibration/recalibrate.py**:
   simple_recalibrate(outcomes, current_thresholds) per §11.2:
   - Phase 1 (< 50 outcomes): adjust only GOOD threshold
   - Phase 2 (50-100): adjust all three thresholds
   - Phase 3 (100+): dimension re-weighting via logistic regression (stub this — return action="full_recalibrate" with a TODO note, since it requires sklearn and more data than we'll have initially)

   calibration/outcome_analyzer.py:
   - compute_conversion_rates(outcomes) → rates by classification bucket
   - compute_cost_per_outcome(outcomes) → average cost per positive outcome
   - generate_report(outcomes) → summary dict for stats dashboard

2. **Implement cleanup logic** in agents/checkpoint.py (extend existing):
   - cleanup_expired_logs(log_dir, retention_days) → deletes log files older than N days
   - cleanup_completed_checkpoints(checkpoint_dir, state) → removes checkpoints for applications that are no longer "generating"
   - cleanup_old_queue_entries(state, retention_days) → archives old queue entries

3. **Create a CLI entry point** — main.py at project root:
   ```python
   # Commands:
   # python main.py run          → starts orchestrator + dashboard
   # python main.py dashboard    → starts dashboard only
   # python main.py calibrate    → runs calibration on current outcomes
   # python main.py cleanup      → runs cleanup
   # python main.py validate     → validates profile.json and style_guide.md
   ```

4. **Final integration tests**:
   tests/test_integration.py:
   - test_full_pipeline_mock: Mock all LLM calls with realistic responses. Run a single job through the full pipeline: scout → match → resume → verify → cover letter → verify → app questions → posting check → dedup → queue. Verify: state updated correctly at each stage, checkpoints created, queue entry has all fields, quality_score computed by code.
   - test_calibration_phase1: create 25 outcomes (20 GOOD with 0 positive, 5 STRONG with 2 positive) → should recommend raising GOOD threshold
   - test_calibration_insufficient_data: 10 outcomes → "insufficient_data"
   - test_cleanup_removes_old_checkpoints: create checkpoint for completed app → cleanup removes it
   - test_validate_profile: valid profile → passes; profile missing required fields → reports errors

Run pytest tests/ — ALL tests across all phases should pass.
```

---

## PHASE 7: Documentation + Final Polish

### Prompt 17: README + Configuration Guide + Quick Start

```
Create project documentation:

1. **README.md** at project root:
   - Project description: what this is, what it does
   - Architecture overview (simplified version of §1)
   - Quick start: install, configure, run
   - How it works: the pipeline in plain English
   - Configuration: what to edit and where
   - Profile setup guide: how to populate profile.json
   - Style Guide setup: how to run the calibration session
   - Dashboard usage: screenshots/descriptions of each view
   - Cost expectations
   - Development: how to run tests, how to modify prompts

2. **docs/PROFILE_GUIDE.md**: Step-by-step guide to populating profile.json:
   - What each section means
   - Tips for writing good accomplishments (quantify, be specific)
   - How to handle missing data
   - The application_question_answers section and why it matters

3. **docs/PROMPT_ENGINEERING.md**: Guide to modifying agent prompts:
   - File locations
   - Version numbering convention
   - How to test prompt changes (regression testing)
   - What to watch out for (don't remove grounding rules, etc.)

4. Verify the full test suite passes: pytest tests/ -v

5. Print a summary of the project:
   - Total files created
   - Total lines of code (excluding tests)
   - Total test count
   - Test pass rate
```

---

## Implementation Notes for the Human

**Sequencing rationale:** Phases 1-2 build all the testable, deterministic code that doesn't need API keys. You can validate the entire verification pipeline, state management, and rendering without spending a dollar. Phase 3 adds LLM wrappers (mockable). Phase 4 ties it together. Phase 5 is the UI. Phase 6 is operational tooling. Phase 7 is docs.

**Where to expect friction:**
- Prompt 3 (Source Mapper) — threshold tuning will need iteration with real data
- Prompt 6 (Structural Detector) — spaCy POS tags aren't perfectly reliable on resume fragments
- Prompt 14 (Orchestrator) — most complex file, most mocking required for tests
- Prompt 15 (Dashboard) — htmx interactions might need debugging in-browser

**What to skip if in a hurry:**
- Phase 5 (Dashboard) — use the JSON queue files directly, review in any text editor
- Prompt 16 calibration — not needed until you have 20+ outcomes (weeks of usage)
- The rendering pipeline — just submit the markdown or paste into the application form

**What NOT to skip:**
- Prompts 1-7 (verification suite) — this is the core value. Without it, you're just another LLM cover letter generator.
- Prompt 14 (orchestrator) — ties everything together
- Test fixtures — they're the basis for all threshold tuning
