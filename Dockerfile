FROM python:3.13-slim

# Install curl and other dependencies needed for uv installation
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

WORKDIR /app

# Copy project files
COPY pyproject.toml pyproject.toml
COPY aoc_bot/ aoc_bot/

# Install dependencies using uv
RUN uv sync --frozen

# Create data and logs directories
RUN mkdir -p data logs

# Run the bot
CMD ["/root/.cargo/bin/uv", "run", "python", "-m", "aoc_bot.main"]
