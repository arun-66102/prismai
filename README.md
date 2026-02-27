<p align="center">
  <img src="https://img.shields.io/badge/Prism-AI-blueviolet?style=for-the-badge&logo=prisma&logoColor=white" alt="Prism AI" />
</p>

<h1 align="center">🔮 Prism AI</h1>

<p align="center">
  <b>One Product Name. Infinite Content.</b><br/>
  AI-powered content generation platform for creators — blogs, social media images & video scripts, all from a single input.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/PostgreSQL-async-4169E1?style=flat-square&logo=postgresql&logoColor=white" />
  <img src="https://img.shields.io/badge/Groq-LLaMA_3.3-orange?style=flat-square" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" />
</p>

---

## 🚀 What is Prism AI?

**Prism AI** is an all-in-one AI content generation platform built for **content creators, marketers, and indie hackers**. Just enter your **product name**, and Prism AI instantly generates:

| Content Type | Description |
|---|---|
| 📝 **SEO Blog** | A fully structured, SEO-optimized blog article with title, meta description, headings, and CTA |
| 🎬 **Video Script** | A professional video script with hook, intro, main content, engagement prompt, and outro |
| 🖼️ **Social Media Image** | Eye-catching AI-generated visuals tailored for platforms like Instagram, LinkedIn & Twitter |

---

## ✨ Features

- 🎯 **Single Input Workflow** — Enter a product name and let AI handle the rest
- 🔐 **Secure Authentication** — JWT-based auth with Access & Refresh tokens
- 👥 **Role-Based Access Control (RBAC)** — Dedicated User and Admin roles
- 💎 **Subscription Tiers** — Free, Pro, and Business tiers with integrated rate limiting
- 🛡️ **Admin Dashboard** — Manage users, monitor usage stats, and update account statuses
- 🖼️ **Social Media Image Generation** — Powered by FLUX.1-schnell via HuggingFace/Together AI
- ⚡ **Ultra-Fast Inference** — Powered by Groq and LLaMA 3.3
- 🐘 **PostgreSQL Integration** — High-performance, asynchronous database handling with `asyncpg`

---

## 🏗️ Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python, FastAPI, Gunicorn |
| **Frontend** | Vanilla JavaScript, CSS (Glassmorphism), HTML5 |
| **Database** | PostgreSQL (Production), SQLite (Development) |
| **Text AI** | Groq (LLaMA 3.3-70b-versatile) |
| **Image AI** | Hugging Face / Together AI (FLUX.1-schnell) |
| **Auth** | JWT (JSON Web Tokens) |

---

## 📁 Project Structure

```
Prism-AI/
├── backend/
│   ├── main.py               # FastAPI entry point & Auth routes
│   ├── admin.py              # Admin-only endpoints & stats
│   ├── database.py           # PostgreSQL connection & helper functions
│   ├── blog_generation.py    # Blog content logic
│   ├── video_script.py       # Video script logic
│   ├── image_generation.py   # Image generation (FLUX)
│   └── models.py             # Pydantic models for validation
├── frontend/
│   ├── index.html            # Core SPA UI
│   ├── app.js                # Frontend logic & Auth handling
│   ├── admin.html            # Admin dashboard UI
│   └── admin.js              # Admin logic
├── Dockerfile                # Production container config
└── .env                      # API Keys & DB Connection
```

---

## ⚙️ Getting Started

### 1. Set Up Environment
Create a `.env` file in the `backend/` directory:
```env
JWT_SECRET=your_jwt_secret
API_KEY=your_groq_api_key
HF_API_KEY=your_huggingface_api_key
DATABASE_URL=postgresql://user:pass@localhost:5432/prism
```

### 2. Install Dependencies
```bash
pip install -r backend/requirements.txt
```

### 3. Run Locally (Development)
```bash
cd backend
python -m uvicorn main:app --reload
```
The API will be live at **http://localhost:8000**

---

## 🚢 Deployment

Prism AI is production-ready. I have created detailed guides for several platforms:

- 🧱 **[Dokku (Heroku-style VPS)](./docs/dokku_deployment.md)**
- 🚀 **[Coolify (Web Dashboard VPS)](./docs/coolify_deployment.md)**
- ☁️ **[Render + Supabase (100% Free)](./docs/free_deployment_guide.md)**

---

## 🗺️ Roadmap

- [x] Full Authentication System
- [x] Admin Dashboard & RBAC
- [x] PostgreSQL Migration
- [x] Social Media Image Generation
- [ ] Stripe Payment Integration
- [ ] Content History & Export (PDF/MD)
- [ ] Multi-language Support
- [ ] Team Workspaces

---

## 🤝 Contributing
Contributions are welcome! Please fork the repo and open a PR.

## 📄 License
Licensed under the **MIT License**.

---
<p align="center">
  Built with 💜 by <b>Prism AI Team</b>
</p>
