FROM python:3.12-slim

WORKDIR /app

COPY . .

ENV PORT=10000

EXPOSE 10000

CMD ["python", "server.py"]
