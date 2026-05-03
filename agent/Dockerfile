FROM python:3.11-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.11-slim

WORKDIR /app

# Create non-root user
RUN groupadd -r agent && useradd -r -g agent -u 1000 agent

COPY --from=builder /install /usr/local
COPY src/ ./src/

# Switch to non-root user
USER 1000

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
