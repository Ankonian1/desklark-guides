// Headless verification for the catalog lookbook page (build/web-content/catalog/).
// Run: node tests/verify.mjs   (from the build/web-content/catalog directory)
//
// Same battery pattern as the guides hub's own tests/verify.mjs (one level
// up), plus two checks that file specifically calls out as N/A there but
// matter here:
//   1. Page-weight budget -- html + shared styles.css + every product image
//      this page references must total under 2.5MB (task budget). Computed
//      from actual on-disk file sizes, not a guess.
//   2. file:// protocol smoke test -- confirms the page (including all 22
//      images, which use plain relative <img src> paths, not fetch/XHR) also
//      renders correctly with no HTTP server at all, the way a reviewer
//      might open it directly from disk.
//
// Also carried over from the guides' battery:
//   - No external requests (every request must resolve back to 127.0.0.1).
//   - Valid JSON-LD ItemList with exactly 22 Product items, each with the
//     required Offer fields.
//   - 320px clean (no horizontal overflow at iPhone-SE-class width).
//   - Zero console/page errors.
//   - Placeholder-token resolution (deploy-time check, added 2026-08-05):
//     zero literal "{{" survives anywhere in the rendered output. The 14
//     not-yet-live products render as inert `.catalog-card--soon` divs (no
//     href) with a "Coming soon" badge/CTA instead of a placeholder link,
//     and their JSON-LD Offer omits the "url" field entirely rather than
//     asserting a fake one. The 8 live products keep their real Etsy URLs
//     in both the card href and the JSON-LD offer.url.
//   - axe-core WCAG2A+AA scan against the HTTP-served page (skipped under
//     file://, same known CORS-on-stylesheet-fetch quirk noted in the
//     sibling calculators'/guides' own verify.mjs scripts).

import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import http from "node:http";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, ".."); // .../web-content/catalog
const HUB_ROOT = path.resolve(ROOT, ".."); // .../web-content (styles.css lives here)
const SHARED_NODE_MODULES = path.resolve(HUB_ROOT, "../web-tools/node_modules");
const SCREENSHOT_DIR = path.join(ROOT, "screenshots");
fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

const { chromium } = require(path.join(SHARED_NODE_MODULES, "playwright"));
const AXE_SOURCE_PATH = path.join(SHARED_NODE_MODULES, "axe-core", "axe.min.js");

const PAGE_WEIGHT_BUDGET_BYTES = 2.5 * 1024 * 1024;
const EXPECTED_PRODUCT_COUNT = 22;
const EXPECTED_LIVE_COUNT = 8;

const results = [];
function pass(scenario) { results.push({ scenario, status: "PASS" }); }

function extractJsonLdBlocks(html) {
  const blocks = [];
  const re = /<script type="application\/ld\+json">([\s\S]*?)<\/script>/g;
  let m;
  while ((m = re.exec(html))) blocks.push(m[1].trim());
  return blocks;
}

// ---------------------------------------------------------------------------
// 1. Page-weight budget (static, no browser needed)
// ---------------------------------------------------------------------------
function checkPageWeight() {
  const htmlPath = path.join(ROOT, "index.html");
  const cssPath = path.join(HUB_ROOT, "styles.css");
  const html = fs.readFileSync(htmlPath, "utf8");

  let total = fs.statSync(htmlPath).size + fs.statSync(cssPath).size;
  const imgRefs = [...html.matchAll(/src="(images\/[^"]+\.webp)"/g)].map((m) => m[1]);
  assert.equal(imgRefs.length, EXPECTED_PRODUCT_COUNT, `expected ${EXPECTED_PRODUCT_COUNT} product images referenced, found ${imgRefs.length}`);
  for (const rel of imgRefs) {
    const p = path.join(ROOT, rel);
    assert.ok(fs.existsSync(p), `referenced image missing on disk: ${rel}`);
    total += fs.statSync(p).size;
  }
  assert.ok(
    total <= PAGE_WEIGHT_BUDGET_BYTES,
    `page weight ${(total / 1024 / 1024).toFixed(2)}MB exceeds ${(PAGE_WEIGHT_BUDGET_BYTES / 1024 / 1024).toFixed(1)}MB budget`
  );
  pass(`page weight under budget (${(total / 1024).toFixed(1)} KB of ${(PAGE_WEIGHT_BUDGET_BYTES / 1024 / 1024).toFixed(1)} MB)`);
  return { html, total, imgRefs };
}

