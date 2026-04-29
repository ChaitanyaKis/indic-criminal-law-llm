"""RAG generator — provider-agnostic wrapper over Gemini / Groq / Claude.

Design principles
-----------------
1. **Grounded output.** The system prompt constrains the model to use
   only the supplied retrieved chunks and to decline when the context is
   insufficient. No training-time legal knowledge is welcomed (see
   ``docs/bns_transition_findings.md`` for why).
2. **Mandatory citations.** Every substantive claim must carry a
   ``[doc_id: <id>]`` marker so :func:`verify_citations` can check it.
3. **Provider choice, not provider lock-in.** The three providers below
   are exchangeable; future additions (local Ollama, vLLM) fit the
   same interface.

Default provider: ``"gemini"`` (Gemini 2.5 Flash, AI Studio free tier).
API keys are expected in environment variables, loaded from ``.env``
via ``python-dotenv``.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Literal

from dotenv import load_dotenv

log = logging.getLogger(__name__)

Provider = Literal["gemini", "groq", "claude"]

DEFAULT_PROVIDER: Provider = "gemini"
DEFAULT_MODELS: dict[str, str] = {
    "gemini": "gemini-2.5-flash",
    "groq": "llama-3.1-70b-versatile",
    "claude": "claude-3-5-haiku-latest",
}

_SYSTEM_PROMPT = """You are a legal research assistant for Indian criminal law, answering strictly from retrieved Supreme Court judgment excerpts provided to you.

Rules:
1. Use ONLY information from the retrieved chunks below. Do not draw on legal knowledge from training data.
2. Every claim must carry a citation in the form [doc_id: <id>] right after the claim.
3. If the retrieved chunks do not contain enough information to answer the question, say so plainly: "The retrieved context does not contain enough information to answer this question about X." Do not guess.
4. When the chunks disagree or are ambiguous, surface the disagreement rather than picking one side.
5. Use neutral, Indian legal writing style. Prefer concrete section/case references over generalities.
6. Keep the answer under 250 words unless the question genuinely needs more.

