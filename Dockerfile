FROM python:3.10-alpine

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable

COPY . .

RUN mkdir -p logs

CMD ["uv", "run", "python", "main.py"]
