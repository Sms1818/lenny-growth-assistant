# Lenny Growth Assistant: Frontend

React and TypeScript (Vite) interface for Lenny Growth Assistant, an MVP that
answers product and growth questions from Lenny's Podcast and Newsletter and
cites its sources. It talks to the FastAPI backend in this repo.

## What it does
- Chat with persistent sessions. Each session keeps its own message history,
  and a sidebar lets you switch between them.
- Shows numbered citations and source cards for every answer (title, source
  type, guest, links, timestamps).
- Provider toggle in the header: Auto, Local (Ollama) or Cloud. Completed
  responses show which provider and model produced them.
- Artifact viewer in a side panel. Markdown is rendered, and generated HTML
  runs inside a sandboxed iframe with no permissions. Artifacts can also be
  opened in a new tab.
- Ship 30 for 30 essay generation from the composer.
- Checks the backend on startup and shows a "Disconnected" badge if it can't
  be reached. API errors appear as inline banners, and long generations show
  a live elapsed time counter.

## Run it
With the full stack (recommended), from the repo root:

    docker compose up --build

The frontend is then at http://localhost:5173.

To run it on its own:

    cd frontend
    cp .env.example .env
    npm install
    npm run dev

`VITE_API_BASE_URL` (default http://localhost:8000) must point at the backend.

## Checks
    npm run lint     # oxlint
    npm run build    # tsc + vite build

There are no frontend tests yet.

## Status
MVP. See the main README for the backend, ingestion and architecture.