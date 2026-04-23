"""Semantic, paragraph-aware chunker for Indian court judgments.

Design
------
- Target chunk: 500 tokens (cl100k_base) with 100-token overlap.
- Paragraph boundaries (``\\n\\n``) are respected. The chunker greedily
  packs whole paragraphs until adding the next would exceed the target;
  a new chunk then starts with the last ~``overlap_tokens`` of the
  previous chunk's tail so that retrieval hits on paragraph boundaries
  still return useful context.
- A paragraph that is itself larger than the target is sentence-split
  (regex on sentence-ending punctuation followed by whitespace). We
  never break mid-sentence.
- No special case for mega-judgments; the same greedy loop handles
  500-char docs and 1.8M-char docs alike.

Output
------
Each :class:`Chunk` carries ``chunk_id = "{doc_id}__{chunk_idx:04d}"``
— deterministic, so a second chunking pass over the same judgment
produces identical IDs. This is the pipeline's idempotency guarantee:
downstream Qdrant point IDs derive from ``chunk_id`` via UUID5.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

DEFAULT_TARGET_TOKENS = 500
DEFAULT_OVERLAP_TOKENS = 100
DEFAULT_ENCODING = "cl100k_base"

# Sentence splitter: end-of-sentence punctuation followed by whitespace.
# Kept intentionally simple — heavy-handed NLP sentence splitters mostly
# add failure modes on legal citations ("Cr.P.C." etc.) for no real gain.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    chunk_idx: int
    text: str
    char_start: int
    char_end: int
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def token_count(self) -> int:
        return self.metadata.get("token_count", 0)


@dataclass
class _Piece:
    """Internal unit of chunking — a paragraph or a sentence slice."""

    text: str
    char_start: int
    char_end: int
    tokens: list[int]


class JudgmentChunker:
    def __init__(
        self,
        target_tokens: int = DEFAULT_TARGET_TOKENS,
        overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
        encoding_name: str = DEFAULT_ENCODING,
    ):
        import tiktoken

        if overlap_tokens >= target_tokens:
            raise ValueError("overlap_tokens must be < target_tokens")
        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens
        self.enc = tiktoken.get_encoding(encoding_name)

    # ---- Public API ---------------------------------------------------

    def chunk(self, judgment: dict[str, Any]) -> list[Chunk]:
        doc_id = judgment.get("doc_id")
        if doc_id is None:
            raise ValueError("judgment is missing doc_id")
        text = judgment.get("full_text") or ""
        if not text.strip():
            return []

        pieces = self._split_into_pieces(text)
        if not pieces:
            return []

        meta = self._build_metadata(judgment)
        return self._pack(str(doc_id), pieces, meta)

    # ---- Internal ----------------------------------------------------

    def _split_into_pieces(self, text: str) -> list[_Piece]:
        """Break text into paragraphs, then sub-split any oversize paragraph
        at sentence boundaries. Track char offsets throughout."""
        pieces: list[_Piece] = []
        # Paragraph = content between blank lines (2+ newlines).
        cursor = 0
        for match in re.finditer(r"(.+?)(\n{2,}|$)", text, flags=re.DOTALL):
            para_text = match.group(1)
            para_start = match.start(1)
            para_end = para_start + len(para_text)
            cursor = match.end()

            stripped = para_text.strip()
            if not stripped:
                continue

            toks = self.enc.encode(para_text)
            if len(toks) <= self.target_tokens:
                pieces.append(_Piece(para_text, para_start, para_end, toks))
            else:
                pieces.extend(self._sentence_split(para_text, para_start))
            if cursor >= len(text):
                break
        return pieces

    def _sentence_split(self, para_text: str, para_start: int) -> list[_Piece]:
        """Split an oversize paragraph at sentence boundaries. Each emitted
        piece may still exceed ``target_tokens`` if a single sentence is
        huge (very rare for judgment text)."""
        out: list[_Piece] = []
        # Use split with capture so we keep the whitespace — but easier to
        # just re-find offsets via a running cursor.
        cursor = 0
        last_end = 0
        sentences: list[tuple[int, int, str]] = []
        for m in _SENTENCE_END.finditer(para_text):
            end = m.start()
            if end > last_end:
                sentences.append((last_end, end, para_text[last_end:end]))
                last_end = m.end()
        if last_end < len(para_text):
            sentences.append((last_end, len(para_text), para_text[last_end:]))
        if not sentences:
            # Defensive: fall back to one big piece.
            return [_Piece(para_text, para_start, para_start + len(para_text),
                           self.enc.encode(para_text))]

        # Pack sentences into pieces up to target_tokens.
        buf_start = sentences[0][0]
        buf_end = sentences[0][0]
        buf_toks: list[int] = []
        for s_start, s_end, s_text in sentences:
            s_toks = self.enc.encode(s_text)
            if buf_toks and len(buf_toks) + len(s_toks) > self.target_tokens:
                out.append(_Piece(
                    para_text[buf_start:buf_end],
                    para_start + buf_start,
                    para_start + buf_end,
                    buf_toks,
                ))
                buf_start = s_start
                buf_toks = []
            if not buf_toks:
                buf_start = s_start
            buf_toks.extend(s_toks)
            buf_end = s_end
        if buf_toks:
            out.append(_Piece(
                para_text[buf_start:buf_end],
                para_start + buf_start,
                para_start + buf_end,
                buf_toks,
            ))
        return out

    def _pack(self, doc_id: str, pieces: list[_Piece], metadata: dict) -> list[Chunk]:
        chunks: list[Chunk] = []
        buf: list[_Piece] = []
        buf_tokens = 0

        def emit() -> None:
            nonlocal buf, buf_tokens
            if not buf:
                return
            idx = len(chunks)
            # Contiguous-enough text: join with the original separator gap.
            text = "\n\n".join(p.text.strip() for p in buf if p.text.strip())
            char_start = buf[0].char_start
            char_end = buf[-1].char_end
            chunks.append(Chunk(
                chunk_id=f"{doc_id}__{idx:04d}",
                doc_id=doc_id,
                chunk_idx=idx,
                text=text,
                char_start=char_start,
                char_end=char_end,
                metadata={**metadata, "token_count": buf_tokens},
            ))
            # Seed next buffer with tail-overlap
            tail = self._take_tail(buf, self.overlap_tokens)
            buf = tail
            buf_tokens = sum(len(p.tokens) for p in buf)

        for piece in pieces:
            if buf_tokens + len(piece.tokens) > self.target_tokens and buf:
                emit()
            buf.append(piece)
            buf_tokens += len(piece.tokens)

        # Final chunk (no further overlap needed)
        if buf:
            idx = len(chunks)
            text = "\n\n".join(p.text.strip() for p in buf if p.text.strip())
            chunks.append(Chunk(
                chunk_id=f"{doc_id}__{idx:04d}",
                doc_id=doc_id,
                chunk_idx=idx,
                text=text,
                char_start=buf[0].char_start,
                char_end=buf[-1].char_end,
                metadata={**metadata, "token_count": buf_tokens},
            ))
        return chunks

    def _take_tail(self, pieces: list[_Piece], overlap_tokens: int) -> list[_Piece]:
        """Return the suffix of ``pieces`` whose total token count is
        approximately ``overlap_tokens``. Takes whole pieces where they
        fit, and sub-slices the boundary piece (via token-level re-decode)
        so the overlap cap is honoured even when the boundary piece is
        itself near target size."""
        if overlap_tokens <= 0 or not pieces:
            return []
        running = 0
        out: list[_Piece] = []
        for piece in reversed(pieces):
            if running >= overlap_tokens:
                break
            needed = overlap_tokens - running
            if len(piece.tokens) <= needed:
                out.append(piece)
                running += len(piece.tokens)
                continue
            # Sub-slice the tail of this piece so the overlap caps cleanly.
            tail_tokens = piece.tokens[-needed:]
            tail_text = self.enc.decode(tail_tokens)
            tail_char_end = piece.char_end
            tail_char_start = max(piece.char_start, piece.char_end - len(tail_text))
            out.append(_Piece(
                text=tail_text,
                char_start=tail_char_start,
                char_end=tail_char_end,
                tokens=tail_tokens,
            ))
            running += len(tail_tokens)
            break
        out.reverse()
        return out

    @staticmethod
    def _build_metadata(judgment: dict[str, Any]) -> dict[str, Any]:
        """Extract the vector-payload-relevant fields from the judgment dict."""
        statutes = judgment.get("statutes_cited") or []
        acts: list[str] = []
        seen_acts: set[str] = set()
        for s in statutes:
            act = s.get("act")
            if act and act not in seen_acts:
                seen_acts.add(act)
                acts.append(act)
        year: int | None = None
        date = judgment.get("date")
        if isinstance(date, str) and len(date) >= 4 and date[:4].isdigit():
            year = int(date[:4])
        has_ipc_302 = any(
            s.get("act") == "IPC" and s.get("section") == "302" for s in statutes
        )
        return {
            "title": judgment.get("title"),
            "court": judgment.get("court"),
            "date": date,
            "year": year,
            "statutes_cited_acts": acts,
            "has_ipc_302": has_ipc_302,
        }
