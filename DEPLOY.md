# Deploying the web board to Vercel

This branch (`host/vercel`) makes the app serverless-ready:

- The API is **stateless** — every request carries the position (FEN), so no
  game lives in server memory. The browser keeps the game in `localStorage`.
- The engine runs **in-process** (no UCI subprocess), built once per function
  instance and reused across warm requests.
- `api/index.py` is the Vercel entrypoint; `vercel.json` routes every request
  to it and FastAPI serves both the API and the static board.

## Setup, step by step

1. Push this branch: `git push -u origin host/vercel`.
2. On [vercel.com](https://vercel.com), **Add New → Project** and import the
   `git-gud-chess` GitHub repository.
3. Configure the project:
   - **Framework Preset**: Other
   - **Root Directory**: leave as the repository root. The function imports
     the `chessbot/` engine package, which lives next to `web/`, so `web/`
     alone cannot be the root.
   - Build/output settings: leave empty (there is no build step).
4. In **Settings → Git**, set the **Production Branch** to `host/vercel`
   (or merge this branch into `master` and skip this step).
5. Deploy. Optional environment variables:
   - `CHESSBOT_WEIGHTS` — path to a weights file; defaults to the bundled
     `demo.npz` (delete it or set this to switch evaluators).
   - `CHESSBOT_MOVETIME_MS` — engine think time per move (default `800`).
     Keep it comfortably under the function timeout.

## Notes

- Cold starts add a few hundred ms (numpy import + weight load) to the first
  move after idle; warm moves respond in roughly the movetime.
- Local development is unchanged: `uv run python -m web` still serves the
  same app on http://127.0.0.1:13501.
