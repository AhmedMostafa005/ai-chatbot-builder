from __future__ import annotations

import csv
import io
import json
import re
from html.parser import HTMLParser
from pathlib import Path

import fitz
from docx import Document as DocxDocument

SUPPORTED = {".txt", ".md", ".csv", ".json", ".html", ".htm", ".pdf", ".docx"}

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…؟۔।])\s+")
_BLOCK_TAGS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "table", "td", "th", "ul", "ol", "article", "section", "header", "footer"}
_SKIP_TAGS = {"script", "style", "noscript", "template"}


def extract_text(filename: str, data: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED:
        raise ValueError(f"Unsupported file type: {ext}. Supported: {', '.join(sorted(SUPPORTED))}")
    if ext in {".txt", ".md"}:
        return data.decode("utf-8", errors="replace")
    if ext == ".csv":
        return _csv_to_text(data)
    if ext == ".json":
        return _json_to_text(data)
    if ext in {".html", ".htm"}:
        return _html_to_text(data)
    if ext == ".pdf":
        with fitz.open(stream=data, filetype="pdf") as pdf:
            return "\n".join(page.get_text("text") for page in pdf)
    docx = DocxDocument(io.BytesIO(data))
    return "\n".join(p.text for p in docx.paragraphs)


def _csv_to_text(data: bytes) -> str:
    reader = csv.reader(io.StringIO(data.decode("utf-8-sig", errors="replace")))
    rows = [r for r in reader if any(cell.strip() for cell in r)]
    if not rows:
        return ""
    header = [h.strip() for h in rows[0]]
    lines = [" | ".join(header)]
    for i, row in enumerate(rows[1:], start=1):
        cells = [f"{h}: {c.strip()}" for h, c in zip(header, row) if c.strip()]
        if cells:
            lines.append(f"Row {i}; " + "; ".join(cells))
    return "\n".join(lines)


def _json_to_text(data: bytes) -> str:
    try:
        obj = json.loads(data.decode("utf-8", errors="replace"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return data.decode("utf-8", errors="replace")
    lines: list[str] = []

    def walk(node: object, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}.{key}" if path else str(key))
        elif isinstance(node, list):
            if not node:
                lines.append(f"{path}: []")
            for i, item in enumerate(node):
                walk(item, f"{path}[{i}]")
        else:
            lines.append(f"{path}: {node}" if path else f"{node}")

    walk(obj, "")
    return "\n".join(lines)


class _TextCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in _SKIP_TAGS:
            self.skip += 1
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS and self.skip:
            self.skip -= 1
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip and data.strip():
            self.parts.append(data.strip())


def _html_to_text(data: bytes) -> str:
    collector = _TextCollector()
    collector.feed(data.decode("utf-8", errors="replace"))
    return " ".join(collector.parts)


def _split_sentences(paragraph: str) -> list[str]:
    parts = [s.strip() for s in _SENTENCE_SPLIT.split(paragraph) if s.strip()]
    return parts or ([paragraph.strip()] if paragraph.strip() else [])


def chunk_text(text: str, size: int = 900, overlap: int = 150) -> list[str]:
    if size < 1 or not text or not text.strip():
        return []
    overlap = max(0, min(overlap, size - 1))
    paragraphs = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n{2,}", text)]
    paragraphs = [p for p in paragraphs if p]
    if not paragraphs:
        paragraphs = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines()]
        paragraphs = [p for p in paragraphs if p]
    if not paragraphs:
        paragraphs = [" ".join(text.split())]

    chunks: list[str] = []
    current = ""

    def flush() -> None:
        nonlocal current
        if current:
            chunks.append(current)

    for paragraph in paragraphs:
        for sentence in _split_sentences(paragraph):
            if len(sentence) > size:
                flush()
                current = ""
                _emit_windows(sentence, size, overlap, chunks)
                continue
            if not current:
                current = sentence
            elif len(current) + len(sentence) + 1 <= size:
                current = f"{current} {sentence}"
            else:
                allowed = size - len(sentence) - 1
                tail = current[-allowed:] if allowed > overlap else (current[-overlap:] if overlap else "")
                flush()
                current = f"{tail} {sentence}".strip()
    flush()
    return chunks


def _emit_windows(text: str, size: int, overlap: int, chunks: list[str]) -> None:
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(start + 1, end - overlap)
