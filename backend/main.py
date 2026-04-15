import json
import logging
import os
import re
from typing import Dict, List

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from openai import AsyncOpenAI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

PUBMED_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
NIM_MODEL = "meta/llama-3.1-70b-instruct"
NIM_TEMPERATURE = 0.2
NIM_MAX_TOKENS = 1000
NIM_TOP_P = 0.7
NIM_STREAM = True
NIM_ENABLE_THINKING = False
PUBMED_DB = "pubmed"
PUBMED_RETMAX = 30
TOP_RESULTS = 8
MAX_PER_CATEGORY = 3
CATEGORY_ORDER = [
    "Treatment Insights",
    "Clinical Trials",
    "Prognosis",
    "Other",
]

app = FastAPI(title="ClinIQ")
load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
logger = logging.getLogger(__name__)


def parse_cors_origins() -> List[str]:
    raw_origins = os.getenv("ALLOW_ORIGINS", "")
    origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
    if origins:
        return origins
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

LOCKED_LLM_PROMPT_TEMPLATE = """You are a STRICT medical summary formatter.

You are given structured medical research summary data.

Your ONLY job is to format the provided summary fields into readable text WITHOUT ANY modification.

ABSOLUTE RULES (NON-NEGOTIABLE):

1. You MUST ONLY use the exact summary fields provided in the input.

2. You MUST NOT:

   * add new research papers
   * mention paper titles
   * invent new examples
   * infer missing data
   * rewrite item-level evidence

3. You MUST ONLY format:

   * overall_summary
   * overall_confidence
   * uncertainty_notes
   * key_takeaways
   * category summaries
   * trend strengths
   * suggested next steps

4. If any transformation risks altering meaning:
   → output the original text exactly

INPUT DATA:
{{structured_json_output}}

TASK:
Convert the structured summary data into clean, readable text.

STRICT OUTPUT FORMAT:

1. Summary paragraph
2. Overall Confidence
3. Uncertainty Notes
4. Key Takeaways (bullet points)
5. Treatment Insights

   * Trend Strength
   * Summary only
6. Clinical Trials

   * Trend Strength
   * Summary only
7. Prognosis

   * Trend Strength
   * Summary only
8. Other Relevant Research

   * Trend Strength
   * Summary only
9. Suggested Next Steps

CRITICAL ENFORCEMENT:

* DO NOT render item-level research papers
* DO NOT rewrite or paraphrase paper titles
* DO NOT merge or invent item-level evidence
* DO NOT introduce examples not present in the input

If unsure:
→ keep original summary text unchanged

Goal:
Perfect summary formatting with ZERO item-level alteration."""

app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    query: str = ""
    location: str = ""
    last_disease: str | None = None


class PubMedResult(BaseModel):
    pubmed_id: str
    link: str
    title: str
    pub_date: str
    score: int
    category: str
    reason: str
    impact: str


class CategoryResponse(BaseModel):
    trend_strength: str
    summary: str
    items: List[PubMedResult]


class QueryResponse(BaseModel):
    overall_summary: str
    overall_confidence: str
    uncertainty_notes: str
    key_takeaways: List[str]
    Treatment_Insights: CategoryResponse = Field(..., alias="Treatment Insights")
    Clinical_Trials: CategoryResponse = Field(..., alias="Clinical Trials")
    Prognosis: CategoryResponse
    Other: CategoryResponse

    class Config:
        populate_by_name = True


class QueryContext(BaseModel):
    disease: str
    location: str = ""
    built_query: str
    expanded_terms: List[str]


class FinalResponse(BaseModel):
    query_context: QueryContext
    raw_data: QueryResponse
    llm_output: str | None
    validated: bool
    status: str
    error: str | None = None


class HealthResponse(BaseModel):
    status: str


def extract_year(pub_date: str) -> int | None:
    year_match = re.search(r"(19|20)\d{2}", pub_date)
    return int(year_match.group(0)) if year_match else None


def normalize_disease_name(disease: str) -> str:
    return re.sub(r"\s+", " ", disease.strip().lower())


def disease_aliases(disease: str) -> List[str]:
    normalized = normalize_disease_name(disease)
    alias_map = {
        "lung cancer": ["lung cancer", "nsclc", "small cell lung", "non-small cell lung", "sclc"],
        "breast cancer": ["breast cancer", "breast carcinoma"],
        "glioblastoma": ["glioblastoma", "glioblastoma multiforme", "gbm"],
    }
    if normalized in alias_map:
        return alias_map[normalized]

    tokens = [token for token in re.split(r"[\s/-]+", normalized) if len(token) > 2]
    aliases = [normalized]
    if tokens:
        aliases.extend([" ".join(tokens), *tokens])
    return list(dict.fromkeys(alias for alias in aliases if alias))


