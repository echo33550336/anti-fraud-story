# Anti-Fraud Scenario Trainer — MIX-V5

An interactive anti-fraud exercise based on *The Ticket Before the Final Act*. Players navigate 15 story nodes and 16 possible endings, then receive a path-based review and integer score.

## Features

- Two connected scam patterns: ticket impersonation, an impersonated familiar contact, and escalating investment pressure.
- Fixed-choice and free-text answers with confirmation and explicit story-state tracking.
- Deterministic story routing and scoring; optional model-assisted comments for open answers.
- A browser frontend and Python backend served from one process.
- Session data is held in memory for the demo and is not persisted to a database.

## Run locally

On Windows, double-click `start.bat`, then open <http://127.0.0.1:5000>.

Or run:

```powershell
cd backend
python app.py
```

Python 3.8 or newer is recommended. The service uses the Python standard library.

## Repository layout

- `frontend/` — browser UI, story text, images, audio, and frontend tools.
- `backend/` — HTTP service, story engine, scoring, configuration, and deployment files.
- `docs/` — system manual and design materials.
- `start.bat` — Windows launcher.

## API

- `POST /api/story/start`
- `POST /api/story/answer`
- `POST /api/story/open`
- `POST /api/story/confirm`
- `GET /api/story/review?session_id=...`

See `docs/系统手册.md` for the full API and scoring description.

## Optional model comments

Model-assisted open-answer comments are **disabled by default** in this public package. To enable them, configure `LLM_API_KEY` as an environment variable and explicitly enable the feature in `backend/config.json`. Never commit API credentials. Free-text answers may be sent to the configured provider when this feature is enabled; monitor that provider's RPM, token, and usage quotas.

## Deployment

The repository includes a root `Dockerfile` and `render.yaml` for deployment. See `backend/deploy/部署与公网演示.md` for deployment options and operational notes.