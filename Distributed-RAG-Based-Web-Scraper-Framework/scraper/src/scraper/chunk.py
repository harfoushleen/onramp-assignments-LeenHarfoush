"""Chunking step: splits a ProcessedPage's text + tables into overlap-based
chunks ready for embedding.

Overlap-based rather than naive fixed-length splitting: a hard cut at exactly
CHUNK_SIZE_CHARS characters can slice a sentence (or a fact) in half, so
whichever chunk retrieval picks up loses the context on the other side of the
cut. Carrying CHUNK_OVERLAP_CHARS characters over into the next chunk means a
fact sitting near a boundary is very likely to appear whole in at least one
chunk, at the cost of ~15% storage/embedding redundancy -- a reasonable
trade for this project's scale.

Character-based (not token-based) sizing: nomic-embed-text has an 8192-token
context window, far larger than a 500-character chunk could ever fill, so
overshooting slightly on token count is never a real risk here. Counting
characters avoids pulling in a tokenizer dependency purely to size chunks.

Table chunking (discussed and confirmed): a table's key-value pairs are
serialized into a single chunk's text as "Key: Value" lines, one table per
chunk, appended after the body-text chunks. Tables from this project's sites
are small (a handful of rows) and always comfortably under CHUNK_SIZE_CHARS,
so they're treated as atomic -- no overlap splitting applied to them -- and
kept as a plain chunk_text rather than a separate schema concept, since
nothing downstream needs to treat a table chunk differently from a text
chunk at query time.
"""

CHUNK_SIZE_CHARS = 500
CHUNK_OVERLAP_CHARS = 75  # 15% of CHUNK_SIZE_CHARS


def chunk_text(
    text: str, chunk_size: int = CHUNK_SIZE_CHARS, overlap: int = CHUNK_OVERLAP_CHARS
) -> list[str]:
    """Splits `text` into overlapping chunks. Each chunk after the first
    starts `chunk_size - overlap` characters after the previous chunk
    started, so consecutive chunks share `overlap` characters of context.
    Returns an empty list for empty/whitespace-only input.
    """
    text = text.strip()
    if not text:
        return []
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap")

    stride = chunk_size - overlap
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start += stride
    return chunks


def serialize_table(table: dict[str, str]) -> str:
    """Formats a table's key-value pairs as one "Key: Value" line per row."""
    return "\n".join(f"{key}: {value}" for key, value in table.items())


def chunk_processed_page(text: str, tables: list[dict[str, str]]) -> list[str]:
    """Builds the full ordered list of chunk texts for a processed page:
    overlap-based chunks of the body text, followed by one atomic chunk per
    table. Order matters only insofar as it determines chunk_index -- the
    body/table split itself is not otherwise significant downstream.
    """
    chunks = chunk_text(text)
    for table in tables:
        serialized = serialize_table(table)
        if serialized:
            chunks.append(serialized)
    return chunks