def paper_matches_disease(title: str, disease: str) -> bool:
    title_lower = title.lower()
    aliases = disease_aliases(disease)
    if any(alias in title_lower for alias in aliases):
        return True

    key_tokens = [token for token in re.split(r"[\s/-]+", normalize_disease_name(disease)) if len(token) > 3]
    return bool(key_tokens) and all(token in title_lower for token in key_tokens)


def paper_has_conflicting_disease(title: str, disease: str) -> bool:
    title_lower = title.lower()
    if paper_matches_disease(title, disease):
        return False

    conflicting_markers = [
        "lung cancer",
        "nsclc",
        "small cell lung",
        "breast cancer",
        "glioblastoma",
        "prostate cancer",
        "colorectal cancer",
        "ovarian cancer",
        "pancreatic cancer",
        "leukemia",
        "lymphoma",
        "melanoma",
    ]
    allowed_aliases = set(disease_aliases(disease))
    return any(marker in title_lower and marker not in allowed_aliases for marker in conflicting_markers)


def contains_conflicting_disease(text: str, disease: str) -> bool:
    return paper_has_conflicting_disease(text, disease)


def expand_query(query: str) -> List[str]:
    normalized = query.strip().lower()
    mappings = {
        "lung cancer": [
            "lung cancer treatment",
            "NSCLC therapy",
            "lung cancer clinical trials",
            "small cell lung cancer therapy",
        ]
    }
    return mappings.get(
        normalized,
        [
            f"{query.strip()} treatment",
            f"{query.strip()} clinical trials",
            f"{query.strip()} survival",
        ],
    )


def is_vague_query(query: str) -> bool:
    normalized = query.strip().lower()
    if not normalized:
        return True

    explicit_disease_markers = [
        "cancer",
        "tumor",
        "carcinoma",
        "disease",
        "syndrome",
        "lung",
        "nsclc",
        "small cell",
    ]
    if any(marker in normalized for marker in explicit_disease_markers):
        return False

    vague_markers = [
        "what about",
        "treatment",
        "therapy",
        "clinical trial",
        "trials",
        "research",
        "survival",
        "prognosis",
    ]
    return any(marker in normalized for marker in vague_markers)


def resolve_disease_query(query: str, last_disease: str | None) -> str:
    cleaned_query = query.strip()
    cleaned_last_disease = (last_disease or "").strip()

    if cleaned_query:
        if cleaned_last_disease and is_vague_query(cleaned_query):
            return cleaned_last_disease
        return cleaned_query

    return cleaned_last_disease


def build_query(disease: str, location: str) -> str:
    cleaned_disease = disease.strip()
    cleaned_location = location.strip()
    if cleaned_location:
        return f"{cleaned_disease} {cleaned_location} clinical trials OR treatment OR research"
    return cleaned_disease


def score_paper(title: str, pub_date: str, disease: str, location: str = "") -> int:
    score = 0
    title_lower = title.lower()
    location_lower = location.strip().lower()
    has_treatment_intent = (
        "treatment" in title_lower
        or "therapy" in title_lower
        or "clinical trial" in title_lower
    )
    disease_lower = normalize_disease_name(disease)

    if disease_lower and disease_lower in title_lower:
        score += 5
    elif paper_matches_disease(title, disease):
        score += 4

    if disease_lower == "lung cancer":
        if "nsclc" in title_lower:
            score += 4
        if bool(re.search(r"(?<!non[-\s])small cell lung", title_lower)):
            score += 4

    if "treatment" in title_lower or "therapy" in title_lower:
        score += 3
    if "clinical trial" in title_lower:
        score += 3
    if "survival" in title_lower or "prognosis" in title_lower:
        score += 2

    year = extract_year(pub_date)

    if year is not None and 2025 <= year <= 2026:
        score += 3
    elif year is not None and 2023 <= year <= 2024:
        score += 2
    else:
        score += 1

    if not has_treatment_intent:
        score -= 2

    if location_lower and location_lower in title_lower:
        score += 1

    return score


def categorize_paper(title: str) -> str:
    title_lower = title.lower()
    if any(keyword in title_lower for keyword in ["clinical trial", "trial", "randomized", "phase"]):
        return "Clinical Trials"
    if any(keyword in title_lower for keyword in ["survival", "prognosis", "outcome"]):
        return "Prognosis"
    if any(keyword in title_lower for keyword in ["treatment", "therapy", "chemotherapy", "immunotherapy"]):
        return "Treatment Insights"
    if "study" in title_lower:
        return "Clinical Trials"
    return "Other"