// ---------------------------------------------------------------------------
// 2. JSON-LD ItemList validity + product count + live/placeholder split
// ---------------------------------------------------------------------------
function checkJsonLd(html) {
  const blocks = extractJsonLdBlocks(html);
  assert.equal(blocks.length, 1, "expected exactly one JSON-LD block");
  let doc;
  try {
    doc = JSON.parse(blocks[0]);
  } catch (e) {
    throw new Error(`JSON-LD did not parse: ${e.message}`);
  }
  assert.equal(doc["@context"], "https://schema.org", "JSON-LD @context");
  assert.equal(doc["@type"], "ItemList", "JSON-LD @type");
  for (const field of ["name", "description", "url", "numberOfItems", "itemListElement"]) {
    assert.ok(doc[field] !== undefined, `JSON-LD ItemList missing required field "${field}"`);
  }
  assert.equal(doc.numberOfItems, EXPECTED_PRODUCT_COUNT, "numberOfItems");
  assert.equal(doc.itemListElement.length, EXPECTED_PRODUCT_COUNT, "itemListElement length");

  let liveCount = 0;
  const seenPositions = new Set();
  doc.itemListElement.forEach((li, idx) => {
    const scenario = `ItemList[${idx}]`;
    assert.equal(li["@type"], "ListItem", `${scenario} @type`);
    assert.equal(typeof li.position, "number", `${scenario} position is a number`);
    assert.ok(!seenPositions.has(li.position), `${scenario} duplicate position ${li.position}`);
    seenPositions.add(li.position);
    const item = li.item;
    assert.equal(item["@type"], "Product", `${scenario} item @type`);
    for (const field of ["name", "description", "image", "brand", "offers"]) {
      assert.ok(item[field], `${scenario} Product missing "${field}"`);
    }
    assert.ok(item.image.startsWith("https://"), `${scenario} image is an absolute URL`);
    const offer = item.offers;
    assert.equal(offer["@type"], "Offer", `${scenario} offer @type`);
    assert.match(offer.price, /^\d+\.\d{2}$/, `${scenario} offer.price is a decimal string`);
    assert.equal(offer.priceCurrency, "USD", `${scenario} offer.priceCurrency`);
    if (offer.url !== undefined) {
      assert.ok(offer.url.startsWith("https://www.etsy.com/listing/"), `${scenario} offer.url, when present, is a real Etsy listing URL (not a placeholder)`);
      liveCount += 1;
      assert.equal(offer.availability, "https://schema.org/InStock", `${scenario} live product is InStock`);
    } else {
      assert.equal(offer.availability, "https://schema.org/PreOrder", `${scenario} non-live product (no offer.url) is PreOrder`);
    }
  });
  assert.equal(liveCount, EXPECTED_LIVE_COUNT, `expected exactly ${EXPECTED_LIVE_COUNT} live Etsy offers in JSON-LD`);
  pass(`JSON-LD ItemList valid: ${EXPECTED_PRODUCT_COUNT} products, ${liveCount} live offers`);
}

// ---------------------------------------------------------------------------
// 3. Product-count / live-count sanity in the rendered markup itself
// ---------------------------------------------------------------------------
function checkMarkupCounts(html) {
  const cardMatches = [...html.matchAll(/class="catalog-card( catalog-card--live| catalog-card--soon)?"/g)];
  assert.equal(cardMatches.length, EXPECTED_PRODUCT_COUNT, `expected ${EXPECTED_PRODUCT_COUNT} .catalog-card elements, found ${cardMatches.length}`);
  const liveMatches = cardMatches.filter((m) => m[1] === " catalog-card--live");
  const soonMatches = cardMatches.filter((m) => m[1] === " catalog-card--soon");
  assert.equal(liveMatches.length, EXPECTED_LIVE_COUNT, `expected ${EXPECTED_LIVE_COUNT} .catalog-card--live elements, found ${liveMatches.length}`);
  const expectedSoon = EXPECTED_PRODUCT_COUNT - EXPECTED_LIVE_COUNT;
  assert.equal(soonMatches.length, expectedSoon, `expected ${expectedSoon} .catalog-card--soon elements, found ${soonMatches.length}`);
  // Every .catalog-card--soon must be a <div> (no href, never a broken/
  // placeholder link), never an <a>.
  const soonAnchors = (html.match(/<a class="catalog-card catalog-card--soon"/g) || []).length;
  assert.equal(soonAnchors, 0, `found ${soonAnchors} .catalog-card--soon rendered as an <a> instead of an inert <div>`);
  const soonDivs = (html.match(/<div class="catalog-card catalog-card--soon"/g) || []).length;
  assert.equal(soonDivs, expectedSoon, `expected ${expectedSoon} .catalog-card--soon <div>s, found ${soonDivs}`);
  const badgeCount = (html.match(/class="catalog-soon-badge"/g) || []).length;
  assert.equal(badgeCount, expectedSoon, `expected ${expectedSoon} "Coming soon" badges, found ${badgeCount}`);
  pass(`markup counts: ${EXPECTED_PRODUCT_COUNT} cards, ${liveMatches.length} live, ${soonMatches.length} coming-soon (all inert divs)`);
}

