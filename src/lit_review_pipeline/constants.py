"""Constants shared across the pipeline."""

from __future__ import annotations

REQUIRED_COLUMNS: list[str] = [
    "id",
    "title",
    "abstract",
    "doi",
    "publication_year",
    "type",
]

MANUFACTURING_KEYWORDS: tuple[str, ...] = (
    "manufacturing",
    "factory",
    "production line",
    "industrial",
    "supply chain",
    "assembly",
    "shop floor",
    "predictive maintenance",
    "quality control",
    "process optimization",
)

STRUCTURED_FIELDS: list[str] = [
    "use_cases",
    "opportunities",
    "challenges",
    "ai_category",
    "business_function",
    "technical_complexity",
    "roi_impact",
    "time_horizon",
    "industry_segment",
    "implementation_stage",
    "data_requirements",
    "model_family",
    "deployment_pattern",
    "human_in_the_loop",
    "risk_factors",
    "compliance_considerations",
    "kpis",
    "stakeholders",
    "cost_profile",
    "scalability",
    "integration_complexity",
    "confidence_score",
    "concise_summary",
]
