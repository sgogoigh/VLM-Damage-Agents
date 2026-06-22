# Orchestrate Claims Desk — Frontend

A Next.js (App Router) customer-support chat for the Orchestrate claim verifier.
A claim is described conversationally; the backend inspects the photos and returns
a forensic **verdict dossier** — status, cited evidence, severity, and risk flags.

## What it does

- **Support chat** — greet → pick the damaged object → describe → attach photos → Verify.
- **Case library** (right rail) — loads real dataset cases (labeled `sample` set and
  the input-only `test` set) with thumbnails; click to stage a case.
- **Verdict dossier** — the result renders as a card: verdict, evidence/usability
  tags, issue · part · severity, justification, risk flags, and the evidence
  thumbnails with the model's *cited* images highlighted. For labeled cases it also
  shows a predicted-vs-labeled diff.
- **Provider switch + live status** — driven by `/api/providers` and `/api/health`.

## Backend integration

Talks to the FastAPI backend (default `http://localhost:8000`):

| UI surface | Endpoint |
|---|---|
| status pill | `GET /api/health` |
| provider switch + footer | `GET /api/providers` |
| case library | `GET /api/samples?split=sample\|test` |
| evidence thumbnails | `GET /dataset/<image_path>` (static) |
| Verify | `POST /api/verify` |

The backend's CORS already allows `http://localhost:3000`.

## Project structure

```
frontend/
├── app/
│   ├── layout.tsx          # metadata, viewport, global styles
│   ├── page.tsx            # renders <ClaimsDesk/>
│   └── globals.css         # the entire design system (tokens, components, motion)
├── components/
│   ├── ClaimsDesk.tsx      # orchestrator: chat state, verify flow, data loading
│   ├── Header.tsx          # brand, live status pill, provider switch
│   ├── ChatThread.tsx      # scrolling message list (auto-scroll)
│   ├── MessageBubble.tsx   # agent/user bubbles, typing indicator, verdict row
│   ├── Composer.tsx        # object picker + textarea + evidence tray + send
│   ├── SamplePicker.tsx    # right-rail case library (labeled / test)
│   ├── VerdictDossier.tsx  # the verdict card (status, evidence, diff)
│   └── icons.tsx           # inline SVG icon set
└── lib/
    ├── api.ts              # typed API client (NEXT_PUBLIC_API_BASE) + imageUrl()
    └── types.ts            # shared request/response + chat-message types
```

## Run locally

```bash
# 1) start the backend (separate terminal)
cd backend && uvicorn app.main:app --reload --port 8000

# 2) start the frontend
cd frontend
npm install
npm run dev          # http://localhost:3000
```

Point at a non-default backend by setting `NEXT_PUBLIC_API_BASE` (see
`.env.local.example`).

## Design notes

"The Claims Desk": a warm conversation that resolves into a precise, instrument-like
verdict. Humanist sans for talk, a monospace face for all forensic readouts (image
IDs, flags, status codes). Deep indigo-slate ground, electric periwinkle accent, and
status-driven color — emerald (supported), rose (contradicted), amber (not enough
info). All styles live in `app/globals.css`; components are in `components/`.
