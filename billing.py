"""
billing.py – Cost estimation, credit conversion and credit debit helpers.

Pricing variables are read from environment (with sensible defaults).
"""

import os
from typing import Dict, Any, Optional

# ---------------------------------------------------------------------------
# Pricing constants (loaded from environment)
# ---------------------------------------------------------------------------

AMAZON_S3_GO_PRICE              = float(os.environ.get("AMAZON_S3_GO_PRICE",              "0.023"))
AMAZON_S3_PUT_REQUEST_PRICE     = float(os.environ.get("AMAZON_S3_PUT_REQUEST_PRICE",     "0.005"))
AMAZON_S3_COPY_REQUEST_PRICE    = float(os.environ.get("AMAZON_S3_COPY_REQUEST_PRICE",    "0.005"))
AMAZON_S3_GET_REQUEST_PRICE     = float(os.environ.get("AMAZON_S3_GET_REQUEST_PRICE",     "0.0004"))
AMAZON_S3_DELETE_REQUEST_PRICE  = float(os.environ.get("AMAZON_S3_DELETE_REQUEST_PRICE",  "0.0004"))
AMAZON_S3_POST_REQUEST_PRICE    = float(os.environ.get("AMAZON_S3_POST_REQUEST_PRICE",    "0.005"))
AMAZON_S3_LIST_REQUEST_PRICE    = float(os.environ.get("AMAZON_S3_LIST_REQUEST_PRICE",    "0.0004"))

DATA_IMPULSE_PRICE_BY_GO        = float(os.environ.get("DATA_IMPULSE_PRICE_BY_GO",        "1"))
VIREEL_VPS_PRICE_BY_MINUTE       = float(os.environ.get("VIREEL_VPS_PRICE_BY_MINUTE",       "0.01"))

ASSEMBLY_ESTIMATE_COST_PER_MINUTE = float(os.environ.get("ASSEMBLY_ESTIMATE_COST_PER_MINUTE", "0.21"))
OPEN_IA_INPUT_TOKEN_PER_DOLLAR    = float(os.environ.get("OPEN_IA_INPUT_TOKEN_PER_DOLLAR", "400000"))
OPEN_IA_OUTPUT_TOKEN_PER_DOLLAR   = float(os.environ.get("OPEN_IA_OUTPUT_TOKEN_PER_DOLLAR", "100000"))
GEMINI_INPUT_TOKEN_PER_DOLLAR     = float(os.environ.get("GEMINI_INPUT_TOKEN_PER_DOLLAR", "1000000"))
GEMINI_OUTPUT_TOKEN_PER_DOLLAR    = float(os.environ.get("GEMINI_OUTPUT_TOKEN_PER_DOLLAR", "200000"))


# 1 USD = CREDIT_UNIT_PRICE_BY_DOLLAR credits
CREDIT_UNIT_PRICE_BY_DOLLAR     = float(os.environ.get("CREDIT_UNIT_PRICE_BY_DOLLAR",     "100"))
# Final price majoration factor applied to all user-facing credit costs
VIREEL_PRICE_MAJORATION         = float(os.environ.get("VIREEL_PRICE_MAJORATION",         "2.0"))


# ---------------------------------------------------------------------------
# Core converters
# ---------------------------------------------------------------------------

def usd_to_credits(amount_usd: float) -> float:
    """Convert a USD amount to credits."""
    return round(float(amount_usd) * CREDIT_UNIT_PRICE_BY_DOLLAR, 2)


def apply_majoration(credits: float) -> float:
    """Apply the platform majoration factor to a credit amount."""
    return round(float(credits) * VIREEL_PRICE_MAJORATION, 2)


def usd_to_final_credits(amount_usd: float) -> float:
    """Full pipeline: USD → credits → majoated credits."""
    return apply_majoration(usd_to_credits(amount_usd))


def estimate_llm_usage_cost_usd(provider: str, input_tokens: float, output_tokens: float) -> float:
    """Compute real-time LLM cost from token usage and token-per-dollar env vars."""
    p = (provider or "").strip().lower()
    in_tokens = max(0.0, float(input_tokens or 0.0))
    out_tokens = max(0.0, float(output_tokens or 0.0))

    if p == "openai":
        in_per_dollar = max(1.0, OPEN_IA_INPUT_TOKEN_PER_DOLLAR)
        out_per_dollar = max(1.0, OPEN_IA_OUTPUT_TOKEN_PER_DOLLAR)
    elif p == "gemini":
        in_per_dollar = max(1.0, GEMINI_INPUT_TOKEN_PER_DOLLAR)
        out_per_dollar = max(1.0, GEMINI_OUTPUT_TOKEN_PER_DOLLAR)
    else:
        return 0.0

    return round((in_tokens / in_per_dollar) + (out_tokens / out_per_dollar), 6)


# ---------------------------------------------------------------------------
# Cost estimation helpers
# ---------------------------------------------------------------------------