Citation format: attach ``[doc_id: <id>]`` after the relevant sentence. Optionally include a short excerpt: ``[doc_id: <id>, "short quoted phrase"]``. Never invent a doc_id that is not in the retrieved chunks."""


@dataclass
class GenerationResult:
    answer: str
    citations: list[dict[str, Any]]
    model_used: str
    prompt_tokens: int | None
    completion_tokens: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "citations": self.citations,
            "model_used": self.model_used,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
        }


PromptFormat = Literal["numbered", "id_only"]


def _format_chunks_for_prompt(
    retrieved, prompt_format: PromptFormat = "numbered",
) -> str:
    """Flatten retrieved chunks into a prompt-ready context block.

    Two formats supported:

    - ``"numbered"`` (default, current behaviour): each chunk is
      preceded by ``--- Chunk N ---``. The chunk ordinal sits next to
      the doc_id which can occasionally cause an attention-pattern
      collapse where the model emits the chunk number as if it were a
      doc_id (Mode 2 hallucination — see
      ``docs/findings/2026-04-28_hallucination_signal.md``).
    - ``"id_only"``: chunks are separated by a horizontal rule and
      identified only by their doc_id. No ordinal numbering. Treatment
      arm of the Mode 2 hypothesis test.
    """
    lines: list[str] = []
    for i, c in enumerate(retrieved, 1):
        if hasattr(c, "doc_id"):
            did = c.doc_id
            text = c.text
            meta = c.metadata
            score = c.score
        else:
            did = c.get("doc_id", "")
            text = c.get("text", "")
            meta = c.get("metadata") or {}
            score = c.get("score", 0.0)
        title = (meta or {}).get("title") or "(untitled)"
        year = (meta or {}).get("year") or "?"
        if prompt_format == "id_only":
            lines.append(
                f"[doc_id: {did}] (year: {year}, score: {score:.3f})\n"
                f"Title: {title}\n"
                f"{text.strip()}"
            )
        else:  # "numbered"
            lines.append(
                f"--- Chunk {i} "
                f"(doc_id: {did}, year: {year}, score: {score:.3f}) ---\n"
                f"Title: {title}\n"
                f"{text.strip()}"
            )
    sep = "\n\n---\n\n" if prompt_format == "id_only" else "\n\n"
    return sep.join(lines)


def _build_user_prompt(
    question: str, retrieved, prompt_format: PromptFormat = "numbered",
) -> str:
    ctx = _format_chunks_for_prompt(retrieved, prompt_format)
    return (
        f"RETRIEVED CHUNKS:\n\n{ctx}\n\n"
        f"QUESTION: {question}\n\n"
        f"Answer the question using ONLY the retrieved chunks above, with "
        f"citations in the required [doc_id: <id>] format. If the chunks "
        f"are insufficient, say so explicitly."
    )


# ---- Provider adapters -------------------------------------------------


def _call_gemini(
    system: str, user: str, model: str, temperature: float, max_output_tokens: int,
) -> tuple[str, int | None, int | None]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    # Gemini 2.5 family runs an internal "thinking" pass whose tokens
    # count against max_output_tokens. With thinking on, a 1024-token
    # budget routinely yields ~40 visible tokens (the rest is thinking).
    # We disable it (thinking_budget=0) so the entire budget goes to
    # the visible response — RAG answers don't benefit from internal
    # reasoning since the retrieval already does the heavy lifting.
    response = client.models.generate_content(
        model=model,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    text = response.text or ""
    prompt_t = completion_t = None
    usage = getattr(response, "usage_metadata", None)
    if usage is not None:
        prompt_t = getattr(usage, "prompt_token_count", None)
        completion_t = getattr(usage, "candidates_token_count", None)
    return text, prompt_t, completion_t


def _call_groq(
    system: str, user: str, model: str, temperature: float, max_output_tokens: int,
) -> tuple[str, int | None, int | None]:
    from groq import Groq

    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        temperature=temperature,
        max_tokens=max_output_tokens,
    )
    text = resp.choices[0].message.content or ""
    usage = resp.usage
    return text, getattr(usage, "prompt_tokens", None), getattr(usage, "completion_tokens", None)


def _call_claude(
    system: str, user: str, model: str, temperature: float, max_output_tokens: int,
) -> tuple[str, int | None, int | None]:
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = client.messages.create(
        model=model,
        max_tokens=max_output_tokens,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    usage = resp.usage
    return text, getattr(usage, "input_tokens", None), getattr(usage, "output_tokens", None)


_PROVIDERS: dict[str, Callable] = {
    "gemini": _call_gemini,
    "groq": _call_groq,
    "claude": _call_claude,
}


def _is_retryable(exc: BaseException) -> bool:
    """Crude cross-SDK check for transient errors — 429/503 class."""
    msg = str(exc).lower()
    for sig in ("503", "429", "unavailable", "rate limit", "overloaded",
                "resource exhausted", "too many requests"):
        if sig in msg:
            return True
    # google-genai raises specific ServerError/ClientError types
    cls_name = type(exc).__name__
    if cls_name in ("ServerError", "APIStatusError", "RateLimitError"):
        return True
    return False


def _call_with_retry(
    fn: Callable, *args, max_retries: int = 3, base_delay: float = 4.0,
):
    last_exc: BaseException | None = None
    for attempt in range(max_retries + 1):
        try:
            return fn(*args)
        except Exception as e:  # noqa: BLE001
            last_exc = e
            if attempt >= max_retries or not _is_retryable(e):
                raise
            delay = base_delay * (2 ** attempt)
            log.warning(
                "Retryable LLM error on attempt %d (%s); sleeping %.1fs",
                attempt + 1, type(e).__name__, delay,
            )
            time.sleep(delay)
    # Unreachable (loop either returns or raises), but mypy-friendly:
    raise last_exc  # type: ignore[misc]


# ---- Public class ------------------------------------------------------


class RAGGenerator:
    def __init__(
        self,
        provider: Provider = DEFAULT_PROVIDER,
        model: str | None = None,
    ):
        load_dotenv()
        if provider not in _PROVIDERS:
            raise ValueError(f"Unknown provider {provider!r}; choose from {list(_PROVIDERS)}")
        self.provider = provider
        self.model = model or DEFAULT_MODELS[provider]
        self._validate_credentials()

    def _validate_credentials(self) -> None:
        env_key = {
            "gemini": "GEMINI_API_KEY",
            "groq": "GROQ_API_KEY",
            "claude": "ANTHROPIC_API_KEY",
        }[self.provider]
        if not os.environ.get(env_key):
            raise RuntimeError(
                f"Provider {self.provider!r} requires {env_key} to be set "
                "(in .env or the environment)."
            )

    def answer(
        self,
        question: str,
        retrieved_chunks,
        temperature: float = 0.2,
        max_output_tokens: int = 1024,
        prompt_format: PromptFormat = "numbered",
    ) -> GenerationResult:
        if not retrieved_chunks:
            return GenerationResult(
                answer=(
                    "The retrieved context is empty — no relevant chunks were "
                    "found for this query. I cannot answer this question from "
                    "the current corpus."
                ),
                citations=[],
                model_used=self.model,
                prompt_tokens=0,
                completion_tokens=0,
            )

        user = _build_user_prompt(question, retrieved_chunks, prompt_format)
        caller = _PROVIDERS[self.provider]
        text, pt, ct = _call_with_retry(
            caller, _SYSTEM_PROMPT, user, self.model, temperature,
            max_output_tokens,
        )

        # Light post-processing: derive the structured citation list by
        # matching cited doc_ids against chunks and attaching a short excerpt.
        from src.rag.citation_verifier import extract_citations
        cited_ids = extract_citations(text)
        chunks_by_doc: dict[str, list] = {}
        for c in retrieved_chunks:
            did = getattr(c, "doc_id", None) if not isinstance(c, dict) else c.get("doc_id")
            if did is None:
                continue
            chunks_by_doc.setdefault(str(did), []).append(c)
        citations: list[dict[str, Any]] = []
        for did in cited_ids:
            if did in chunks_by_doc:
                first = chunks_by_doc[did][0]
                excerpt = (
                    (getattr(first, "text", None) if not isinstance(first, dict)
                     else first.get("text", "")) or ""
                )[:200].strip().replace("\n", " ")
                score = (getattr(first, "score", None) if not isinstance(first, dict)
                         else first.get("score"))
                citations.append({
                    "doc_id": did,
                    "excerpt": excerpt,
                    "score": round(float(score or 0.0), 4),
                })
            else:
                citations.append({
                    "doc_id": did,
                    "excerpt": None,
                    "score": None,
                    "hallucinated": True,
                })

        return GenerationResult(
            answer=text,
            citations=citations,
            model_used=self.model,
            prompt_tokens=pt,
            completion_tokens=ct,
        )
