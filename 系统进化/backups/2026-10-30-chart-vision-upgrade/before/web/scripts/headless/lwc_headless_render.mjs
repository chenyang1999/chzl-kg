#!/usr/bin/env node
/**
 * Lightweight Charts 无头出图：复用 web 指标逻辑，Playwright 截图。
 * 用法: node lwc_headless_render.mjs --input payload.json --output out.png
 */
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { performance } from "node:perf_hooks";
import { chromium } from "playwright";
import { calcBullBear, calcMACD, BULL_BEAR_WARMUP_BARS } from "../../src/lib/technicalIndicators.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const LWC_JS = join(__dirname, "../../node_modules/lightweight-charts/dist/lightweight-charts.standalone.production.js");
const TEMPLATE = join(__dirname, "chart_template.html");

function parseArgs(argv) {
  const out = { input: "", output: "" };
  for (let i = 2; i < argv.length; i++) {
    if (argv[i] === "--input") out.input = argv[++i];
    else if (argv[i] === "--output") out.output = argv[++i];
  }
  if (!out.input || !out.output) {
    console.error("Usage: node lwc_headless_render.mjs --input payload.json --output out.png");
    process.exit(1);
  }
  return out;
}

function filterByTimes(points, timeSet) {
  return (points || []).filter((p) => timeSet.has(String(p.time)));
}

function filterSiSe(siSe, candles) {
  if (!siSe) return null;
  const timeSet = new Set(candles.map((c) => String(c.time)));
  const out = {};
  for (const key of Object.keys(siSe)) {
    out[key] = (siSe[key] || []).filter((b) => timeSet.has(String(b.time)));
  }
  return out;
}

export function preparePanel({ label, period, candles, volumes, source, maxBars = 120 }) {
  const need = Math.max(maxBars, BULL_BEAR_WARMUP_BARS);
  const fullCandles = candles.length > need ? candles.slice(-need) : candles;
  const bullBear = calcBullBear(fullCandles, { maXiong: 6, maJueCe: 50 });
  const macd = calcMACD(fullCandles);
  const vis = fullCandles.slice(-maxBars);
  const timeSet = new Set(vis.map((c) => String(c.time)));
  const visVolumes = (volumes || []).filter((v) => timeSet.has(String(v.time)));

  return {
    label: label || period,
    period,
    source,
    candles: vis,
    volumes: visVolumes,
    bullBear: {
      niu: filterByTimes(bullBear.niu, timeSet),
      xiong: filterByTimes(bullBear.xiong, timeSet),
      jueCe: filterByTimes(bullBear.jueCe, timeSet),
      siSeSiLiang: filterSiSe(bullBear.siSeSiLiang, vis),
    },
    macd: {
      macdLine: filterByTimes(macd.macdLine, timeSet),
      signalLine: filterByTimes(macd.signalLine, timeSet),
      histogram: filterByTimes(macd.histogram, timeSet),
    },
  };
}

function buildHtml() {
  const tpl = readFileSync(TEMPLATE, "utf8");
  const lwc = readFileSync(LWC_JS, "utf8");
  return tpl.replace("<!--LWC_INLINE-->", `<script>${lwc}</script>`);
}

export async function renderPayloadToPng(payload, outputPath, { reuseBrowser = null } = {}) {
  const timings = {};
  const t0 = performance.now();

  const panels = (payload.panels || []).map((p) =>
    preparePanel({
      label: p.label,
      period: p.period,
      candles: p.candles || [],
      volumes: p.volumes || [],
      source: p.source,
      maxBars: p.maxBars || payload.maxBars || 120,
    })
  );
  timings.prepare_ms = Math.round(performance.now() - t0);

  const renderPayload = {
    title: payload.title,
    width: payload.width || 1320,
    panels,
  };

  let browser = reuseBrowser;
  let launched = false;
  const t1 = performance.now();
  if (!browser) {
    browser = await chromium.launch({ headless: true });
    launched = true;
  }
  timings.browser_ms = Math.round(performance.now() - t1);

  const t2 = performance.now();
  const page = await browser.newPage({ viewport: { width: renderPayload.width, height: 920 } });
  const html = buildHtml();
  await page.setContent(html, { waitUntil: "load" });
  await page.evaluate((data) => window.__renderCharts(data), renderPayload);
  await page.waitForFunction(() => window.__chartsReady === true, { timeout: 15000 });
  timings.dom_ms = Math.round(performance.now() - t2);

  const t3 = performance.now();
  await page.screenshot({ path: outputPath, fullPage: true, type: "png" });
  timings.screenshot_ms = Math.round(performance.now() - t3);
  await page.close();

  if (launched) await browser.close();

  timings.total_ms = Math.round(performance.now() - t0);
  timings.renderer = "lightweight_charts_playwright";
  timings.path = resolve(outputPath);
  return timings;
}

async function main() {
  const { input, output } = parseArgs(process.argv);
  const payload = JSON.parse(readFileSync(input, "utf8"));
  const timings = await renderPayloadToPng(payload, output);
  writeFileSync(output + ".timings.json", JSON.stringify(timings, null, 2));
  console.log(JSON.stringify(timings));
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