def estimate_reel_cost_usd(
    duration_minutes: float = 5.0,
    video_size_gb: float = 0.5,
    uses_youtube_download: bool = False,
    youtube_download_gb: float = 0.0,
    uses_openai: bool = True,
    uses_assembly: bool = False,
    uses_gemini: bool = False,
) -> Dict[str, Any]:
    """Estimate the USD cost of a reel generation operation.

    Returns a dict with a ``total_usd`` key and per-service breakdowns.
    """
    # S3 costs: storage month + basic requests
    s3_usd = (
        video_size_gb * AMAZON_S3_GO_PRICE
        + 1 * AMAZON_S3_PUT_REQUEST_PRICE
        + 2 * AMAZON_S3_GET_REQUEST_PRICE
        + 1 * AMAZON_S3_LIST_REQUEST_PRICE
    )

    vps_usd = duration_minutes * VIREEL_VPS_PRICE_BY_MINUTE

    dataimpulse_usd = (
        youtube_download_gb * DATA_IMPULSE_PRICE_BY_GO
        if uses_youtube_download and youtube_download_gb > 0
        else 0.0
    )

    assembly_usd = duration_minutes * ASSEMBLY_ESTIMATE_COST_PER_MINUTE if uses_assembly else 0.0
    # Real OpenAI/Gemini costs are billed from exact token usage at runtime.
    openai_usd = 0.0 if uses_openai else 0.0
    gemini_usd = 0.0 if uses_gemini else 0.0

    total_usd = s3_usd + vps_usd + dataimpulse_usd + assembly_usd + openai_usd + gemini_usd

    return {
        "s3_usd":           round(s3_usd,           6),
        "vps_usd":          round(vps_usd,           6),
        "dataimpulse_usd":  round(dataimpulse_usd,   6),
        "assembly_usd":     round(assembly_usd,      6),
        "openai_usd":       round(openai_usd,        6),
        "gemini_usd":       round(gemini_usd,        6),
        "total_usd":        round(total_usd,         6),
    }


def estimate_caption_cost_usd(
    duration_minutes: float = 5.0,
    video_size_gb: float = 0.5,
    uses_assembly: bool = True,
    uses_openai: bool = True,
    uses_gemini: bool = False,
) -> Dict[str, Any]:
    """Estimate the USD cost of a caption generation operation."""
    s3_usd = (
        video_size_gb * AMAZON_S3_GO_PRICE
        + 1 * AMAZON_S3_PUT_REQUEST_PRICE
        + 2 * AMAZON_S3_GET_REQUEST_PRICE
    )
    vps_usd      = duration_minutes * VIREEL_VPS_PRICE_BY_MINUTE
    assembly_usd = duration_minutes * ASSEMBLY_ESTIMATE_COST_PER_MINUTE if uses_assembly else 0.0
    # Real OpenAI/Gemini costs are billed from exact token usage at runtime.
    openai_usd = 0.0 if uses_openai else 0.0
    gemini_usd = 0.0 if uses_gemini else 0.0
    total_usd    = s3_usd + vps_usd + assembly_usd + openai_usd + gemini_usd

    return {
        "s3_usd":           round(s3_usd,       6),
        "vps_usd":          round(vps_usd,       6),
        "dataimpulse_usd":  0.0,
        "assembly_usd":     round(assembly_usd,  6),
        "openai_usd":       round(openai_usd,    6),
        "gemini_usd":       round(gemini_usd,    6),
        "total_usd":        round(total_usd,     6),
    }


def estimate_publication_cost_usd(
    platform_count: int = 1,
    video_size_gb: float = 0.5,
) -> Dict[str, Any]:
    """Estimate the USD cost of a social media publication operation."""
    s3_usd    = (
        video_size_gb * AMAZON_S3_GO_PRICE
        + platform_count * AMAZON_S3_GET_REQUEST_PRICE
    )
    vps_usd   = 1.0 * VIREEL_VPS_PRICE_BY_MINUTE
    total_usd = s3_usd + vps_usd

    return {
        "s3_usd":           round(s3_usd,   6),
        "vps_usd":          round(vps_usd,  6),
        "dataimpulse_usd":  0.0,
        "assembly_usd":     0.0,
        "openai_usd":       0.0,
        "gemini_usd":       0.0,
        "total_usd":        round(total_usd, 6),
    }


def calculate_credits_for_operation(cost_breakdown_usd: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a USD cost breakdown dict to credits (with majoration).

    Returns the breakdown enriched with credit fields.
    """
    total_usd     = float(cost_breakdown_usd.get("total_usd", 0.0))
    base_credits  = usd_to_credits(total_usd)
    final_credits = apply_majoration(base_credits)

    return {
        **cost_breakdown_usd,
        "base_credits":      base_credits,
        "majoration_factor": VIREEL_PRICE_MAJORATION,
        "final_credits":     final_credits,
    }


# ---------------------------------------------------------------------------
# Default credit amounts per operation (for simple flat-rate estimate)
# These are computed at module load time from the pricing constants and
# represent a "typical" operation so the frontend can show a quick check.
# ---------------------------------------------------------------------------

DEFAULT_REEL_CREDITS = 1.0
DEFAULT_CAPTION_CREDITS = 1.0
DEFAULT_PUBLICATION_CREDITS = 1.0

