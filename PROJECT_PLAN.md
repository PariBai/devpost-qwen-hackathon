# PROJECT_PLAN.md

**Devpost — Global AI Hackathon with Qwen Cloud · Track 1: MemoryAgent**
Deadline: **July 9** · Submit target: **July 8** (keep July 9 as buffer)

Strategy: **deploy backend first → frontend → prompts + features → docs/video.**
A deployed, working simple app beats a feature-rich localhost app that isn't eligible.

---

## Auth decision: do you need signup/login/password?

**Build the *smallest possible* user system — a `users` table + a simple login that returns a stable `user_id`. Do NOT build "real" auth (email verification, OAuth, password reset, refresh tokens).**

Why: the *only* thing the memory system needs from auth is a **stable, unique `user_id`** to namespace preferences. Judges score the *memory*, not the login page.

Concretely:
- A Postgres `users` table: `id (uuid)`, `username`, `password_hash`, `created_at`.
- `POST /signup` and `POST /login` → returns a token (a simple JWT) carrying `user_id`.
- Frontend stores the token, sends it on each chat request; backend extracts `user_id` and passes it into `SessionContext(user_id=...)`.
- Password hashing with `passlib[bcrypt]` (5 lines). No email, no OAuth.

~1 hour of work in FastAPI, looks legitimate in the demo, and enables the killer Track-1 moment: log in as User A (Hinglish + cement), log out, log in as User B (fresh memory) — proving per-user isolation.

---

## Before anything: check your credits (5 min)

Log into the **Alibaba Cloud console** and look in two places:
1. **Billing / Expenses → Coupons & Credits (or "Vouchers")** — hackathon cloud credits for ECS/RDS/etc.
2. **Model Studio / DashScope console → usage/credits** — Qwen token budget (separate from cloud infra credits).

What consumes them:
- **ECS** (small Linux VM to run the backend) — a couple dollars/day for a small instance.
- **Postgres** — free if run in Docker *on the ECS*; costs credits if using managed **ApsaraDB RDS**.
- **Qwen tokens** (DashScope) — every agent turn.

> Report rough credit amounts to size the instance so we don't burn out mid-week.

---

## Stack recommendation (for a deployment beginner)

- **Compute: ECS** (a plain Linux VM), **not** Function Compute. An ECS is just "a computer in the cloud you SSH into and run your app" — easier to understand/debug and handles streaming cleanly. Function Compute has cold-starts and streaming quirks.
- **Database: Postgres in Docker on the same ECS** to start (zero extra cost, one `docker compose up`). Upgrade to managed RDS later if credits allow.
- **Backend framework: FastAPI** with an SSE streaming endpoint (wraps the existing LangGraph `astream`).
- **Frontend: a single-page app** (plain React/Vite or Next.js) — kept minimal.

---

## The full task list (phased, step-by-step)

Ordered: **deploy backend first → frontend → prompts+features → docs/video.** Auth slots in with the backend because deployment needs it.

### Phase 0 — Foundations (local, ~half day)
- [ ] 0.1 Confirm credits (above) and report amounts.
- [ ] 0.2 Freeze a `requirements.txt` from the `psxd` env (`pip freeze > requirements.txt`), pruned to what's actually imported.
- [ ] 0.3 Create a `.env.example` documenting every var (`DASHSCOPE_API_KEY`, `DB_URL_LOCAL`, `QWEN_MODEL`, `JWT_SECRET`, `FINANCE_DATA_DIR`, `DB_PATH`).
- [ ] 0.4 Add an open-source `LICENSE` file (MIT is fine) — **required for eligibility**, do it now so it's not forgotten.

### Phase 1 — Wrap the graph in a FastAPI backend (local, ~1 day)
- [ ] 1.1 Create `app/api/main.py` with FastAPI.
- [ ] 1.2 `POST /chat` streaming endpoint (SSE) that takes `{message, thread_id}` + auth token, builds `SessionContext(user_id=…)`, and streams the existing `compliance_chunk`/`finance_chunk`/`synthesize_chunk`.
- [ ] 1.3 Wire the **Postgres checkpointer** (per-session/thread context) and **Postgres store** (cross-session memory) via `DB_URL_LOCAL` — the "per-session + cross-session with Postgres" goal.
- [ ] 1.4 `GET /threads` and `GET /threads/{id}` so the frontend can list/resume conversations (uses the checkpointer).
- [ ] 1.5 `GET /me/preferences` endpoint (reads the store) — powers the "🧠 memory panel" in the UI and is a great demo visual.
- [ ] 1.6 CORS config for the frontend origin.
- [ ] 1.7 Run locally, test with `curl`/browser before touching the cloud.

