# ReadEasy — OCR Text Reader for Seniors & Low Vision Users

> A mobile-first web application that captures text from images or camera, recognizes it using OCR, and reads it aloud — with user accounts and scan history.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Flask](https://img.shields.io/badge/Flask-3.x-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue)
![Railway](https://img.shields.io/badge/Deployed-Railway-purple)
![PWA](https://img.shields.io/badge/PWA-Ready-orange)

---

## 🌐 Live Demo

**[https://zestful-alignment-production-9e8c.up.railway.app](https://zestful-alignment-production-9e8c.up.railway.app)**

---

## 📖 About

ReadEasy was built as a diploma project for the Diploma in Information Technology program. The target audience is elderly people and users with low vision who struggle with small printed text on medicine labels, receipts, and documents.

The app solves a real accessibility gap — most OCR tools are built for developers, not for everyday users who simply need to read what's in front of them.

---

## ✨ Features

- 📷 **Camera & Upload** — capture text live from the camera or upload from gallery
- 🔍 **OCR Recognition** — Tesseract engine with multi-strategy image preprocessing
- 🔤 **Font Scaling** — adjustable font size from 18pt to 80pt
- 🔊 **Text-to-Speech** — reads recognized text aloud automatically
- 🔐 **User Authentication** — register and login with Bcrypt-hashed passwords
- 📋 **Scan History** — every scan saved per user account in PostgreSQL
- 📱 **PWA** — installable on iOS and Android, works offline

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML5, CSS3, Vanilla JS, PWA |
| Backend | Python, Flask, Flask-Login, Flask-Bcrypt |
| OCR | Tesseract, OpenCV, Pillow, NumPy |
| Database | PostgreSQL, SQLAlchemy, psycopg2 |
| Deploy | Railway, Gunicorn, GitHub |

---

## 🗂️ Project Structure

```
professional-ocr-system/
├── app.py              # Main Flask application, routes, OCR logic
├── models.py           # Database models (User, ScanHistory)
├── auth.py             # Authentication blueprint (register/login/logout)
├── index.html          # Frontend single-page application
├── requirements.txt    # Python dependencies
├── Procfile            # Gunicorn start command for Railway
├── nixpacks.toml       # Tesseract installation config for Railway
├── railway.json        # Railway builder config
├── static/
│   ├── manifest.json       # PWA manifest
│   ├── service-worker.js   # PWA offline support
│   └── icons/              # App icons (72px to 512px)
└── .env.example        # Environment variables template
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL
- Tesseract OCR

### 1. Clone the repository

```bash
git clone https://github.com/isslxm/professional-ocr-system.git
cd professional-ocr-system
```

### 2. Create virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Tesseract

**Windows:** Download from [github.com/UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki)

**macOS:**
```bash
brew install tesseract
```

**Linux:**
```bash
sudo apt install tesseract-ocr tesseract-ocr-rus
```

### 5. Set up PostgreSQL

```sql
CREATE DATABASE ocr_db;
CREATE USER ocr_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE ocr_db TO ocr_user;
```

### 6. Create `.env` file

```env
SECRET_KEY=your_random_secret_key
DATABASE_URL=postgresql://ocr_user:your_password@localhost:5432/ocr_db
```

Generate a secure secret key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 7. Run the application

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000)

---

## 🌍 Deployment (Railway)

1. Push your code to GitHub
2. Create a new project on [railway.app](https://railway.app)
3. Connect your GitHub repository
4. Add a PostgreSQL database service
5. Add `SECRET_KEY` to environment variables
6. Railway auto-deploys on every push to `main`

---

## 🔌 API Endpoints

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/register` | Create new account |
| POST | `/api/auth/login` | Sign in |
| POST | `/api/auth/logout` | Sign out |
| GET | `/api/auth/me` | Get current user |

### OCR

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/recognize` | Recognize text from image |
| GET | `/api/health` | Health check |

### History

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/history` | Get scan history (paginated) |
| DELETE | `/api/history/<id>` | Delete one record |
| DELETE | `/api/history` | Clear all history |

---

## 🧠 How OCR Works

The app uses a multi-strategy approach for maximum accuracy:

1. **Standard preprocessing** — grayscale conversion, CLAHE contrast enhancement, adaptive thresholding
2. **Small text mode** — 2.5x upscaling before recognition
3. **Dark background mode** — color inversion for light text on dark backgrounds
4. **Multiple PSM modes** — tries PSM 6, 3, 4, 11 and picks the best result

---

## 📊 Database Schema

```
users
├── id (PK)
├── username
├── email
├── password (bcrypt hash)
└── created_at

scan_history
├── id (PK)
├── user_id (FK → users.id)
├── extracted_text
├── language
├── engine
├── source (upload / camera)
├── char_count
└── created_at
```

---

## 👤 Author

**Islam Osmonov**
Diploma in Information Technology

---

## 📄 License

This project was created for academic purposes as part of a diploma program.