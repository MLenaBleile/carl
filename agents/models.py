"""Shared dataclasses for all LLM agents."""

from dataclasses import dataclass, field


@dataclass
class MatchResult:
    """Result from MatchAgent scoring a job."""
    job: dict
    composite_score: float
    classification: str  # STRONG | GOOD | MARGINAL | WEAK
    dimension_scores: dict = field(default_factory=dict)
    key_selling_points: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    tailoring_notes: str = ""
    token_usage: dict = field(default_factory=dict)


@dataclass
class ResumeResult:
    """Result from ResumeAgent generating/revising a resume."""
    resume_content: str
    profile_entries_used: list[str] = field(default_factory=list)
    iterations_completed: int = 1
    iteration_log: list[dict] = field(default_factory=list)
    remaining_concerns: list[str] = field(default_factory=list)
    quality_score: int = 0  # Set by VerificationRunner, not self-score
    profile_version: str = "1.0.0"
    token_usage: dict = field(default_factory=dict)


@dataclass
class CoverLetterResult:
    """Result from CoverLetterAgent."""
    cover_letter_content: str
    profile_entries_used: list[str] = field(default_factory=list)
    company_facts_used: list[dict] = field(default_factory=list)
    voice_match_confidence: str = "not_assessed"
    iterations_completed: int = 1
    iteration_log: list[dict] = field(default_factory=list)
    remaining_concerns: list[str] = field(default_factory=list)
    quality_score: int = 0
    profile_version: str = "1.0.0"
    token_usage: dict = field(default_factory=dict)


@dataclass
class AppQuestionAnswer:
    """Single application question answer."""
    question_text: str
    answer: str
    source: str  # pre_approved | profile_derived | job_posting_derived
    profile_entries_used: list[str] = field(default_factory=list)
    confidence: str = "high"  # high | medium | low
    needs_human_review: bool = False


@dataclass
class AppQuestionsResult:
    """Result from AppQuestionsAgent."""
    answers: list[AppQuestionAnswer] = field(default_factory=list)
    token_usage: dict = field(default_factory=dict)


@dataclass
class VerifyResult:
    """Result from VerifyAgent."""
    verdict: str  # PASS | FAIL
    resume_review: dict = field(default_factory=dict)
    cover_letter_review: dict = field(default_factory=dict)
    app_questions_review: dict = field(default_factory=dict)
    revision_instructions: dict = field(default_factory=dict)
    notes: str = ""
    token_usage: dict = field(default_factory=dict)
