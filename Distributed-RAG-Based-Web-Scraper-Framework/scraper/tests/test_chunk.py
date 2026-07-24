from scraper.chunk import chunk_processed_page, chunk_text, serialize_table


def test_chunk_text_splits_long_text_into_multiple_chunks():
    text = "x" * 1200

    chunks = chunk_text(text, chunk_size=500, overlap=75)

    assert len(chunks) > 1
    assert all(len(chunk) <= 500 for chunk in chunks)


def test_chunk_text_consecutive_chunks_share_overlap_content():
    # Distinct characters at each position so we can find the exact overlap.
    text = "".join(chr(ord("a") + (i % 26)) for i in range(1200))

    chunks = chunk_text(text, chunk_size=500, overlap=75)

    first, second = chunks[0], chunks[1]
    # The last `overlap` characters of the first chunk should reappear at
    # the start of the second chunk.
    overlap_slice = first[-75:]
    assert second.startswith(overlap_slice)


def test_chunk_text_short_text_returns_single_chunk():
    chunks = chunk_text("A short sentence that fits in one chunk.", chunk_size=500, overlap=75)

    assert chunks == ["A short sentence that fits in one chunk."]


def test_chunk_text_empty_input_returns_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_chunk_text_rejects_overlap_not_smaller_than_chunk_size():
    try:
        chunk_text("hello", chunk_size=100, overlap=100)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_serialize_table_formats_key_value_lines():
    table = {"UPC": "e00eb4fd15", "Price (excl. tax)": "£51.77"}

    result = serialize_table(table)

    assert result == "UPC: e00eb4fd15\nPrice (excl. tax): £51.77"


def test_chunk_processed_page_appends_serialized_tables_after_text_chunks():
    text = "Short body text."
    tables = [{"UPC": "abc123"}, {"Price": "£10.00"}]

    chunks = chunk_processed_page(text, tables)

    assert chunks == ["Short body text.", "UPC: abc123", "Price: £10.00"]


def test_chunk_processed_page_with_no_tables_only_chunks_text():
    chunks = chunk_processed_page("Just some text.", [])

    assert chunks == ["Just some text."]


def test_chunk_processed_page_skips_empty_tables():
    chunks = chunk_processed_page("Body.", [{}])

    assert chunks == ["Body."]