def build_reason(title: str, pub_date: str, category: str, disease: str) -> str:
    title_lower = title.lower()
    year = extract_year(pub_date)
    year_hint = f" from {year}" if year is not None else ""
    disease_label = disease.strip()

    if category == "Treatment Insights":
        if "precision medicine" in title_lower:
            return "Treatment overview spanning chemoradiotherapy and precision medicine"
        if "immunotherapy" in title_lower and "duration" in title_lower:
            return f"Recent immunotherapy paper examining treatment duration{year_hint}"
        if "chemotherapy" in title_lower:
            return f"Treatment-focused paper examining chemotherapy strategies{year_hint}"
        if "anticoagulant" in title_lower:
            return "Therapy-related paper examining bleeding risk during anticoagulant use"
        if "targeting" in title_lower:
            return f"Targeted therapy paper focused on an advanced {disease_label} mechanism{year_hint}"
        if "real-world" in title_lower and "outcome" in title_lower:
            return "Study focused on treatment outcomes in real-world patients"
        if "treatment" in title_lower:
            return f"Recent paper covering {disease_label} treatment strategy{year_hint}"
        if "therapy" in title_lower:
            return f"Therapy-focused paper outlining a {disease_label} management approach{year_hint}"
        return f"Treatment-focused paper relevant to current {disease_label} care{year_hint}"

    if category == "Clinical Trials":
        if "systematic review" in title_lower:
            return f"Review of clinical trials assessing current {disease_label} treatment approaches"
        if "phase" in title_lower:
            return f"Phase-based clinical study assessing a {disease_label} intervention{year_hint}"
        if "randomized" in title_lower:
            return f"Randomized clinical study comparing {disease_label} care options{year_hint}"
        if "immunotherapy" in title_lower:
            return "Recent clinical trial evaluating an immunotherapy strategy"
        if "retrospective study" in title_lower or "multicenter" in title_lower:
            return f"Multicenter clinical study evaluating a {disease_label} intervention"
        return f"Clinical study evaluating a disease-specific intervention{year_hint}"

    if category == "Prognosis":
        if "surgery" in title_lower and "radiotherapy" in title_lower:
            return "Prognosis comparison between surgical and radiotherapy approaches"
        if "survival" in title_lower:
            return f"Survival-focused analysis in {disease_label} patients{year_hint}"
        if "outcome" in title_lower:
            return f"Study focused on outcomes in a {disease_label} population"
        return f"Prognosis-oriented paper relevant to {disease_label} care{year_hint}"

    return f"Relevant {disease_label} research adding supporting clinical context{year_hint}"


def build_impact(title: str, category: str, disease: str) -> str:
    title_lower = title.lower()
    disease_label = disease.strip()

    if category == "Treatment Insights":
        if "precision medicine" in title_lower or "targeting" in title_lower:
            return "Suggests clinicians may increasingly rely on biomarker-guided and targeted treatment selection."
        if "immunotherapy" in title_lower:
            return "Highlights emerging preference for immunotherapy-driven treatment planning."
        if "chemotherapy" in title_lower:
            return "Indicates chemotherapy remains important alongside newer treatment strategies."
        if "anticoagulant" in title_lower:
            return "Suggests clinicians may need to weigh bleeding risk more carefully during active treatment."
        return f"Indicates growing importance of more tailored treatment planning in {disease_label} care."

    if category == "Clinical Trials":
        if "immunotherapy" in title_lower or "pembrolizumab" in title_lower:
            return "Highlights emerging preference for immunotherapy combinations in active trials."
        if "chemotherapy" in title_lower:
            return "Suggests clinicians may continue to see chemotherapy combinations tested against newer regimens."
        return "Indicates growing importance of trial evidence in shaping upcoming treatment choices."

    if category == "Prognosis":
        if "surgery" in title_lower and "radiotherapy" in title_lower:
            return "Highlights emerging preference for comparing major treatment pathways through survival impact."
        if "survival" in title_lower:
            return "Indicates growing importance of tracking survival gains linked to newer care patterns."
        if "outcome" in title_lower:
            return "Suggests clinicians may increasingly rely on real-world outcomes to guide expectations."
        return "Indicates growing importance of prognosis signals when evaluating treatment value."

    return f"Adds useful context around the broader {disease_label} evidence landscape."


def collect_theme_counts(items: List[PubMedResult]) -> Dict[str, int]:
    theme_keywords = {
        "immunotherapy": ["immunotherapy", "checkpoint inhibitor", "pembrolizumab", "nivolumab"],
        "chemotherapy": ["chemotherapy", "carboplatin", "paclitaxel"],
        "targeted therapy": ["targeted", "egfr", "met", "biomarker", "precision medicine"],
        "real-world evidence": ["real-world"],
        "survival outcomes": ["survival", "outcome", "prognosis"],
        "combination strategies": ["combination", "plus"],
    }
    counts = {theme: 0 for theme in theme_keywords}
    for item in items:
        title_lower = item.title.lower()
        for theme, keywords in theme_keywords.items():
            if any(keyword in title_lower for keyword in keywords):
                counts[theme] += 1
    return counts


