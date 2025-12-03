FROM python:3.9-slim-bullseye

# Install curl and build dependencies for Python packages
RUN apt-get update
RUN apt-get install -y --no-install-recommends curl build-essential python3-dev
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

# Install uv package manager
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Copy project files
COPY pyproject.toml pyproject.toml
COPY uv.lock uv.lock
COPY README.md README.md
COPY aoc_bot/ aoc_bot/

# Install dependencies using uv
RUN uv sync --frozen

# Create data and logs directories
RUN mkdir -p data logs

# Run the bot
CMD ["/root/.local/bin/uv", "run", "python", "-m", "aoc_bot.main"]
