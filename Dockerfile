# PSX MemoryAgent API image
# Python 3.12 to match the dev env (psxd = 3.12.7).
FROM python:3.12-slim

# - PYTHONUNBUFFERED: logs stream immediately (important for SSE + docker logs)
# - PYTHONDONTWRITEBYTECODE: no .pyc clutter in the image
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first (own layer) so code changes don't re-run pip every build.
# psycopg[binary], PyMuPDF, rapidfuzz, bcrypt all ship manylinux wheels -> no
# compiler needed, so we can stay on the small slim base.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the rest of the app (respects .dockerignore).
COPY . .

EXPOSE 8086

# Entrypoint: modular web layer in backend/ (backend.main:app).
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8086"]
