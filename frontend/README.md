# Orchestrate Frontend

This is a minimal Next.js app for the Orchestrate Claim Verifier.

## Run locally

1. Install dependencies:
   ```bash
   cd frontend
   npm install
   ```
2. Start the development server:
   ```bash
   npm run dev
   ```
3. Open `http://localhost:3000`.

## Usage

Enter a `user_id`, `claim_object`, `user_claim`, and semicolon-separated image paths in the text area. The app sends a request to the backend at `http://localhost:8000/api/verify`.

## Notes

- The backend should be running separately using `uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000`.
- Configure your backend API origin in `backend/app/config.py` if needed.
