// Browser check for slice 1. Run: node odometer-trips/tests/e2e/trip-flow.cjs
// Serves odometer-trips/ on localhost, then at 1280, 768 and 375 px (mock transport):
// adds a vehicle, triggers both odometer rejections, saves a trip, reloads, voids it.
// Then checks that the local transport keeps a trip across a reload.
// Also downloads the trips CSV and checks the header and the quoting at each width.
// Fails on any console error, page error, failed request or horizontal scroll.

const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { chromium } = require('playwright');

const ROOT = path.resolve(__dirname, '..', '..');
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.json': 'application/json' };
const WIDTHS = [[1280, 800], [768, 1024], [375, 667]];

function serve() {
  const server = http.createServer((req, res) => {
    const urlPath = decodeURIComponent(new URL(req.url, 'http://x').pathname);
    const file = path.resolve(ROOT, '.' + urlPath);
    if (!file.startsWith(ROOT + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
      res.writeHead(404).end('not found');
      return;
    }
    res.writeHead(200, { 'content-type': TYPES[path.extname(file)] || 'application/octet-stream' });
    fs.createReadStream(file).pipe(res);
  });
  return new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve(server)));
}

function watch(page, problems) {
  page.on('console', (m) => { if (m.type() === 'error') problems.push(`console: ${m.text()}`); });
  page.on('pageerror', (e) => problems.push(`pageerror: ${e.message}`));
  page.on('requestfailed', (r) => problems.push(`requestfailed: ${r.url()}`));
  page.on('response', (r) => { if (r.status() >= 400) problems.push(`http ${r.status()}: ${r.url()}`); });
}

async function open(page, url) {
  await page.goto(url);
  await page.waitForSelector('body[data-ready="true"]');
}

async function saveTrip(page, { start, end, destination }) {
  await page.getByLabel('Date').fill('2026-02-01');
  await page.getByLabel('Start km').fill(String(start));
  await page.getByLabel('End km').fill(String(end));
  await page.getByLabel('Purpose').selectOption({ label: 'Work' });
  await page.getByLabel('Destination').fill(destination);
  await page.getByRole('button', { name: 'Save trip' }).click();
}

async function noHorizontalScroll(page, label) {
  const { sw, iw } = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, iw: window.innerWidth }));
  assert.ok(sw <= iw, `${label}: page scrolls sideways (${sw} > ${iw})`);
}