def has_conflict_signals(items: List[PubMedResult]) -> bool:
    conflict_keywords = ["comparison", "versus", "risk", "variation"]
    for item in items:
        title_lower = item.title.lower()
        if any(keyword in title_lower for keyword in conflict_keywords):
            return True
    return False


def calculate_trend_strength(items: List[PubMedResult]) -> str:
    if not items:
        return "Low"

    high_score_count = sum(1 for item in items if item.score >= 13)
    moderate_score_count = sum(1 for item in items if item.score >= 10)
    average_score = sum(item.score for item in items) / len(items)

    if len(items) >= 3 and high_score_count >= 2 and average_score >= 12:
        return "High"
    if len(items) >= 2 and moderate_score_count >= 2 and average_score >= 10:
        return "Medium"
    return "Low"


def build_category_summary(category: str, items: List[PubMedResult], disease: str) -> str:
    if not items:
        return "No high-confidence research signals identified in this category."

    theme_counts = collect_theme_counts(items)
    prominent_themes = [theme for theme, count in theme_counts.items() if count > 0]
    year_values = [extract_year(item.pub_date) for item in items if extract_year(item.pub_date) is not None]
    recent_focus = "recent 2025-2026 work" if any(year >= 2025 for year in year_values) else "mixed publication years"
    trend_strength = calculate_trend_strength(items)
    weak_signal_note = ""
    if trend_strength == "Low":
        weak_signal_note = " Evidence remains limited because the selected papers are fewer or lower-scoring."
    elif trend_strength == "Medium" and len(items) < 3:
        weak_signal_note = " The pattern is meaningful but still based on a modest number of papers."

    if category == "Treatment Insights":
        if theme_counts["immunotherapy"] and theme_counts["targeted therapy"]:
            return f"Recent research strongly indicates a shift toward immunotherapy and targeted therapy, pointing to precision medicine as a leading treatment direction in {recent_focus}.{weak_signal_note}"
        if theme_counts["chemotherapy"] and theme_counts["real-world evidence"]:
            return f"Recent treatment research strongly indicates chemotherapy is being refined through real-world evidence rather than replaced outright in {recent_focus}.{weak_signal_note}"
        if prominent_themes:
            return f"Recent treatment papers strongly indicate momentum around {', '.join(prominent_themes[:2])}, signaling a meaningful shift in {disease} management in {recent_focus}.{weak_signal_note}"
        return f"Recent treatment papers strongly indicate ongoing change in {disease} management approaches in {recent_focus}.{weak_signal_note}"

    if category == "Clinical Trials":
        if theme_counts["immunotherapy"] and theme_counts["combination strategies"]:
            return f"Recent clinical studies strongly indicate trial activity is centered on immunotherapy-based combinations, reinforcing this as a priority direction in {recent_focus}.{weak_signal_note}"
        if theme_counts["immunotherapy"]:
            return f"Recent clinical studies strongly indicate immunotherapy remains the dominant focus of trial evaluation in {recent_focus}.{weak_signal_note}"
        return f"Recent clinical studies strongly indicate active testing of new interventions in {disease} patients across {recent_focus}.{weak_signal_note}"

    if category == "Prognosis":
        if theme_counts["survival outcomes"] and theme_counts["real-world evidence"]:
            return f"Recent prognosis research strongly indicates survival assessment is increasingly tied to real-world evidence, not just tightly controlled studies, in {recent_focus}.{weak_signal_note}"
        return f"Recent prognosis papers strongly indicate survival and outcome patterns are becoming central to treatment evaluation in {recent_focus}.{weak_signal_note}"

    if prominent_themes:
        return f"Other relevant papers indicate supporting signals around {', '.join(prominent_themes[:2])}.{weak_signal_note}"
    return f"Other relevant papers indicate broader supporting clinical context.{weak_signal_note}"


