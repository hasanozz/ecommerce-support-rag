from __future__ import annotations

from backend.app.config import get_settings
from backend.app.rag.chunking import create_chunks


def main() -> None:
    settings = get_settings()
    input_path = settings.processed_data_path / "rag_documents.jsonl"
    output_path = settings.processed_data_path / "rag_chunks.jsonl"
    chunks = create_chunks(input_path, output_path)
    print(f"CHUNKS_OK documents={sum(1 for _ in input_path.open(encoding='utf-8'))} chunks={len(chunks)}")


if __name__ == "__main__":
    main()
