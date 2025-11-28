FROM python:3.11-slim

WORKDIR /app

RUN mkdir -p /data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN groupadd -g 1000 appuser && \
    useradd -r -u 1000 -g appuser appuser && \
    chown -R appuser:appuser /app /data

USER appuser

EXPOSE 53215

CMD ["python", "app.py"]
