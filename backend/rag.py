"""
Core RAG logic:
1. chunk_text()       -> potong teks panjang jadi chunk kecil
2. RagStore           -> kelola FAISS index + metadata chunk (simpan/load dari disk)
3. generate_answer()  -> panggil Gemini (Google AI Studio) buat jawab pakai context
"""
import os
import json
import uuid
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from google import genai

# ---------- Konfigurasi ----------
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
EMBED_DIM = 384  # dimensi output all-MiniLM-L6-v2
CHUNK_SIZE = 500      # karakter per chunk
CHUNK_OVERLAP = 80    # overlap antar chunk biar konteks nggak putus

STORAGE_DIR = os.path.join(os.path.dirname(__file__), "storage")
INDEX_PATH = os.path.join(STORAGE_DIR, "faiss.index")
CHUNKS_PATH = os.path.join(STORAGE_DIR, "chunks.json")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-flash-latest"

_embed_model = None


def get_embed_model():
    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer(EMBED_MODEL_NAME)
    return _embed_model


def chunk_text(text: str, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Potong teks jadi list chunk string, dengan overlap karakter."""
    text = text.strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


class RagStore:
    """Wrapper buat FAISS index + metadata chunk, auto persist ke disk."""

    def __init__(self):
        os.makedirs(STORAGE_DIR, exist_ok=True)
        self.chunks = []  # list of dict: {id, text, source, page, subject}
        if os.path.exists(INDEX_PATH) and os.path.exists(CHUNKS_PATH):
            self.index = faiss.read_index(INDEX_PATH)
            with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
                self.chunks = json.load(f)
        else:
            self.index = faiss.IndexFlatL2(EMBED_DIM)

    def _save(self):
        faiss.write_index(self.index, INDEX_PATH)
        with open(CHUNKS_PATH, "w", encoding="utf-8") as f:
            json.dump(self.chunks, f, ensure_ascii=False, indent=2)

    def add_document(self, pages: list, source: str, subject: str = "umum"):
        """
        pages: list of {"page": int, "text": str}
        Chunking tiap halaman, lalu embed & masukin ke index.
        """
        model = get_embed_model()
        new_texts = []
        new_meta = []

        for p in pages:
            for chunk in chunk_text(p["text"]):
                new_texts.append(chunk)
                new_meta.append({
                    "id": str(uuid.uuid4()),
                    "text": chunk,
                    "source": source,
                    "page": p["page"],
                    "subject": subject,
                })

        if not new_texts:
            return 0

        embeddings = model.encode(new_texts, convert_to_numpy=True, normalize_embeddings=True)
        self.index.add(embeddings.astype("float32"))
        self.chunks.extend(new_meta)
        self._save()
        return len(new_texts)

    def search(self, query: str, top_k: int = 4, subject: str = None):
        if self.index.ntotal == 0:
            return []
        model = get_embed_model()
        q_emb = model.encode([query], convert_to_numpy=True, normalize_embeddings=True).astype("float32")

        # Ambil lebih banyak kandidat kalau mau filter subject
        fetch_k = top_k * 4 if subject else top_k
        distances, indices = self.index.search(q_emb, min(fetch_k, self.index.ntotal))

        results = []
        for idx in indices[0]:
            if idx == -1 or idx >= len(self.chunks):
                continue
            meta = self.chunks[idx]
            if subject and meta["subject"] != subject:
                continue
            results.append(meta)
            if len(results) >= top_k:
                break
        return results

    def list_subjects(self):
        return sorted(set(c["subject"] for c in self.chunks))


_store = None


def get_store() -> RagStore:
    global _store
    if _store is None:
        _store = RagStore()
    return _store


def generate_answer(question: str, context_chunks: list) -> str:
    """Kirim pertanyaan + context ke Gemini (Google AI Studio), return jawaban teks."""
    if not GEMINI_API_KEY:
        return "[ERROR] GEMINI_API_KEY belum di-set di environment variable."

    if not context_chunks:
        return "Maaf, aku belum nemu materi yang relevan di dokumen yang kamu upload buat jawab pertanyaan ini."

    context_text = "\n\n".join(
        f"[Sumber: {c['source']}, halaman {c['page']}]\n{c['text']}"
        for c in context_chunks
    )

    prompt = f"""Kamu adalah asisten belajar untuk mahasiswa. Jawab pertanyaan HANYA berdasarkan konteks materi kuliah di bawah ini.
Jika jawabannya tidak ada di konteks, katakan dengan jujur bahwa materi yang diupload belum membahas itu, jangan mengarang.
Jawab dengan bahasa yang jelas dan mudah dipahami mahasiswa.

KONTEKS MATERI:
{context_text}

PERTANYAAN MAHASISWA:
{question}

JAWABAN:"""

    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )
    return response.text