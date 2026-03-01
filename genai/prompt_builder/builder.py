"""
Prompt Construction Module

Assembles the final prompt payload for Amazon Bedrock from a user query and
retrieved context chunks, enforcing token budget limits and applying
injection-mitigation guardrails.

This module is intentionally side-effect-free (no AWS calls) so that it can be
fully unit-tested without mocking.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from templates import (
    CHARS_PER_TOKEN,
    CONTEXT_MAX_CHARS,
    QUERY_MAX_CHARS,
    RAG_SYSTEM_PROMPT,
    RESTRICTED_SYSTEM_PROMPT,
    SYSTEM_PROMPT_MAX_CHARS,
    citation_user_message,
    rag_user_message,
    summarisation_user_message,
)

logger = logging.getLogger(__name__)

# ── Injection-mitigation patterns ─────────────────────────────────────────────

# Common prompt-injection prefixes/patterns to strip from user queries
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    # Classic instruction override variants
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|above)\s+instructions?", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?(previous|prior|above)\s+instructions?", re.IGNORECASE),
    re.compile(r"override\s+(all\s+)?(previous|prior|above)\s+instructions?", re.IGNORECASE),
    # Role reassignment
    re.compile(r"you\s+are\s+now\s+", re.IGNORECASE),
    re.compile(r"act\s+as\s+(a\s+|an\s+)?(?:different|new|unrestricted)\s+", re.IGNORECASE),
    # Instruction injection markers
    re.compile(r"new\s+instructions?:", re.IGNORECASE),
    re.compile(r"updated\s+instructions?:", re.IGNORECASE),
    re.compile(r"system\s+prompt:", re.IGNORECASE),
    # XML/tag-based injection
    re.compile(r"<\s*/?system\s*>", re.IGNORECASE),
    re.compile(r"<\s*/?instruction\s*>", re.IGNORECASE),
    re.compile(r"<\s*/?prompt\s*>", re.IGNORECASE),
    # Token-style injection markers
    re.compile(r"\[INST\]", re.IGNORECASE),
    re.compile(r"###\s*instruction", re.IGNORECASE),
    re.compile(r"###\s*system", re.IGNORECASE),
]

# ── Token estimation ──────────────────────────────────────────────────────────

def estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in *text* using a conservative heuristic.

    Uses a 4-chars-per-token ratio, which errs on the side of over-counting to
    avoid exceeding model context windows.

    Args:
        text: Input string.

    Returns:
        Estimated token count. Returns 0 for empty strings; returns at least 1
        for any non-empty string.
    """
    if not text:
        return 0
    return max(1, int(len(text) / CHARS_PER_TOKEN))


# ── Injection mitigation ──────────────────────────────────────────────────────

def sanitise_query(query: str) -> str:
    """Remove known prompt-injection patterns from *query*.

    This is a defence-in-depth measure; Bedrock Guardrails configured with
    PROMPT_ATTACK filtering provide the primary mitigation.

    Args:
        query: Raw user query.

    Returns:
        Sanitised query string.
    """
    sanitised = query
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(sanitised):
            logger.warning(
                "Potential prompt injection detected and removed",
                extra={"pattern": pattern.pattern},
            )
            sanitised = pattern.sub("", sanitised).strip()
    return sanitised


# ── Context truncation ────────────────────────────────────────────────────────

def _truncate_context(chunks: list[str], max_chars: int) -> list[str]:
    """Return as many chunks as fit within *max_chars*, truncating the last if needed."""
    selected: list[str] = []
    total = 0
    for chunk in chunks:
        remaining = max_chars - total
        if remaining <= 0:
            break
        if len(chunk) <= remaining:
            selected.append(chunk)
            total += len(chunk)
        else:
            # Partial inclusion: truncate at last complete sentence if possible
            truncated = chunk[:remaining]
            last_period = truncated.rfind(". ")
            if last_period > remaining // 2:
                truncated = truncated[: last_period + 1]
            selected.append(truncated)
            break
    return selected


# ── Prompt assembly ───────────────────────────────────────────────────────────

class PromptBuilder:
    """Assembles a Bedrock-ready prompt payload from a query and context.

    Args:
        mode:              One of ``"rag"`` (default), ``"citation"``,
                           or ``"summarisation"``.
        use_restricted:    Use the stricter system prompt with explicit
                           injection-mitigation language (default: ``True``).
        max_context_chars: Override the default context character limit.
        max_query_chars:   Override the default query character limit.
    """

    _MODES = {
        "rag": rag_user_message,
        "citation": citation_user_message,
        "summarisation": summarisation_user_message,
    }

    def __init__(
        self,
        mode: str = "rag",
        use_restricted: bool = True,
        max_context_chars: int = CONTEXT_MAX_CHARS,
        max_query_chars: int = QUERY_MAX_CHARS,
    ) -> None:
        if mode not in self._MODES:
            raise ValueError(f"mode must be one of {list(self._MODES)}; got {mode!r}")
        self.mode = mode
        self.system_prompt = (
            RESTRICTED_SYSTEM_PROMPT if use_restricted else RAG_SYSTEM_PROMPT
        )
        self.max_context_chars = max_context_chars
        self.max_query_chars = max_query_chars
        self._build_user_message = self._MODES[mode]

    def build(
        self,
        query: str,
        context_chunks: list[str],
        max_tokens: int = 2048,
    ) -> dict[str, Any]:
        """Build and return a Bedrock Claude Messages API payload.

        Steps:
        1. Sanitise query for injection patterns.
        2. Truncate query to character limit.
        3. Truncate context to character limit.
        4. Assemble system + user messages.
        5. Return payload dict with token usage estimate.

        Args:
            query:          End-user question or instruction.
            context_chunks: Retrieved document passages, ranked by relevance.
            max_tokens:     Maximum tokens for the model response.

        Returns:
            Dict with keys ``payload`` (Bedrock body) and ``token_estimate``.

        Raises:
            ValueError: if the query is empty after sanitisation.
        """
        # 1. Sanitise
        query = sanitise_query(query.strip())
        if not query:
            raise ValueError("Query is empty or consists only of injection patterns.")

        # 2. Truncate query
        if len(query) > self.max_query_chars:
            logger.warning(
                "Query truncated from %d to %d chars",
                len(query),
                self.max_query_chars,
            )
            query = query[: self.max_query_chars]

        # 3. Truncate context
        truncated_chunks = _truncate_context(context_chunks, self.max_context_chars)
        if len(truncated_chunks) < len(context_chunks):
            logger.info(
                "Context truncated: %d of %d chunks used",
                len(truncated_chunks),
                len(context_chunks),
            )

        # 4. Assemble user message
        user_message = self._build_user_message(query, truncated_chunks)

        payload: dict[str, Any] = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "system": self.system_prompt,
            "messages": [
                {"role": "user", "content": user_message},
            ],
        }

        # 5. Token estimate (prompt only – response tokens are not known yet)
        prompt_token_estimate = estimate_tokens(self.system_prompt) + estimate_tokens(
            user_message
        )

        logger.info(
            "Prompt assembled",
            extra={
                "mode": self.mode,
                "context_chunks": len(truncated_chunks),
                "prompt_token_estimate": prompt_token_estimate,
                "max_tokens": max_tokens,
            },
        )

        return {
            "payload": payload,
            "token_estimate": {
                "prompt_tokens": prompt_token_estimate,
                "max_response_tokens": max_tokens,
                "total_budget_tokens": prompt_token_estimate + max_tokens,
            },
        }