### Phase 2 — Minimal auth (local, ~1–2 hrs)
- [ ] 2.1 `users` table + migration/setup.
- [ ] 2.2 `POST /signup`, `POST /login` (passlib bcrypt), issue JWT with `user_id`.
- [ ] 2.3 FastAPI dependency that extracts `user_id` from the token and injects it into every chat request.
- [ ] 2.4 Test: two users, isolated memory.

### Phase 3 — Dockerize (local, ~half day)
- [ ] 3.1 `Dockerfile` for the FastAPI app.
- [ ] 3.2 `docker-compose.yml` with two services: `api` + `postgres` (with a named volume so memory persists across restarts).
- [ ] 3.3 `docker compose up` locally and confirm the whole thing works end-to-end in containers. **If it runs in Docker locally, it will run on the ECS.**

### Phase 4 — Deploy to Alibaba Cloud ECS (~1 day, guided each click)
- [ ] 4.1 Create an ECS instance (Ubuntu, small size), open security-group ports (22 SSH, 80/443, the API port).
- [ ] 4.2 SSH in; install Docker + docker-compose.
- [ ] 4.3 Copy the repo up (git clone), add the production `.env`.
- [ ] 4.4 `docker compose up -d`; verify the API responds on the public IP.
- [ ] 4.5 (Optional) Nginx reverse proxy + a domain/HTTPS — nice but not required for the video.
- [ ] 4.6 **Record the Alibaba Cloud proof video** (backend running on the ECS) and note the code file that calls Alibaba Cloud (Qwen/DashScope) — **required deliverable.**

### Phase 5 — Frontend (~1.5 days)
- [ ] 5.1 Vite + React app: login/signup screen, chat screen, thread sidebar.
- [ ] 5.2 SSE streaming render of the three chunk types.
- [ ] 5.3 **Memory panel**: shows current stored preferences (`/me/preferences`) and a live "🧠 remembered / 🗑 forgot" feed from the `[memory]` events — the visual that sells Track 1.
- [ ] 5.4 Deploy the frontend (static hosting — Alibaba OSS static site, or serve it from the same ECS via Nginx).

### Phase 6 — Prompt overhaul + features (~1.5 days, parallel-able)
- [ ] 6.1 **You rewrite the prompts** (router, synthesize, memory_writer, agents) as you see fit — I'll wire whatever you write and help tighten the memory-writer rules (e.g. "don't store one-off topics").
- [ ] 6.2 **Shariah-compliance feature** — flag KSE-100 companies compliant/not; store "Shariah-only" as a user preference → auto-filter results. (Highest-value feature: it's really a memory feature.)
- [ ] 6.3 **Consolidated profit** for a company (finance tool addition).
- [ ] 6.4 **Daily follow-up** (stretch, but *excellent* for Track 1 — proactive use of memory): a scheduled job that reads each user's stored preferences, generates a personalized market summary via Qwen, and delivers it (email via Alibaba DirectMail, or just an in-app "digest" for the demo). Shows the agent *acting* on accumulated memory autonomously.

### Phase 7 — Submission package (~1 day, do NOT leave to the end)
- [ ] 7.1 Architecture diagram (Qwen Cloud → FastAPI → Postgres checkpointer/store → frontend).
- [ ] 7.2 README + text description + track ID.
- [ ] 7.3 3-min demo video: session 1 teaches preferences → new session proves persistence + Shariah filter in action → memory panel on screen.
- [ ] 7.4 Submit **July 8**, keep July 9 as buffer.

---

## On feature priorities
- **Shariah-compliant** → yes, do it (Phase 6.2), it's a memory feature in disguise.
- **Consolidated profit** → yes if time (6.3), it's quick.
- **Daily follow-up** → strong Track-1 signal (proactive memory use); mark it stretch and only build if Phases 1–5 are solid.

**Sequencing:** get Phases 1–4 done first (a deployed, working backend) before adding any new feature.