const MIME = { ".html": "text/html", ".css": "text/css", ".webp": "image/webp" };
function startServer(root) {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      const reqPath = decodeURIComponent(req.url.split("?")[0]);
      let filePath = path.join(root, reqPath);
      if (reqPath.endsWith("/")) filePath = path.join(filePath, "index.html");
      fs.readFile(filePath, (err, data) => {
        if (err) {
          res.writeHead(404);
          res.end("not found");
          return;
        }
        const ext = path.extname(filePath);
        res.writeHead(200, { "Content-Type": MIME[ext] || "application/octet-stream" });
        res.end(data);
      });
    });
    server.listen(0, "127.0.0.1", () => resolve(server));
  });
}

async function main() {
  const { html } = checkPageWeight();
  checkJsonLd(html);
  checkMarkupCounts(html);

  // Serve the whole web-content hub (not just catalog/) so the page's
  // "../styles.css" reference resolves the same way it will once deployed.
  const server = await startServer(HUB_ROOT);
  const port = server.address().port;
  const url = `http://127.0.0.1:${port}/catalog/index.html`;
  const browser = await chromium.launch({ headless: true });

  // ---------------- No external requests + console errors + images load ----------------
  const context = await browser.newContext({ viewport: { width: 1280, height: 1400 } });
  const page = await context.newPage();
  const externalRequests = [];
  const consoleErrors = [];
  const failedImages = [];
  page.on("request", (req) => {
    const reqUrl = new URL(req.url());
    if (reqUrl.hostname !== "127.0.0.1") externalRequests.push(req.url());
  });
  page.on("console", (msg) => { if (msg.type() === "error") consoleErrors.push(msg.text()); });
  page.on("pageerror", (err) => consoleErrors.push(String(err)));
  page.on("requestfailed", (req) => { if (req.url().endsWith(".webp")) failedImages.push(req.url()); });

  await page.goto(url, { waitUntil: "networkidle" });
  // Product images use loading="lazy" (this page is light enough that it
  // isn't needed for the weight budget, but it's still the right default
  // for a long below-the-fold grid) -- scroll the full page height so every
  // card's image actually triggers its lazy load before checking it below,
  // the same way a real reader scrolling the lookbook would see them all.
  await page.evaluate(async () => {
    const step = 400;
    for (let y = 0; y < document.body.scrollHeight; y += step) {
      window.scrollTo(0, y);
      await new Promise((r) => setTimeout(r, 30));
    }
    window.scrollTo(0, 0);
  });
  await page.waitForLoadState("networkidle");

  assert.equal(externalRequests.length, 0, `external request(s) detected: ${JSON.stringify(externalRequests)}`);
  pass("no external requests");
  assert.equal(consoleErrors.length, 0, `console/page error(s): ${JSON.stringify(consoleErrors)}`);
  pass("no console errors");
  assert.equal(failedImages.length, 0, `image request(s) failed: ${JSON.stringify(failedImages)}`);

  const brokenImages = await page.evaluate(() =>
    [...document.querySelectorAll(".catalog-card-media img")]
      .filter((img) => !img.complete || img.naturalWidth === 0)
      .map((img) => img.src)
  );
  assert.equal(brokenImages.length, 0, `image(s) failed to render: ${JSON.stringify(brokenImages)}`);
  const imgCount = await page.locator(".catalog-card-media img").count();
  assert.equal(imgCount, EXPECTED_PRODUCT_COUNT, `expected ${EXPECTED_PRODUCT_COUNT} rendered product images, found ${imgCount}`);
  pass(`all ${imgCount} product images loaded and rendered (nonzero naturalWidth)`);

  // ---------------- Placeholder-token resolution ----------------
  const bodyText = await page.content();
  assert.ok(!bodyText.includes("{{"), `unresolved "{{" placeholder token(s) found in rendered output`);
  pass("placeholder tokens resolved (zero literal \"{{\" in rendered output)");

  // ---------------- Accessibility scan (axe-core, desktop viewport) ----------------
  const axeSource = fs.readFileSync(AXE_SOURCE_PATH, "utf8");
  await page.addScriptTag({ content: axeSource });
  const axeResults = await page.evaluate(async () => {
    // eslint-disable-next-line no-undef
    return await axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa"] } });
  });
  const violations = axeResults.violations.map((v) => ({ id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.length }));
  assert.equal(violations.length, 0, `axe-core found ${violations.length} violation(s): ${JSON.stringify(violations, null, 2)}`);
  pass("axe-core clean (wcag2a + wcag2aa)");

  await context.close();

  // ---------------- 320px clean (no horizontal overflow) ----------------
  const mobileCtx = await browser.newContext({ viewport: { width: 320, height: 900 } });
  const mobilePage = await mobileCtx.newPage();
  await mobilePage.goto(url, { waitUntil: "networkidle" });
  const overflow = await mobilePage.evaluate(() => {
    const doc = document.documentElement;
    return { scrollWidth: doc.scrollWidth, clientWidth: doc.clientWidth };
  });
  assert.ok(
    overflow.scrollWidth <= overflow.clientWidth + 1,
    `horizontal overflow at 320px: scrollWidth ${overflow.scrollWidth} > clientWidth ${overflow.clientWidth}`
  );
  pass("320px clean (no horizontal overflow)");
  await mobilePage.screenshot({ path: path.join(SCREENSHOT_DIR, "catalog-320.png"), fullPage: true });
  await mobileCtx.close();

  // ---------------- Desktop screenshot for reviewer sign-off ----------------
  const desktopCtx = await browser.newContext({ viewport: { width: 1280, height: 1400 } });
  const desktopPage = await desktopCtx.newPage();
  await desktopPage.goto(url, { waitUntil: "networkidle" });
  await desktopPage.screenshot({ path: path.join(SCREENSHOT_DIR, "catalog-1280.png"), fullPage: true });
  await desktopCtx.close();

  await browser.close();
  server.close();

  // ---------------- file:// protocol smoke test ----------------
  // This page could be opened directly from a downloaded/zipped copy of the
  // site, not only served over HTTP -- confirm it still renders (all 22
  // images included, since <img src="images/<slug>.webp"> is a plain
  // relative path with no fetch/XHR involved) with zero console errors.
  // axe-core is deliberately skipped here (CORS-on-stylesheet-fetch quirk
  // under file://, same as every other page in this repo's test suites);
  // it already ran against the HTTP-served page above.
  {
    const fileBrowser = await chromium.launch({ headless: true });
    const fileCtx = await fileBrowser.newContext();
    const filePage = await fileCtx.newPage();
    const fileErrors = [];
    filePage.on("console", (msg) => { if (msg.type() === "error") fileErrors.push(msg.text()); });
    filePage.on("pageerror", (err) => fileErrors.push(String(err)));

    const fileUrl = "file://" + path.join(ROOT, "index.html");
    await filePage.goto(fileUrl, { waitUntil: "networkidle" });
    await filePage.evaluate(async () => {
      const step = 400;
      for (let y = 0; y < document.body.scrollHeight; y += step) {
        window.scrollTo(0, y);
        await new Promise((r) => setTimeout(r, 30));
      }
      window.scrollTo(0, 0);
    });
    await filePage.waitForLoadState("networkidle");

    const fileImgCount = await filePage.locator(".catalog-card-media img").count();
    assert.equal(fileImgCount, EXPECTED_PRODUCT_COUNT, `file://: expected ${EXPECTED_PRODUCT_COUNT} product images, found ${fileImgCount}`);
    const fileBrokenImages = await filePage.evaluate(() =>
      [...document.querySelectorAll(".catalog-card-media img")]
        .filter((img) => !img.complete || img.naturalWidth === 0)
        .map((img) => img.src)
    );
    assert.equal(fileBrokenImages.length, 0, `file://: image(s) failed to render: ${JSON.stringify(fileBrokenImages)}`);
    assert.equal(fileErrors.length, 0, `file:// protocol produced console/page errors: ${JSON.stringify(fileErrors)}`);

    await fileCtx.close();
    await fileBrowser.close();
    pass(`file:// protocol: page + all ${fileImgCount} images render with zero console errors, no HTTP server`);
  }

  console.log("\n=== Results ===");
  results.forEach((r) => console.log(`  PASS  ${r.scenario}`));
  console.log(`\nScreenshots written to ${SCREENSHOT_DIR}`);
  console.log(`\nAll checks passed (${results.length} assertions).`);
}

main().catch((err) => {
  console.error("\nVERIFY FAILED:", err.message);
  process.exit(1);
});
