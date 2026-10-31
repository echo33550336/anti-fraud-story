# Anti-Fraud Scenario Trainer | The Ticket Before Curtain

An interactive, choice-driven anti-fraud exercise. Players encounter ticketing impersonation, a fake familiar contact, and an escalating investment pitch. The backend advances the story from recorded choices and returns a path-based review.

> **Simulation only:** All payments are fictional. No real payment service is connected. Free-text answers are matched with configured keywords; the project does not use generative AI to interpret them.

**Online demo:** <https://echo33550336.github.io/-/> — a static front-end port of the same graph and integer scoring rules. The Python backend version lives in [`backend/`](backend/).

## What makes it distinctive

- **Two connected scam patterns:** A fake ticketing fee and repeated-transfer pressure lead into small purchases from an impersonated friend and a larger investment request.
- **Choices shape the ending:** The story has 15 nodes and 16 endings. E15 and E16 depend on earlier verification and payment events.
- **Server-side review:** The backend records choices and simulated payment amounts, then calculates the score and badges and returns the matching ending.
- **Practical response skills:** Players practice independent verification, stopping further payments, preserving relevant evidence, contacting official channels, and sharing privacy-aware warnings.

## Tech stack

| Layer | Implementation |
|---|---|
| Frontend | HTML, CSS, vanilla JavaScript; no build step |
| API | Python standard library `http.server` |
| Story engine | JSON graph configuration, deterministic conditional routing, keyword rules |
| Sessions | In-memory server-side state with a two-hour idle timeout |

There are no third-party Python dependencies. Sessions are not stored in a database and are lost when the server restarts, so the current setup is intended for local demos and single-process use.

## Run locally

One process serves both the API and the page:

```powershell
cd backend
python app.py
```

Open <http://127.0.0.1:5000/>. The frontend is served from `../frontend/`; the API lives under `/api/story/*`.

For frontend-only iteration, start a static server instead and the page falls back to `http://localhost:5000` for the API:

```powershell
cd frontend
python -m http.server 8080 --bind 127.0.0.1
```

CORS currently allows loopback development origins only.

## Repository map

```text
backend/   API, sessions, story engine, configuration, and deployment files
frontend/  page, interaction code, styles, and artwork
docs/      documentation index, story design, and archived analysis
```

- [Backend guide](backend/README.md) · [Frontend guide](frontend/README.md)
- [Documentation index](docs/README.md) · [Story design](docs/story/15-node-16-ending-design.md)
- [Archived gap assessment](docs/archive/integration/13-gap-assessment.md) · [Archived alignment plan](docs/archive/integration/14-backend-alignment-plan.md)

Files under `docs/archive/` preserve earlier models and planning notes. The source code and this README describe the current implementation.
