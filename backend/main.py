"""
FastAPI app: endpoint upload materi & chat tanya-jawab (RAG).
Jalankan: uvicorn main:app --reload --port 8000
"""
import os
import shutil
import tempfile

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pdf_utils import extract_text_from_pdf, extract_text_from_plain
from rag import get_store, generate_answer

app = FastAPI(title="StudyMate AI - RAG Backend")

# Izinkan frontend HTML statis (dibuka langsung dari file/local server) manggil API ini
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    question: str
    subject: str | None = None
    top_k: int = 4


@app.get("/")
def root():
    return {"status": "ok", "message": "StudyMate AI backend jalan."}


@app.get("/subjects")
def list_subjects():
    """List semua mata kuliah/subject yang sudah ada materinya."""
    return {"subjects": get_store().list_subjects()}


@app.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    subject: str = Form("umum"),
):
    """Upload PDF atau .txt, lalu di-chunk, embed, dan masuk ke FAISS index."""
    suffix = os.path.splitext(file.filename)[1].lower()
    if suffix not in [".pdf", ".txt"]:
        raise HTTPException(status_code=400, detail="Hanya mendukung file .pdf atau .txt")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        if suffix == ".pdf":
            pages = extract_text_from_pdf(tmp_path)
        else:
            pages = extract_text_from_plain(tmp_path)

        if not pages:
            raise HTTPException(status_code=400, detail="Tidak ada teks yang bisa diekstrak dari file ini.")

        store = get_store()
        n_chunks = store.add_document(pages, source=file.filename, subject=subject)
    finally:
        os.remove(tmp_path)

    return {
        "filename": file.filename,
        "subject": subject,
        "pages_processed": len(pages),
        "chunks_added": n_chunks,
    }


@app.post("/chat")
def chat(req: ChatRequest):
    """Tanya jawab berdasarkan materi yang sudah diupload."""
    store = get_store()
    relevant_chunks = store.search(req.question, top_k=req.top_k, subject=req.subject)
    answer = generate_answer(req.question, relevant_chunks)

    sources = [
        {"source": c["source"], "page": c["page"], "snippet": c["text"][:150] + "..."}
        for c in relevant_chunks
    ]

    return {"answer": answer, "sources": sources}