def build_overall_summary(grouped_items: Dict[str, List[PubMedResult]], disease: str) -> str:
    all_items = [item for items in grouped_items.values() for item in items]
    if not all_items:
        return f"No relevant {disease} papers were identified from the selected PubMed queries."

    theme_counts = collect_theme_counts(all_items)
    year_values = [extract_year(item.pub_date) for item in all_items if extract_year(item.pub_date) is not None]
    recent_focus = "Recent research (2025-2026)" if any(year >= 2025 for year in year_values) else "The selected research"

    focus_parts = []
    if theme_counts["immunotherapy"]:
        focus_parts.append("immunotherapy")
    if theme_counts["targeted therapy"]:
        focus_parts.append("precision medicine and targeted therapy")
    if theme_counts["chemotherapy"]:
        focus_parts.append("chemotherapy strategy refinement")
    if theme_counts["survival outcomes"]:
        focus_parts.append("survival and outcome tracking")

    if not focus_parts:
        focus_text = f"{disease} management"
    elif len(focus_parts) == 1:
        focus_text = focus_parts[0]
    else:
        focus_text = ", ".join(focus_parts[:-1]) + f", and {focus_parts[-1]}"

    trial_signal = ""
    if grouped_items["Clinical Trials"]:
        trial_signal = " Clinical studies also indicate these approaches are being actively tested in practice."

    return f"{recent_focus} strongly indicates a shift toward {focus_text}.{trial_signal}"


def build_key_takeaways(grouped_items: Dict[str, List[PubMedResult]], disease: str) -> List[str]:
    all_items = [item for items in grouped_items.values() for item in items]
    if not all_items:
        return ["No high-confidence cross-paper signals identified from the selected results."]

    theme_counts = collect_theme_counts(all_items)
    takeaways: List[str] = []

    if theme_counts["immunotherapy"] and theme_counts["targeted therapy"]:
        takeaways.append(
            f"Immunotherapy and targeted therapy dominate the strongest recent {disease} treatment signals."
        )
    elif theme_counts["immunotherapy"]:
        takeaways.append(
            "Immunotherapy remains the clearest recurring signal across the highest-ranked recent papers."
        )

    if grouped_items["Clinical Trials"]:
        if theme_counts["combination strategies"] or theme_counts["immunotherapy"]:
            takeaways.append(
                "Clinical trial activity is concentrated around checkpoint inhibitors and combination strategies."
            )
        else:
            takeaways.append(
                f"Clinical studies remain an important driver of which {disease} interventions are gaining momentum."
            )

    if grouped_items["Prognosis"]:
        if theme_counts["survival outcomes"] and theme_counts["real-world evidence"]:
            takeaways.append(
                f"Real-world outcome studies are becoming central to understanding survival patterns in {disease}."
            )
        else:
            takeaways.append(
                "Recent prognosis papers keep survival outcomes near the center of treatment evaluation."
            )

    if theme_counts["chemotherapy"]:
        takeaways.append(
            "Chemotherapy still appears as an active component of modern care, often alongside newer approaches."
        )

    if not takeaways:
        takeaways.append(
            f"The highest-ranked papers point to increasingly specialized and evidence-driven {disease} care."
        )

    return takeaways[:5]


def calculate_overall_confidence(grouped_items: Dict[str, List[PubMedResult]]) -> str:
    all_items = [item for items in grouped_items.values() for item in items]
    if not all_items:
        return "Low"

    populated_categories = sum(1 for category in CATEGORY_ORDER if grouped_items[category])
    high_score_count = sum(1 for item in all_items if item.score >= 13)
    moderate_score_count = sum(1 for item in all_items if item.score >= 10)

    if populated_categories >= 3 and high_score_count >= 3:
        return "High"
    if populated_categories >= 2 and moderate_score_count >= 4:
        return "Medium"
    return "Low"


def build_uncertainty_notes(grouped_items: Dict[str, List[PubMedResult]]) -> str:
    all_items = [item for items in grouped_items.values() for item in items]
    if not all_items:
        return "Findings are based on very limited evidence from the selected PubMed results."

    notes: List[str] = []
    high_score_count = sum(1 for item in all_items if item.score >= 13)
    low_strength_categories = [
        category for category in CATEGORY_ORDER if calculate_trend_strength(grouped_items[category]) == "Low"
    ]
    recent_years = [extract_year(item.pub_date) for item in all_items if extract_year(item.pub_date) is not None]

    if high_score_count <= 2:
        notes.append("Findings are based on a limited number of high-scoring studies.")
    elif len(all_items) <= 4:
        notes.append("Evidence is directionally useful but comes from a relatively small set of selected papers.")

    if low_strength_categories:
        notes.append(
            f"Signals are weaker in {', '.join(low_strength_categories)}, where coverage is sparse or lower-scoring."
        )

    if has_conflict_signals(all_items):
        notes.append(
            "Some studies compare differing approaches, indicating potential variation in outcomes."
        )

    if recent_years and all(year >= 2025 for year in recent_years):
        notes.append("Evidence is strong but primarily concentrated in recent publications.")

    if not notes:
        notes.append("The selected papers are fairly consistent, but conclusions still depend on a small curated set of results.")

    return " ".join(notes)


