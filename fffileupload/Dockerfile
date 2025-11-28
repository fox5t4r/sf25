FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    php-cgi \
    cron \
    procps \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir flask werkzeug

RUN groupadd -g 1000 appuser && \
    useradd -r -u 1000 -g appuser appuser

WORKDIR /app

COPY app.py /app/
COPY templates/ /app/templates/
COPY static/ /app/static/

COPY flag.txt /flag.txt
RUN chmod 444 /flag.txt && chown root:root /flag.txt

RUN mkdir -p /app/uploads && \
    chown -R appuser:appuser /app && \
    chmod 755 /app/uploads

COPY cleanup.sh /usr/local/bin/cleanup.sh
RUN chmod +x /usr/local/bin/cleanup.sh && \
    chown root:root /usr/local/bin/cleanup.sh

RUN echo "*/30 * * * * appuser /usr/local/bin/cleanup.sh >> /var/log/cleanup.log 2>&1" > /etc/cron.d/cleanup && \
    chmod 0644 /etc/cron.d/cleanup && \
    crontab /etc/cron.d/cleanup

RUN touch /var/log/cleanup.log && \
    chown appuser:appuser /var/log/cleanup.log

RUN echo '#!/bin/bash\n\
# Cron 데몬 시작\n\
cron\n\
echo "[INFO] Cron 시작됨 - 30분마다 파일 정리 실행"\n\
# Flask 애플리케이션을 appuser로 실행\n\
exec su -s /bin/bash -c "cd /app && python3 app.py" appuser\n\
' > /start.sh && chmod +x /start.sh

EXPOSE 88

CMD ["/start.sh"]
