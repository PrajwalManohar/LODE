"""Chunk PDF manuals and markdown SOPs for ChromaDB indexing."""

from pathlib import Path

from vein.config import MANUALS_DIR, SOPS_DIR


def chunk_text(
    text: str,
    source: str,
    corpus_type: str,
    instrument_id: str = "",
    section: str = "",
    page: str = "",
    chunk_size: int = 500,
    overlap: int = 80,
) -> list[dict]:
    words = text.split()
    chunks: list[dict] = []
    i = 0
    idx = 0
    while i < len(words):
        piece = " ".join(words[i : i + chunk_size])
        if len(piece.strip()) < 40:
            break
        chunks.append({
            "id": f"{corpus_type}-{source[:20].replace(' ', '-')}-{idx}",
            "source": source,
            "section": section or f"Chunk {idx + 1}",
            "page": page,
            "corpus_type": corpus_type,
            "instrument_id": instrument_id,
            "text": piece.strip(),
        })
        i += chunk_size - overlap
        idx += 1
    return chunks


def load_pdf_chunks(path: Path, source: str, corpus_type: str, instrument_id: str = "") -> list[dict]:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return []

    doc = fitz.open(path)
    all_chunks: list[dict] = []
    for page_num, page in enumerate(doc, start=1):
        text = page.get_text()
        if not text.strip():
            continue
        all_chunks.extend(
            chunk_text(
                text,
                source=source,
                corpus_type=corpus_type,
                instrument_id=instrument_id,
                section=f"Page {page_num}",
                page=str(page_num),
            )
        )
    doc.close()
    return all_chunks


def load_markdown_chunks(path: Path, source: str, corpus_type: str, instrument_id: str = "") -> list[dict]:
    text = path.read_text(encoding="utf-8")
    sections: list[tuple[str, str]] = []
    current_title = path.stem
    current_lines: list[str] = []

    for line in text.splitlines():
        if line.startswith("## "):
            if current_lines:
                sections.append((current_title, "\n".join(current_lines)))
            current_title = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines:
        sections.append((current_title, "\n".join(current_lines)))

    chunks: list[dict] = []
    for title, body in sections:
        chunks.extend(
            chunk_text(
                body,
                source=source,
                corpus_type=corpus_type,
                instrument_id=instrument_id,
                section=title,
            )
        )
    return chunks


def load_corpus_from_disk() -> list[dict]:
    chunks: list[dict] = []
    instrument_map = {
        "xrd": "xrd-d8",
        "sem": "sem-jeol",
        "icp": "icp-ms",
        "furnace": "tube-furnace",
        "rock": "rock-mech",
    }

    for directory, corpus_type in ((MANUALS_DIR, "manual"), (SOPS_DIR, "sop")):
        if not directory.exists():
            continue
        for path in directory.iterdir():
            if path.suffix.lower() == ".pdf":
                inst_id = next((v for k, v in instrument_map.items() if k in path.stem.lower()), "")
                chunks.extend(load_pdf_chunks(path, path.stem, corpus_type, inst_id))
            elif path.suffix.lower() in (".md", ".txt"):
                inst_id = next((v for k, v in instrument_map.items() if k in path.stem.lower()), "")
                chunks.extend(load_markdown_chunks(path, path.stem, corpus_type, inst_id))
    return chunks