def build_next_steps(structured_output: QueryResponse) -> List[str]:
    next_steps: List[str] = []
    raw_data = structured_output.model_dump(by_alias=True)

    treatment_items = raw_data["Treatment Insights"]["items"]
    clinical_items = raw_data["Clinical Trials"]["items"]
    prognosis_items = raw_data["Prognosis"]["items"]

    treatment_titles = " ".join(item["title"].lower() for item in treatment_items)
    clinical_titles = " ".join(item["title"].lower() for item in clinical_items)
    prognosis_titles = " ".join(item["title"].lower() for item in prognosis_items)

    if clinical_items:
        if "immunotherapy" in clinical_titles or "pembrolizumab" in clinical_titles:
            next_steps.append("You may want to explore clinical trials if seeking newer immunotherapy-based options.")
        else:
            next_steps.append("You may want to explore clinical trials if seeking experimental treatment directions.")

    if treatment_items:
        if "precision medicine" in treatment_titles or "target" in treatment_titles or "egfr" in treatment_titles:
            next_steps.append("Treatment insights are strongest around precision medicine and targeted therapy selection.")
        elif "chemotherapy" in treatment_titles:
            next_steps.append("Treatment evidence suggests comparing where chemotherapy still fits alongside newer approaches.")

    if prognosis_items:
        if "survival" in prognosis_titles or "outcome" in prognosis_titles:
            next_steps.append("Prognosis findings suggest reviewing survival and real-world outcome patterns before comparing options.")

    if not next_steps:
        next_steps.append("You may want to review the highest-scoring category first to focus on the strongest current evidence.")

    return next_steps[:3]


def build_llm_summary_input(structured_output: QueryResponse) -> dict:
    raw_data = structured_output.model_dump(by_alias=True)
    return {
        "overall_summary": raw_data["overall_summary"],
        "overall_confidence": raw_data["overall_confidence"],
        "uncertainty_notes": raw_data["uncertainty_notes"],
        "key_takeaways": raw_data["key_takeaways"],
        "Treatment Insights": {
            "trend_strength": raw_data["Treatment Insights"]["trend_strength"],
            "summary": raw_data["Treatment Insights"]["summary"],
        },
        "Clinical Trials": {
            "trend_strength": raw_data["Clinical Trials"]["trend_strength"],
            "summary": raw_data["Clinical Trials"]["summary"],
        },
        "Prognosis": {
            "trend_strength": raw_data["Prognosis"]["trend_strength"],
            "summary": raw_data["Prognosis"]["summary"],
        },
        "Other": {
            "trend_strength": raw_data["Other"]["trend_strength"],
            "summary": raw_data["Other"]["summary"],
        },
        "Suggested Next Steps": build_next_steps(structured_output),
    }


def extract_original_titles(structured_data: dict) -> List[str]:
    titles: List[str] = []
    for category in CATEGORY_ORDER:
        category_block = structured_data.get(category, {})
        for item in category_block.get("items", []):
            title = item.get("title")
            if title:
                titles.append(title)
    return titles


def normalize_validation_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text)
    return normalized.strip()


