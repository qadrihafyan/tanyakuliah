// Ganti ini kalau backend kamu jalan di alamat/port lain
const API_BASE = "http://127.0.0.1:8000";

const uploadForm = document.getElementById("upload-form");
const uploadBtn = document.getElementById("upload-btn");
const uploadStatus = document.getElementById("upload-status");
const subjectInput = document.getElementById("subject-input");
const fileInput = document.getElementById("file-input");
const subjectListEl = document.getElementById("subject-list");
const subjectFilter = document.getElementById("subject-filter");

const chatForm = document.getElementById("chat-form");
const questionInput = document.getElementById("question-input");
const chatWindow = document.getElementById("chat-window");

// ---------- Subjects ----------
async function refreshSubjects() {
  try {
    const res = await fetch(`${API_BASE}/subjects`);
    const data = await res.json();
    const subjects = data.subjects || [];

    subjectListEl.innerHTML = subjects.length
      ? subjects.map(s => `<li>${s}</li>`).join("")
      : `<li style="color:#999;">Belum ada materi.</li>`;

    const currentValue = subjectFilter.value;
    subjectFilter.innerHTML = `<option value="">Semua mata kuliah</option>` +
      subjects.map(s => `<option value="${s}">${s}</option>`).join("");
    subjectFilter.value = currentValue;
  } catch (err) {
    console.error("Gagal ambil daftar subjects:", err);
  }
}

// ---------- Upload ----------
uploadForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const file = fileInput.files[0];
  const subject = subjectInput.value.trim() || "umum";
  if (!file) return;

  uploadBtn.disabled = true;
  uploadStatus.textContent = "Memproses dokumen... (chunking + embedding)";

  const formData = new FormData();
  formData.append("file", file);
  formData.append("subject", subject);

  try {
    const res = await fetch(`${API_BASE}/upload`, { method: "POST", body: formData });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Upload gagal");
    }
    const data = await res.json();
    uploadStatus.textContent = `✓ "${data.filename}" diproses: ${data.chunks_added} bagian materi tersimpan.`;
    uploadForm.reset();
    refreshSubjects();
  } catch (err) {
    uploadStatus.textContent = `✗ ${err.message}`;
  } finally {
    uploadBtn.disabled = false;
  }
});

// ---------- Chat ----------
function clearEmptyState() {
  const empty = chatWindow.querySelector(".chat-empty");
  if (empty) empty.remove();
}

function addBubble(question, answer, sources) {
  clearEmptyState();
  const bubble = document.createElement("div");
  bubble.className = "bubble";

  const sourcesHtml = sources && sources.length
    ? `<details class="bubble-sources">
         <summary>Sumber (${sources.length})</summary>
         <ul>${sources.map(s => `<li>${s.source} — hal. ${s.page}: "${s.snippet}"</li>`).join("")}</ul>
       </details>`
    : "";

  bubble.innerHTML = `
    <div class="bubble-q">${question}</div>
    <div class="bubble-a">${answer}</div>
    ${sourcesHtml}
  `;
  chatWindow.appendChild(bubble);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = questionInput.value.trim();
  if (!question) return;

  const subject = subjectFilter.value || null;
  questionInput.value = "";
  addBubble(question, "Mikir dulu ya...", []);

  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, subject, top_k: 4 }),
    });
    const data = await res.json();

    // Update bubble terakhir (yang tadi "Mikir dulu ya...")
    const lastAnswer = chatWindow.querySelector(".bubble:last-child .bubble-a");
    lastAnswer.textContent = data.answer;

    const lastBubble = chatWindow.querySelector(".bubble:last-child");
    if (data.sources && data.sources.length) {
      const sourcesHtml = `<details class="bubble-sources">
         <summary>Sumber (${data.sources.length})</summary>
         <ul>${data.sources.map(s => `<li>${s.source} — hal. ${s.page}: "${s.snippet}"</li>`).join("")}</ul>
       </details>`;
      lastBubble.insertAdjacentHTML("beforeend", sourcesHtml);
    }
  } catch (err) {
    const lastAnswer = chatWindow.querySelector(".bubble:last-child .bubble-a");
    lastAnswer.textContent = "Gagal menghubungi server. Pastikan backend sudah jalan.";
  }
});

refreshSubjects();