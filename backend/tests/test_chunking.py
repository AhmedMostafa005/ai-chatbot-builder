from app.services.documents import chunk_text

def test_chunk_text_empty():
    assert chunk_text("  \n ") == []

def test_chunk_text_preserves_content_and_overlap():
    text = "a" * 2200
    chunks = chunk_text(text, size=900, overlap=150)
    assert len(chunks) >= 2
    assert all(chunks)
    assert "".join([]) == ""
    assert chunks[0][-150:] == chunks[1][:150]