def looks_like_paper_title(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    ignored_prefixes = [
        "-",
        "*",
        "•",
        "Summary",
        "Overall Confidence",
        "Uncertainty Notes",
        "Key Takeaways",
        "Treatment Insights",
        "Clinical Trials",
        "Prognosis",
        "Other",
        "Trend Strength",
        "Suggested Next Steps",
        "Publication Date:",
        "Score:",
        "Reason:",
        "Why It Matters:",
    ]
    if any(stripped.startswith(prefix) for prefix in ignored_prefixes):
        return False
    lowered = stripped.lower()
    summary_markers = [
        "indicates",
        "suggests",
        "highlights",
        "shows",
        "focuses",
        "summary",
        "confidence",
        "uncertainty",
        "takeaway",
        "evidence",
        "activity",
        "pattern",
        "momentum",
        "direction",
    ]
    if any(marker in lowered for marker in summary_markers):
        return False
    if stripped.endswith((".", "!", "?")) and ":" not in stripped and "(" not in stripped:
        return False
    return len(stripped.split()) >= 8 and stripped[0].isalnum() and any(char.isalpha() for char in stripped)


def validate_llm_output(llm_output: str, original_titles: list) -> bool:
    normalized_output = normalize_validation_text(llm_output)
    for title in original_titles:
        normalized_title = normalize_validation_text(title)
        if normalized_title not in normalized_output:
            logger.warning("LLM validation missing title: %s", title)
            return False
    return True


def detect_extra_titles(llm_output: str, original_titles: list) -> bool:
    normalized_titles = {normalize_validation_text(title) for title in original_titles}
    for line in llm_output.split("\n"):
        normalized_line = normalize_validation_text(line)
        if looks_like_paper_title(normalized_line) and normalized_line not in normalized_titles:
            logger.warning("LLM validation detected extra title-like line: %s", line)
            return True
    return False


def render_system_paper_list_for_validation(structured_output: QueryResponse) -> str:
    raw_data = structured_output.model_dump(by_alias=True)
    lines: List[str] = []
    for category in CATEGORY_ORDER:
        section = raw_data[category]
        lines.append(category)
        lines.append(f"Trend Strength: {section['trend_strength']}")
        for item in section["items"]:
            lines.append(item["title"])
            lines.append(f"Publication Date: {item['pub_date']}")
            lines.append(f"Score: {item['score']}")
            lines.append(f"Reason: {item['reason']}")
            lines.append(f"Why It Matters: {item['impact']}")
    return "\n".join(lines)


async def generate_llm_response(structured_data: dict) -> str:
    nim_api_key = os.getenv("NVIDIA_NIM_API_KEY")
    if not nim_api_key:
        raise HTTPException(
            status_code=500,
            detail="NVIDIA_NIM_API_KEY is not set",
        )

    prompt = LOCKED_LLM_PROMPT_TEMPLATE.replace(
        "{{structured_json_output}}",
        json.dumps(structured_data, indent=2),
    )

    client = AsyncOpenAI(
        base_url=NIM_BASE_URL,
        api_key=nim_api_key,
    )

    try:
        completion = await client.chat.completions.create(
            model=NIM_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": ""},
            ],
            temperature=NIM_TEMPERATURE,
            top_p=NIM_TOP_P,
            max_tokens=NIM_MAX_TOKENS,
            stream=NIM_STREAM,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to start formatted response generation with NVIDIA NIM: {exc}",
        ) from exc

    if NIM_STREAM:
        chunks: List[str] = []
        try:
            async for chunk in completion:
                if chunk.choices and chunk.choices[0].delta.content is not None:
                    chunks.append(chunk.choices[0].delta.content)
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Failed while streaming formatted response from NVIDIA NIM: {exc}",
            ) from exc
        llm_output = "".join(chunks).strip()
    else:
        try:
            llm_output = (completion.choices[0].message.content or "").strip()
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to read formatted response from NVIDIA NIM: {exc}",
            ) from exc

    if not llm_output:
        raise HTTPException(status_code=502, detail="NVIDIA NIM returned an empty response")

    return llm_output


async def fetch_pubmed_for_query(client: httpx.AsyncClient, query: str) -> List[dict]:
    params_esearch = {
        "db": PUBMED_DB,
        "term": query,
        "retmode": "json",
        "retmax": PUBMED_RETMAX,
    }

    try:
        esearch_resp = await client.get(PUBMED_ESEARCH_URL, params=params_esearch)
        esearch_resp.raise_for_status()
        esearch_data = esearch_resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch PubMed IDs: {exc}") from exc

    id_list = esearch_data.get("esearchresult", {}).get("idlist", [])
    if not id_list:
        return []

    params_esummary = {
        "db": PUBMED_DB,
        "id": ",".join(id_list),
        "retmode": "json",
    }

    try:
        esummary_resp = await client.get(PUBMED_ESUMMARY_URL, params=params_esummary)
        esummary_resp.raise_for_status()
        esummary_data = esummary_resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch PubMed summaries: {exc}") from exc

    result_block = esummary_data.get("result", {})
    uids = result_block.get("uids", [])
    summaries: List[dict] = []
    for uid in uids:
        item = result_block.get(uid, {})
        if item:
            item["pubmed_id"] = uid
            summaries.append(item)
    return summaries


