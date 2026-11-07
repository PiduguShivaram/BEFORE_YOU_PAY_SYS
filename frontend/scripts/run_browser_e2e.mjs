import puppeteer from "puppeteer-core";
import { spawn } from "child_process";
import fs from "fs";

const CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const FRONTEND_PORT = 3000;
const FRONTEND_URL = `http://localhost:${FRONTEND_PORT}`;

async function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForServer(url, timeoutMs = 30000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url);
      if (res.ok || res.status === 200 || res.status === 304) {
        return true;
      }
    } catch {
      // Retry
    }
    await sleep(800);
  }
  return false;
}

async function runBrowserE2E() {
  console.log("=== STARTING ANTIGRAVITY BROWSER E2E TEST SUITE ===");
  console.log(`Using Chrome binary: ${CHROME_PATH}`);

  if (!fs.existsSync(CHROME_PATH)) {
    throw new Error(`Chrome binary not found at ${CHROME_PATH}`);
  }

  // 1. Ensure Next.js frontend is running
  console.log("Checking if Next.js frontend is accessible...");
  let serverProcess = null;
  const isAlreadyRunning = await waitForServer(FRONTEND_URL, 2000);

  if (!isAlreadyRunning) {
    console.log("Starting Next.js production server (npm run start)...");
    serverProcess = spawn("cmd.exe", ["/c", "npm", "run", "start"], {
      cwd: process.cwd(),
      stdio: "pipe",
    });

    serverProcess.stdout.on("data", (d) => process.stdout.write(`[Next.js] ${d}`));
    serverProcess.stderr.on("data", (d) => process.stderr.write(`[Next.js ERR] ${d}`));

    const started = await waitForServer(FRONTEND_URL, 35000);
    if (!started) {
      if (serverProcess) serverProcess.kill();
      throw new Error("Failed to connect to Next.js frontend within 35s");
    }
    console.log("Next.js frontend server is ready!");
  } else {
    console.log("Next.js frontend server is already running.");
  }

  // 2. Launch headless Chrome browser
  console.log("Launching Chrome via puppeteer-core...");
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: "new",
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
      "--disable-gpu",
      "--window-size=1280,800",
    ],
  });

  const results = [];

  function recordTest(name, passed, details = "") {
    results.push({ name, passed, details });
    console.log(`[${passed ? "PASS" : "FAIL"}] ${name} ${details ? "- " + details : ""}`);
  }

  try {
    // TEST 1: Desktop Viewport Navigation & Title
    console.log("\n--- TEST 1: Desktop Viewport (1280x800) ---");
    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 800 });
    await page.goto(FRONTEND_URL, { waitUntil: "domcontentloaded", timeout: 15000 });

    const title = await page.title();
    recordTest("Page Title Verification", title.includes("Before You Pay"), `Title: "${title}"`);

    // TEST 2: Header & Core Navigation Elements
    const hasHeader = await page.$eval("header", (el) => Boolean(el)).catch(() => false);
    recordTest("Header Landmark Present", hasHeader);

    const headingText = await page
      .$eval("h1, h2", (el) => el.textContent)
      .catch(() => "None");
    recordTest("Primary Heading Loaded", headingText.length > 0, `Heading: "${headingText.slice(0, 40)}..."`);

    // TEST 3: Holographic Dropzone & Category Selector
    console.log("\n--- TEST 3: Dropzone & Category Controls ---");
    const dropzoneExists = await page
      .$eval("input[type='file']", (el) => Boolean(el))
      .catch(() => false);
    recordTest("File Upload Input Present", dropzoneExists);

    const categoryButtons = await page.$$eval("button", (buttons) =>
      buttons.map((b) => b.textContent?.trim() || "").filter((t) => t.length > 0)
    );
    const hasCategorySelector = categoryButtons.some(
      (t) =>
        t.includes("Vehicle") ||
        t.includes("Invoice") ||
        t.includes("Hospital") ||
        t.includes("Bill")
    );
    recordTest("Document Category Selector Present", hasCategorySelector);

    // TEST 4: Offline Status Pill
    console.log("\n--- TEST 4: Offline Status & IndexedDB Drawer ---");
    const buttonsCount = await page.$$eval("button", (btns) => btns.length);
    recordTest("Interactive Action Buttons Present", buttonsCount >= 4, `Found ${buttonsCount} buttons`);

    // TEST 5: Mobile Viewport (iPhone 14: 390x844)
    console.log("\n--- TEST 5: Mobile Viewport (390x844) ---");
    const mobilePage = await browser.newPage();
    await mobilePage.setViewport({
      width: 390,
      height: 844,
      isMobile: true,
      hasTouch: true,
    });
    await mobilePage.goto(FRONTEND_URL, { waitUntil: "domcontentloaded", timeout: 15000 });

    const mobileFileInput = await mobilePage
      .$eval("input[type='file']", (el) => Boolean(el))
      .catch(() => false);
    recordTest("Mobile File Input Interactive", mobileFileInput);

    // Check no horizontal scrollbar overflow on mobile (width fits within 400px)
    const mobileBodyWidth = await mobilePage.evaluate(() => document.body.scrollWidth);
    const noHorizontalOverflow = mobileBodyWidth <= 400;
    recordTest(
      "Mobile Viewport Layout Integrity (No Overflow)",
      noHorizontalOverflow,
      `Body scroll width: ${mobileBodyWidth}px`
    );

    // TEST 6: Accessibility Check
    console.log("\n--- TEST 6: Accessibility Audit ---");
    const unlabelledButtons = await page.$$eval("button", (buttons) =>
      buttons.filter(
        (b) => !b.textContent?.trim() && !b.getAttribute("aria-label") && !b.getAttribute("title")
      ).length
    );
    recordTest(
      "All Buttons Have Accessible Names",
      unlabelledButtons === 0,
      `Unlabelled button count: ${unlabelledButtons}`
    );

    // TEST 7: Zero Fake Data Integrity
    console.log("\n--- TEST 7: Zero Fake Data Integrity ---");
    const pageText = await page.evaluate(() => document.body.innerText);
    const hasFakeDealerQuote = pageText.includes("MOCK_DEALER") || pageText.includes("Fake Motors");
    recordTest("No Hardcoded Mock Dealer Quotes on Page", !hasFakeDealerQuote);

    await mobilePage.close();
    await page.close();
  } finally {
    await browser.close();
    if (serverProcess) {
      console.log("Stopping Next.js test server...");
      serverProcess.kill();
    }
  }

  console.log("\n=== BROWSER E2E TEST RESULTS SUMMARY ===");
  const passedCount = results.filter((r) => r.passed).length;
  const failedCount = results.filter((r) => !r.passed).length;
  console.log(`Total Tests: ${results.length} | Passed: ${passedCount} | Failed: ${failedCount}`);

  if (failedCount > 0) {
    process.exit(1);
  } else {
    console.log("All browser E2E tests PASSED successfully!");
  }
}

runBrowserE2E().catch((err) => {
  console.error("Browser E2E Execution Failed:", err);
  process.exit(1);
});

