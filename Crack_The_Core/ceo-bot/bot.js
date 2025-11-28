import express from "express";
import puppeteer from "puppeteer";

const FLAG = process.env.FLAG ?? (console.log("No FLAG env"), process.exit(1));

const APP_HOST = "public-web";
const APP_PORT = "82";
const APP_URL = `http://${APP_HOST}:${APP_PORT}`;
const BOT_PORT = 3000;

const app = express();
app.use(express.json());

let browser = null;

const visitQueue = [];
let isProcessing = false;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const initBrowser = async () => {
  if (browser) {
    try {
      await browser.version();
      return;
    } catch (e) {
      browser = null;
    }
  }

  console.log("[CEO Bot] Initializing browser...");

  browser = await puppeteer.launch({
    headless: "new",
    executablePath: "/usr/bin/chromium",
    args: [
      "--no-sandbox",
      "--disable-dev-shm-usage",
      "--disable-gpu",
      "--disable-software-rasterizer",
    ],
  });

  browser.on("disconnected", () => {
    console.log("[CEO Bot] Browser disconnected");
    browser = null;
  });

  console.log("[CEO Bot] Browser initialized (reusable)");
};

const visitPage = async (token) => {
  console.log(`[CEO Bot] Visiting token: ${token.substring(0, 8)}...`);

  let context = null;
  let page = null;

  try {
    await initBrowser();

    if (!browser) {
      console.error("[CEO Bot] Failed to initialize browser");
      return;
    }

    context = await browser.createBrowserContext();
    page = await context.newPage();

    await context.setCookie({
      name: "flag",
      value: FLAG,
      domain: APP_HOST,
      path: "/",
      httpOnly: false,
    });
    console.log("[CEO Bot] Flag cookie set");

    console.log(`[CEO Bot] Visiting todolist for token: ${token.substring(0, 8)}...`);
    await page.goto(`${APP_URL}/internal/view-todo?token=${token}`, {
      timeout: 10000,
      waitUntil: "networkidle0",
    });

    await sleep(5000);

    console.log(`[CEO Bot] Done for token: ${token.substring(0, 8)}...`);

  } catch (e) {
    console.error(`[CEO Bot] Error: ${e.message}`);
  } finally {
    try {
      if (page) await page.close();
    } catch (e) {
    }
    try {
      if (context) await context.close();
    } catch (e) {
    }
  }
};

const processQueue = async () => {
  if (isProcessing || visitQueue.length === 0) return;

  isProcessing = true;

  while (visitQueue.length > 0) {
    const token = visitQueue.shift();
    await visitPage(token);
    await sleep(2000);
  }

  isProcessing = false;
};

setInterval(processQueue, 5000);

app.post("/visit", (req, res) => {
  const { token } = req.body;

  if (!token) {
    return res.status(400).json({ error: "Token required" });
  }

  if (visitQueue.includes(token)) {
    return res.json({ success: true, message: "Already in queue" });
  }

  if (visitQueue.length >= 10) {
    return res.status(429).json({ error: "Queue is full. Try again later." });
  }

  visitQueue.push(token);
  console.log(`[CEO Bot] Added to queue: ${token.substring(0, 8)}... (queue size: ${visitQueue.length})`);

  res.json({ success: true, message: "Added to visit queue" });
});

app.get("/health", (req, res) => {
  res.json({
    status: "ok",
    queueSize: visitQueue.length,
    isProcessing,
    browserActive: browser !== null,
  });
});

const startServer = async () => {
  await initBrowser();

  app.listen(BOT_PORT, () => {
    console.log("[CEO Bot] Server started");
    console.log(`[CEO Bot] Listening on port ${BOT_PORT}`);
    console.log(`[CEO Bot] Target: ${APP_URL}`);
  });
};

startServer();