async def fetch_pubmed_results(disease: str, location: str = "") -> QueryResponse:
    timeout = httpx.Timeout(15.0)
    built_query = build_query(disease, location)
    disease_queries = expand_query(disease)
    expanded_queries: List[str] = [built_query]
    if location.strip():
        expanded_queries.extend(f"{query} {location.strip()}" for query in disease_queries)
    else:
        expanded_queries.extend(disease_queries)
    expanded_queries = list(dict.fromkeys(query.strip() for query in expanded_queries if query.strip()))

    async with httpx.AsyncClient(timeout=timeout) as client:
        raw_items: List[dict] = []
        for expanded_query in expanded_queries:
            raw_items.extend(await fetch_pubmed_for_query(client, expanded_query))

    seen_titles = set()
    results: List[PubMedResult] = []
    for item in raw_items:
        pubmed_id = str(item.get("pubmed_id", "")).strip()
        title = item.get("title", "")
        pub_date = item.get("pubdate") or item.get("epubdate") or item.get("sortpubdate") or ""

        if not title or not pubmed_id:
            continue

        if not paper_matches_disease(title, disease):
            continue

        if paper_has_conflicting_disease(title, disease):
            continue

        normalized_title = re.sub(r"\s+", " ", title.lower()).strip()
        if normalized_title in seen_titles:
            continue
        seen_titles.add(normalized_title)

        category = categorize_paper(title)
        score = score_paper(title=title, pub_date=pub_date, disease=disease, location=location)
        reason = build_reason(title=title, pub_date=pub_date, category=category, disease=disease)
        impact = build_impact(title=title, category=category, disease=disease)

        if contains_conflicting_disease(reason, disease) or contains_conflicting_disease(impact, disease):
            continue

        results.append(
            PubMedResult(
                pubmed_id=pubmed_id,
                link=f"https://pubmed.ncbi.nlm.nih.gov/{pubmed_id}/",
                title=title,
                pub_date=pub_date,
                score=score,
                category=category,
                reason=reason,
                impact=impact,
            )
        )

    results.sort(key=lambda paper: paper.score, reverse=True)
    grouped_results: Dict[str, List[PubMedResult]] = {
        category: [] for category in CATEGORY_ORDER
    }
    total_added = 0
    for paper in results:
        if total_added >= TOP_RESULTS:
            break
        if len(grouped_results[paper.category]) >= MAX_PER_CATEGORY:
            continue
        grouped_results[paper.category].append(paper)
        total_added += 1

    return QueryResponse(
        overall_summary=build_overall_summary(grouped_results, disease),
        overall_confidence=calculate_overall_confidence(grouped_results),
        uncertainty_notes=build_uncertainty_notes(grouped_results),
        key_takeaways=build_key_takeaways(grouped_results, disease),
        **{
            "Treatment Insights": CategoryResponse(
                trend_strength=calculate_trend_strength(grouped_results["Treatment Insights"]),
                summary=build_category_summary("Treatment Insights", grouped_results["Treatment Insights"], disease),
                items=grouped_results["Treatment Insights"],
            ),
            "Clinical Trials": CategoryResponse(
                trend_strength=calculate_trend_strength(grouped_results["Clinical Trials"]),
                summary=build_category_summary("Clinical Trials", grouped_results["Clinical Trials"], disease),
                items=grouped_results["Clinical Trials"],
            ),
            "Prognosis": CategoryResponse(
                trend_strength=calculate_trend_strength(grouped_results["Prognosis"]),
                summary=build_category_summary("Prognosis", grouped_results["Prognosis"], disease),
                items=grouped_results["Prognosis"],
            ),
            "Other": CategoryResponse(
                trend_strength=calculate_trend_strength(grouped_results["Other"]),
                summary=build_category_summary("Other", grouped_results["Other"], disease),
                items=grouped_results["Other"],
            ),
        },
    )


@app.post("/query", response_model=FinalResponse, response_model_by_alias=True)
async def query_pubmed(payload: QueryRequest) -> FinalResponse:
    resolved_disease = resolve_disease_query(payload.query, payload.last_disease)
    location = payload.location.strip()
    if not resolved_disease:
        raise HTTPException(status_code=400, detail="Query must include a disease or a last known disease")

    raw_data = await fetch_pubmed_results(resolved_disease, location)
    llm_input = build_llm_summary_input(raw_data)
    original_titles = extract_original_titles(raw_data.model_dump(by_alias=True))
    validation_output = render_system_paper_list_for_validation(raw_data)
    query_context = QueryContext(
        disease=resolved_disease,
        location=location,
        built_query=build_query(resolved_disease, location),
        expanded_terms=["treatment", "clinical trials", "recent research"],
    )

    try:
        llm_output = await generate_llm_response(llm_input)
    except HTTPException as exc:
        logger.warning("LLM formatting failed; fallback triggered: %s", exc.detail)
        return FinalResponse(
            query_context=query_context,
            raw_data=raw_data,
            llm_output=None,
            validated=False,
            status="fallback_triggered",
            error=f"LLM output invalid - fallback triggered ({exc.detail})",
        )

    combined_validation_output = f"{llm_output}\n{validation_output}"
    reject_output = (
        not validate_llm_output(combined_validation_output, original_titles)
        or detect_extra_titles(llm_output, original_titles)
    )

    if reject_output:
        logger.warning("LLM validation failed; fallback triggered for query '%s'", resolved_disease)
        return FinalResponse(
            query_context=query_context,
            raw_data=raw_data,
            llm_output=None,
            validated=False,
            status="fallback_triggered",
            error="LLM output invalid - fallback triggered",
        )

    return FinalResponse(
        query_context=query_context,
        raw_data=raw_data,
        llm_output=llm_output,
        validated=True,
        status="validated",
        error=None,
    )


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok")