async function mockFlow(browser, base, [width, height]) {
  const label = `${width}px`;
  const context = await browser.newContext({ viewport: { width, height } });
  const page = await context.newPage();
  const problems = [];
  watch(page, problems);
  const url = `${base}/app/index.html?transport=mock`;

  await open(page, url);
  await page.locator('#vehicle-list').getByText('Test Bike · TEST-001').waitFor();
  await noHorizontalScroll(page, label);

  // Add a vehicle; it becomes the selected vehicle and sets the start reading.
  await page.getByLabel('Vehicle name').fill('Test Van');
  await page.getByLabel('Plate').fill('TEST-002');
  await page.getByLabel('Fuel type').selectOption('Diesel');
  await page.getByLabel('Starting odometer (km)').fill('5000');
  await page.getByRole('button', { name: 'Add vehicle' }).click();
  await page.locator('#vehicle-list').getByText('Test Van · TEST-002').waitFor();
  assert.equal(await page.getByLabel('Start km').inputValue(), '5000', `${label}: start defaults to last end`);

  // Rejection 1: end below start.
  await saveTrip(page, { start: 5000, end: 4990, destination: 'Test Site' });
  await page.locator('#trip-error').getByText('is below the start reading').waitFor();

  // Rejection 2: start below the vehicle's last end reading.
  await saveTrip(page, { start: 4900, end: 4950, destination: 'Test Site' });
  await page.locator('#trip-error').getByText("below this vehicle's last end reading (5000 km)").waitFor();

  // Valid trip.
  await saveTrip(page, { start: 5000, end: 5042, destination: 'Test Site' });
  const trip = page.locator('#trip-list li', { hasText: 'Test Site' });
  await trip.getByText('42 km', { exact: true }).waitFor();
  assert.equal(await page.locator('#trip-error').isHidden(), true, `${label}: error cleared`);
  assert.equal(await page.getByLabel('Start km').inputValue(), '5042', `${label}: start moves to new last end`);
  await noHorizontalScroll(page, label);

  // CSV export: a destination with a comma and quotes comes back quoted in the trips file.
  await saveTrip(page, { start: 5042, end: 5050, destination: 'Shop, "North"' });
  await page.locator('#trip-list li', { hasText: 'Shop' }).getByText('8 km', { exact: true }).waitFor();
  const exportRow = page.locator('#export-list li[data-table="trips"]');
  await exportRow.getByText('3 rows', { exact: true }).waitFor();
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    exportRow.getByRole('button', { name: 'Export trips' }).click(),
  ]);
  assert.match(download.suggestedFilename(), /^odometer-trips-\d{4}-\d{2}-\d{2}\.csv$/, `${label}: file name`);
  const csv = fs.readFileSync(await download.path(), 'utf8');
  assert.ok(csv.startsWith('﻿'), `${label}: byte order mark`);
  const lines = csv.slice(1).split('\r\n');
  assert.equal(lines[0], 'id,vehicle_id,trip_date,start_km,end_km,purpose_id,destination,status,created_at,created_by,updated_at,updated_by,is_active,row_version', `${label}: header`);
  assert.equal(lines.filter((l) => l.includes('Shop')).length, 1, `${label}: one Shop row`);
  assert.ok(lines.some((l) => l.includes('"Shop, ""North"""')), `${label}: quoting`);
  await noHorizontalScroll(page, label);

  // Survives a reload.
  await open(page, url);
  await trip.getByText('42 km', { exact: true }).waitFor();

  // Void needs two taps, and the trip stays listed as Voided.
  await trip.getByRole('button', { name: 'Void' }).click();
  await trip.getByRole('button', { name: 'Confirm void' }).click();
  await page.locator('#trip-list li[data-status="Voided"]', { hasText: 'Test Site' }).waitFor();
  assert.equal(await trip.count(), 1, `${label}: voided trip is still listed`);
  await noHorizontalScroll(page, label);

  await context.close();
  assert.deepEqual(problems, [], `${label}: ${problems.join('; ')}`);
  console.log(`ok ${label} mock flow`);
}

async function localReload(browser, base) {
  const context = await browser.newContext({ viewport: { width: 768, height: 1024 } });
  const page = await context.newPage();
  const problems = [];
  watch(page, problems);
  const url = `${base}/app/index.html`;

  await open(page, url);
  assert.equal(await page.locator('#trip-list li').count(), 0, 'local store starts empty');
  await page.getByLabel('Vehicle name').fill('Test Car');
  await page.getByLabel('Plate').fill('TEST-003');
  await page.getByLabel('Fuel type').selectOption('Gasoline');
  await page.getByLabel('Starting odometer (km)').fill('200');
  await page.getByRole('button', { name: 'Add vehicle' }).click();
  await saveTrip(page, { start: 200, end: 215, destination: 'Test Shop' });
  await page.locator('#trip-list li', { hasText: 'Test Shop' }).getByText('15 km', { exact: true }).waitFor();

  await open(page, url);
  await page.locator('#trip-list li', { hasText: 'Test Shop' }).getByText('15 km', { exact: true }).waitFor();
  const stored = await page.evaluate(() => JSON.parse(localStorage.getItem('odometer-trips:v1')));
  assert.equal(stored.trips.length, 1);
  assert.ok(!('distance_km' in stored.trips[0]), 'distance is not stored');
  assert.ok(stored.audit_log.some((r) => r.table_name === 'trips' && r.action === 'create'));

  await context.close();
  assert.deepEqual(problems, [], `local: ${problems.join('; ')}`);
  console.log('ok local transport survives reload');
}

(async () => {
  const server = await serve();
  const base = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch();
  try {
    for (const size of WIDTHS) await mockFlow(browser, base, size);
    await localReload(browser, base);
    console.log('e2e: all checks passed');
  } finally {
    await browser.close();
    server.close();
  }
})().catch((e) => {
  console.error(`e2e FAILED: ${e.message}`);
  process.exit(1);
});
