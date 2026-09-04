FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY northstar ./northstar
COPY procedures ./procedures
COPY sql ./sql
RUN pip install --no-cache-dir .
RUN mkdir -p /app/data
EXPOSE 8000
CMD ["northstar", "serve", "--host", "0.0.0.0", "--port", "8000"]
