# ClinIQ

[![Live Demo](https://img.shields.io/badge/Live-Demo-emerald.svg)](https://clin-iq-gules.vercel.app/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**ClinIQ** is an evidence-first medical research discovery and summarization platform. It bridges the gap between raw medical literature (PubMed) and actionable clinical insights by using advanced AI and deterministic ranking algorithms.

> [!NOTE]
> **AI-Enhanced, Not AI-Driven**: ClinIQ prioritizes source reliability. All AI-generated summaries are strictly validated against a deterministic ranking engine to ensure ZERO hallucination of research papers.

---

## 🚀 Key Features

- **Intelligent Query Expansion**: Automatically expands vague disease queries (e.g., "lung cancer") into comprehensive search terms covering treatments, clinical trials, and survival outcomes.
- **Evidence Ranking Engine**: A transparent scoring system that ranks papers based on publication recency, clinical intent, and relevance to the specific condition.
- **Validated AI Summaries**: Uses **NVIDIA NIM (Llama 3.1 70B)** to format complex research data into readable summaries. 
- **Hallucination Prevention**: Features a built-in validation layer that rejects AI outputs if they mention papers or details not present in the original source data.
- **Location-Aware Findings**: Filters and prioritizes research relevant to specific geographic locations when provided.

---

## 🛠️ Tech Stack

### Backend
- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.12)
- **AI Interface**: [NVIDIA NIM](https://www.nvidia.com/en-us/ai-data-science/generative-ai/nim/) via AsyncOpenAI
- **Data Source**: [PubMed E-Utils API](https://www.ncbi.nlm.nih.gov/home/develop/api/)
- **Validation**: Strict Pydantic-based data models

### Frontend
- **Framework**: [React](https://react.dev/) + [Vite](https://vitejs.dev/)
- **Styling**: [TailwindCSS](https://tailwindcss.com/)
- **Deployment**: [Vercel](https://vercel.com/)

---

## 💻 Local Development

### Prerequisites
- Python 3.12+
- Node.js 18+
- An [NVIDIA NIM API Key](https://build.nvidia.com/)

### Backend Setup
1. Navigate to the `backend` directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create a `.env` file:
   ```env
   NVIDIA_NIM_API_KEY=your_key_here
   ALLOW_ORIGINS=http://localhost:5173
   ```
5. Run the server:
   ```bash
   uvicorn main:app --reload
   ```

### Frontend Setup
1. Navigate to the `frontend` directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Create a `.env` file:
   ```env
   VITE_API_URL=http://localhost:8000
   ```
4. Run the development server:
   ```bash
   npm run dev
   ```

---

## 🌍 Deployment

### Backend (Railway)
1. Set the root directory to `backend/`.
2. Ensure `NVIDIA_NIM_API_KEY` and `ALLOW_ORIGINS` (your Vercel URL) are set in environment variables.
3. Railway will use the provided `railway.json` and `runtime.txt` for configuration.

### Frontend (Vercel)
1. Set the root directory to `frontend/`.
2. Add `VITE_API_URL` pointing to your Railway service.
3. Ensure the Build Command is `npm run build` and Output Directory is `dist`.

---

## ⚖️ License

Distributed under the MIT License. See `LICENSE` for more information.

---

## 📞 Contact

Project Link: [https://github.com/your-username/curalink](https://github.com/your-username/curalink)
Live Demo: [https://clin-iq-gules.vercel.app/](https://clin-iq-gules.vercel.app/)
