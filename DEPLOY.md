# DEPLOY.md — Alibaba Cloud ECS deployment runbook

Same Docker stack as local. "Deploying" = run the identical `docker compose` on the ECS.
Redeploy anytime with: `git pull && docker compose up -d --build` (~1-2 min).

---

## 0. Prerequisites (in the Alibaba Cloud console)
- [ ] ECS instance: **Ubuntu 22.04**, **2 vCPU / 4 GB**, pay-as-you-go, 40 GB disk, **public IP** assigned.
- [ ] Security Group inbound rules OPEN: **22** (SSH) and **8086** (API). (Source `0.0.0.0/0` is fine for the demo.)
- [ ] Root password (or key pair) set for the instance.
- [ ] Repo is **public** on GitHub, and `data_md/` is committed (so finance queries have data).

You need two things written down: the instance **PUBLIC_IP** and its **login** (root + password, or key).

---

## 1. SSH into the server
From your PC (PowerShell or any terminal):
```bash
ssh root@PUBLIC_IP
```
(If you set a key instead of a password: `ssh -i path\to\key.pem root@PUBLIC_IP`.)
Purpose: log into the cloud box. Everything below runs ON the server.

---

## 2. Install Docker + Compose
```bash
sudo apt update && sudo apt upgrade -y
curl -fsSL https://get.docker.com | sudo sh
docker --version && docker compose version
```
Purpose: installs Docker Engine + the Compose v2 plugin. The last line must print two versions.

---

## 3. Get the code
```bash
git clone <YOUR_PUBLIC_REPO_URL>
cd devpost-qwen-hackathon
```
Purpose: pulls the repo (with `data/`) onto the server.

---

## 4. Create the .env on the server
`.env` is NOT in git (secrets). Create it:
```bash
nano .env
```
Paste this, filling your real values, then Ctrl+O, Enter, Ctrl+X:
```
DASHSCOPE_API_KEY=sk-your-real-key
DASHSCOPE_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-flash

DB_PATH=data/psx.db
FINANCE_DATA_DIR=./data_md

POSTGRES_USER=psx_admin
POSTGRES_PASSWORD=psx_admin
POSTGRES_DB=psx_admin
```
Purpose: gives the container its API key, model, data paths, and Postgres creds.
(Compose sets DB_URL to the `db` service automatically — do NOT add DB_URL here.)

---

## 5. Build and start
```bash
docker compose up -d --build
```
Purpose: builds the api image and starts both containers (Postgres + API) in the background.
First boot creates the Postgres database and the app auto-creates its tables.

---

## 6. Verify (on the server)
```bash
docker compose ps            # db = healthy, api = running
docker compose logs -f api   # watch startup; Ctrl+C stops tailing (not the container)
curl http://localhost:8086/health
```
Expect: `{"status":"ok","agent":"psx_agent"}`.

## 7. Verify from the outside (your PC browser)
Open:
```
http://PUBLIC_IP:8086/health
http://PUBLIC_IP:8086/docs
```
If `localhost` works on the server but the browser does NOT → the Security Group isn't
allowing port 8086. Fix that inbound rule.

---

## 8. Redeploy after code changes (the iterate loop)
On your PC: commit + push. Then on the server:
```bash
cd devpost-qwen-hackathon
git pull
docker compose up -d --build
```
Purpose: pulls new code and rebuilds. ~1-2 min. Postgres data persists (volume untouched).

---

## Handy ops
```bash
docker compose logs --tail 100 api     # recent app logs
docker compose restart api             # restart just the API (data safe)
docker compose down                    # stop all (data safe in volume)
docker compose down -v                 # stop all + WIPE the DB (only if you mean it)
docker system prune -f                 # reclaim disk from old images/layers
```

## Common gotchas
- **Browser can't reach it but server `curl` works** → Security Group missing port 8086.
- **`permission denied` on docker** → run with `sudo`, or add user to the `docker` group.
- **Build OOM / very slow** → the 2 vCPU/4 GB is enough; if tight, stop other processes.
- **Finance says "no data"** → `data_md/` wasn't committed / `FINANCE_DATA_DIR` wrong.
