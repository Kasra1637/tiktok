# HookForge — TikTok Viral Hook Discovery

Discover trending TikTok hooks, analyze what makes them work, face-swap yourself in, and generate video prompts.

## Deploy to Render (Free)

1. Fork this repo
2. Go to [render.com](https://render.com) and sign up with GitHub
3. Click **New** → **Web Service** → Connect your fork
4. Render will auto-detect the Dockerfile
5. Set environment variables:
   - `MONGO_URL` — Your MongoDB Atlas connection string ([free tier](https://www.mongodb.com/atlas))
   - `DB_NAME` — `hookforge`
   - `EMERGENT_LLM_KEY` — Your AI API key
6. Click **Deploy**

Your app will be live at `https://tiktok-hookforge.onrender.com`

## Local Development

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn server:app --reload
```

### Frontend
```bash
cd frontend
yarn install
yarn start
```

Set `REACT_APP_BACKEND_URL=http://localhost:8000` in frontend/.env for local dev.

## Tech Stack

- **Backend:** Python FastAPI + MongoDB + yt-dlp + ffmpeg
- **Frontend:** React 19 + Tailwind CSS + shadcn/ui
- **AI:** Gemini Vision (hook analysis) + Gemini Image Gen (face swap)
- **Deployment:** Docker on Render (free tier)
