FROM node:24-slim

RUN apt-get update && apt-get install -y chromium \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r botuser \
    && useradd -r -g botuser -G audio,video botuser \
    && mkdir -p /home/botuser/Downloads \
    && chown -R botuser:botuser /home/botuser

WORKDIR /app

ENV PUPPETEER_SKIP_DOWNLOAD=true

COPY package.json ./
RUN npm install --omit=dev

COPY bot.js ./

RUN chown -R botuser:botuser /app

USER botuser

CMD ["node", "bot.js"]
