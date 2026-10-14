FROM python:3.12-slim

WORKDIR /app

COPY . .

# Hugging Face Spaces defaults to 7860. Render supplies its own PORT at runtime.
ENV PORT=7860

EXPOSE 7860

CMD ["python", "server.py"]
