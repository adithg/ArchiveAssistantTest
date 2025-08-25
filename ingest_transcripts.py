import os
import csv
import re
from pathlib import Path
from typing import List, Tuple
import argparse

from dotenv import load_dotenv

from langchain.schema import Document
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore

try:
    from pinecone import Pinecone
except Exception:  # pragma: no cover
    Pinecone = None  # type: ignore


SENT_SPLIT_RE = re.compile(r"(?<=[.!?])[\]\)\"']?\s+(?=[A-Z0-9\"'\(\[])")


def split_sentences(text: str) -> List[str]:
    """Lightweight sentence splitter without NLTK."""
    if not text:
        return []
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []
    parts = SENT_SPLIT_RE.split(cleaned)
    sentences: List[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if sentences and len(part) < 30:
            sentences[-1] = (sentences[-1] + " " + part).strip()
        else:
            sentences.append(part)
    return sentences


def load_txt_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def load_csv_file(path: Path) -> str:
    # Heuristic: select the text-like column by highest average token length
    rows: List[List[str]] = []
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if row:
                rows.append(row)
    if not rows:
        return ""

    num_cols = max(len(r) for r in rows)
    if num_cols == 1:
        return "\n".join(r[0] for r in rows if r and r[0].strip())

    # Score columns: choose the one that looks like sentence text
    def score_col(idx: int) -> float:
        values = [r[idx] for r in rows if len(r) > idx and r[idx].strip()]
        if not values:
            return 0.0
        avg_len = sum(len(v) for v in values) / len(values)
        punct = sum(v.count(". ") + v.count("? ") + v.count("! ") for v in values) / max(len(values), 1)
        return avg_len + 20 * punct

    best_idx = max(range(num_cols), key=score_col)
    text_lines = [r[best_idx].strip() for r in rows if len(r) > best_idx and r[best_idx].strip()]
    return "\n".join(text_lines)


def iter_transcripts(transcripts_dir: Path) -> List[Tuple[str, str, dict]]:
    results: List[Tuple[str, str, dict]] = []
    for path in sorted(transcripts_dir.glob("**/*")):
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        if ext not in {".txt", ".csv"}:
            continue

        try:
            if ext == ".txt":
                content = load_txt_file(path)
            else:
                content = load_csv_file(path)
        except Exception as e:  # noqa: BLE001
            print(f"Skip {path.name}: load error {e}")
            continue

        teaching_name = path.stem.strip()
        meta = {"source": str(path), "teaching_name": teaching_name, "filename": path.name}
        results.append((teaching_name, content, meta))
    return results


def parse_csv_rows(csv_path: Path) -> List[dict]:
    rows: List[dict] = []
    with csv_path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        # Normalize fieldnames
        field_map = {fn: (fn or "").strip().lower().replace(" ", "") for fn in (reader.fieldnames or [])}
        # Identify likely columns
        start_key = next((k for k, v in field_map.items() if v in {"starttime", "start", "start_seconds", "startsec"}), None)
        end_key = next((k for k, v in field_map.items() if v in {"endtime", "end", "end_seconds", "endsec"}), None)
        text_key = next((k for k, v in field_map.items() if v in {"transcript", "text", "content"}), None)
        if text_key is None:
            # fall back to longest-looking column if not named clearly
            sample = next(reader, None)
            if sample is None:
                return rows
            cols = list(sample.keys())
            best = max(cols, key=lambda c: len((sample.get(c) or "")))
            text_key = best
            # rewind by re-creating reader
            f.seek(0)
            reader = csv.DictReader(f)
        for r in reader:
            text = (r.get(text_key) or "").strip()
            if not text:
                continue
            def to_float(val):
                try:
                    return float(val)
                except Exception:
                    return None
            start = to_float(r.get(start_key)) if start_key else None
            end = to_float(r.get(end_key)) if end_key else None
            rows.append({"start": start, "end": end, "text": text})
    return rows


def chunk_by_sentences(
    text: str,
    window_size: int = 5,
    step_size: int = 3,
    max_chars: int = 3500,
) -> List[str]:
    def split_long(s: str) -> List[str]:
        if len(s) <= max_chars:
            return [s]
        parts: List[str] = []
        start = 0
        while start < len(s):
            end = min(len(s), start + max_chars)
            # try to break at last whitespace before end
            space = s.rfind(" ", start, end)
            if space != -1 and space > start + max_chars * 0.6:
                end = space
            parts.append(s[start:end].strip())
            start = end
        return [p for p in parts if p]

    raw_sentences = [s.strip() for s in split_sentences(text) if s.strip()]
    sentences: List[str] = []
    for s in raw_sentences:
        sentences.extend(split_long(s))
    if not sentences:
        return []

    chunks: List[str] = []
    i = 0
    while i < len(sentences):
        window = sentences[i : i + window_size]
        if not window:
            break
        # Build chunk respecting max_chars limit
        chunk_parts: List[str] = []
        total = 0
        for s in window:
            s_len = len(s) + (1 if chunk_parts else 0)
            if total + s_len > max_chars and chunk_parts:
                break
            chunk_parts.append(s)
            total += s_len
        chunk = " ".join(chunk_parts)
        # Guard against extremely short chunks (e.g., headings)
        if len(chunk) < 80 and i + window_size < len(sentences):
            i += 1
            continue
        chunks.append(chunk)
        if i + window_size >= len(sentences):
            break
        i += step_size
    return chunks


def ensure_index(index_name: str, dimension: int = 1536):
    if Pinecone is None:
        return
    try:
        pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        existing = set(pc.list_indexes().names())
        if index_name not in existing:
            pc.create_index(name=index_name, dimension=dimension, metric="cosine")
            print(f"Created Pinecone index: {index_name}")
    except Exception as e:  # noqa: BLE001
        print(f"Index check/create skipped or failed: {e}")


def build_documents(transcripts_dir: Path, window_size: int, step_size: int, max_chars: int) -> List[Document]:
    docs: List[Document] = []
    for teaching_name, content, meta in iter_transcripts(transcripts_dir):
        source_path = Path(meta["source"]) 
        if source_path.suffix.lower() == ".csv":
            rows = parse_csv_rows(source_path)
            if not rows:
                continue
            i = 0
            idx = 0
            while i < len(rows):
                window = rows[i : i + window_size]
                if not window:
                    break
                texts = [r["text"] for r in window]
                start_vals = [r["start"] for r in window if r.get("start") is not None]
                end_vals = [r["end"] for r in window if r.get("end") is not None]
                start_sec = min(start_vals) if start_vals else None
                end_sec = max(end_vals) if end_vals else None
                header = ""
                if start_sec is not None and end_sec is not None:
                    header = f"Timestamp: {start_sec}-{end_sec}\n"
                elif start_sec is not None:
                    header = f"Timestamp: {start_sec}\n"
                chunk = header + " ".join(texts)
                md = dict(meta)
                md["chunk_index"] = idx
                if start_sec is not None:
                    md["start_seconds"] = float(start_sec)
                if end_sec is not None:
                    md["end_seconds"] = float(end_sec)
                docs.append(Document(page_content=chunk, metadata=md))
                idx += 1
                if i + window_size >= len(rows):
                    break
                i += step_size
        else:
            for idx, chunk in enumerate(chunk_by_sentences(content, window_size=window_size, step_size=step_size, max_chars=max_chars)):
                md = dict(meta)
                md["chunk_index"] = idx
                # Ensure keys exist for document_prompt formatting
                md.setdefault("start_seconds", None)
                md.setdefault("end_seconds", None)
                docs.append(Document(page_content=chunk, metadata=md))
    return docs


def main():
    parser = argparse.ArgumentParser(description="Ingest transcripts into Pinecone with adjustable chunking")
    parser.add_argument("--window-size", type=int, default=5, help="Number of sentences per chunk (default: 5)")
    parser.add_argument("--step-size", type=int, default=2, help="Sentence stride between chunks (default: 2)")
    parser.add_argument("--max-chars", type=int, default=3500, help="Max characters per chunk (default: 3500)")
    parser.add_argument("--reset-index", action="store_true", help="Delete all existing vectors in the index before ingesting")
    args = parser.parse_args()
    load_dotenv()
    os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "")
    os.environ["PINECONE_API_KEY"] = os.getenv("PINECONE_API_KEY", "")

    transcripts_dir = Path.cwd() / "Transcripts"
    index_name = os.getenv("PINECONE_INDEX", "archiveassistanttest")

    ensure_index(index_name)

    print(f"Loading transcripts from: {transcripts_dir}")
    documents = build_documents(transcripts_dir, window_size=args.window_size, step_size=args.step_size, max_chars=args.max_chars)
    if not documents:
        print("No documents prepared. Aborting.")
        return
    print(f"Prepared {len(documents)} chunks. Uploading to Pinecone index '{index_name}'...")

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vectorstore = PineconeVectorStore(index_name=index_name, embedding=embeddings)

    if args.reset_index and Pinecone is not None:
        try:
            pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
            index = pc.Index(index_name)
            # Try both parameter names for compatibility
            try:
                index.delete(delete_all=True)
            except TypeError:
                index.delete(deleteAll=True)
            print("Cleared existing vectors from index.")
        except Exception as e:
            print(f"Warning: could not clear index: {e}")

    # Batch by approximate token count to avoid 300k token/request limit
    MAX_TOKENS_PER_BATCH = 200_000
    MAX_CHARS_PER_BATCH = MAX_TOKENS_PER_BATCH * 4

    batch: List[Document] = []
    char_sum = 0
    uploaded = 0
    for doc in documents:
        text_len = len(doc.page_content)
        if batch and char_sum + text_len > MAX_CHARS_PER_BATCH:
            vectorstore.add_documents(batch)
            uploaded += len(batch)
            print(f"Uploaded {uploaded}/{len(documents)}...")
            batch, char_sum = [], 0
        batch.append(doc)
        char_sum += text_len

    if batch:
        vectorstore.add_documents(batch)
        uploaded += len(batch)
        print(f"Uploaded {uploaded}/{len(documents)}...")
    print("Upload complete.")


if __name__ == "__main__":
    main()


