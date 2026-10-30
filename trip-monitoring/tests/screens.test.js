// Browser flows on the mock transport (file://, no sign-in). Playwright is preinstalled in cloud
// sessions and is not a project dependency. Screenshots are replaced on every run.
const test = require('node:test');
const assert = require('node:assert');
const path = require('node:path');
const fs = require('node:fs');
const { chromium } = require('playwright');

const WEB = 'file://' + path.join(__dirname, '../src/web/');
const SHOTS = path.join(__dirname, '../docs/screens/m1-screens');
const WIDTHS = [[1280, 800], [768, 1024], [375, 800]];
const USERS = { requestor: 'USR-0001', driver: 'USR-0002', supervisor: 'USR-0003', accounting: 'USR-0004', admin: 'USR-0005' };

async function open() {
  const browser = await chromium.launch();
  const page = await (await browser.newContext()).newPage();
  const problems = [];
  page.on('console', (m) => { if (m.type() === 'error') problems.push('console: ' + m.text()); });
  page.on('pageerror', (e) => problems.push('pageerror: ' + e.message));
  page.on('requestfailed', (r) => problems.push('request failed: ' + r.url()));
  await page.goto(WEB + 'index.html');
  await page.waitForSelector('#role-switch');
  return { browser, page, problems };
}
const as = async (page, role) => { await page.selectOption('#role-switch', USERS[role]); };
const shoot = async (page, name) => {
  fs.mkdirSync(SHOTS, { recursive: true });
  const original = page.viewportSize();
  for (const [w, h] of WIDTHS) {
    await page.setViewportSize({ width: w, height: h });
    await page.screenshot({ path: path.join(SHOTS, `${name}-${w}.png`), fullPage: true });
  }
  await page.setViewportSize(original);
};
const noHorizontalScroll = (page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);

test('list: empty state, role visibility, filter, no console errors at three widths', async () => {
  const { browser, page, problems } = await open();
  try {
    assert.match(await page.textContent('#list'), /No trips to show/);
    for (const [w, h] of WIDTHS) {
      await page.setViewportSize({ width: w, height: h });
      assert.ok(await noHorizontalScroll(page), `no horizontal scroll at ${w}`);
    }
    await shoot(page, 'list-empty');
    await as(page, 'supervisor');
    assert.ok(await page.isHidden('#new-trip'));
    assert.deepStrictEqual(problems, []);
  } finally { await browser.close(); }
});

test('form: full flow Draft to Completed with a return to Draft, list shows role-visible trips', async () => {
  const { browser, page, problems } = await open();
  try {
    // requestor creates a Draft
    await page.click('#new-trip');
    await page.fill('#purpose', 'Site visit (fake)');
    await page.click('#save');
    await page.waitForSelector('#add-traveller');
    assert.match(await page.textContent('#messages'), /Trip created/);
    assert.match(await page.textContent('h2'), /Draft/);
    await page.selectOption('#traveller', USERS.driver);
    await page.click('#add-traveller');
    await page.fill('#start-input', '1000');
    await page.click('#save-start');
    await page.fill('#purpose', 'Site visit edited (fake)');
    await page.click('#save');
    assert.match(await page.textContent('#messages'), /Trip saved/);
    await shoot(page, 'form-draft');
    await page.click('#submit-trip');
    assert.match(await page.textContent('h2'), /Submitted/);
    assert.ok(await page.isDisabled('#purpose'), 'a submitted trip is read-only');

    // supervisor returns it, with a reason
    await as(page, 'supervisor');
    await page.click('#return-trip');
    assert.match(await page.textContent('#messages'), /reason is required/);
    await page.fill('#reason', 'Add the end reading');
    await page.click('#return-trip');
    assert.match(await page.textContent('h2'), /Draft/);

    // requestor finishes the readings and submits again; supervisor validates
    await as(page, 'requestor');
    await page.fill('#end-input', '1050');
    await page.click('#save-end');
    await page.click('#submit-trip');
    await as(page, 'supervisor');
    await shoot(page, 'form-submitted');
    await page.click('#validate-trip');
    assert.match(await page.textContent('h2'), /Trip validated/);

    // accounting completes
    await as(page, 'accounting');
    await page.click('#complete-trip');
    assert.match(await page.textContent('h2'), /Completed/);
    assert.ok(await page.isHidden('#actions'));
    await shoot(page, 'form-completed');

    // list: requestor, a different driver and accounting
    await page.click('#back');
    await page.waitForSelector('#role-switch');
    assert.strictEqual(await page.locator('#list tbody tr').count(), 1);
    await as(page, 'driver');
    assert.match(await page.textContent('#list'), /No trips to show/);
    await as(page, 'admin');
    await page.selectOption('#status-filter', 'Draft');
    assert.match(await page.textContent('#list'), /No trips to show/);
    await page.selectOption('#status-filter', 'Completed');
    assert.strictEqual(await page.locator('#list tbody tr').count(), 1);
    await shoot(page, 'list');
    assert.deepStrictEqual(problems, []);
  } finally { await browser.close(); }
});

test('form: services still refuse what the UI hides, and errors show as messages', async () => {
  const { browser, page, problems } = await open();
  try {
    await page.click('#new-trip');
    await page.fill('#purpose', '   ');
    await page.click('#save');
    assert.match(await page.textContent('#messages'), /purpose is required/);
    await as(page, 'accounting');
    assert.match(await page.textContent('#view'), /cannot create trips/);
    await page.goto(WEB + 'trip.html?id=TRP-0099');
    await page.waitForSelector('#role-switch');
    assert.match(await page.textContent('#messages'), /not found/);
    for (const [w, h] of WIDTHS) {
      await page.setViewportSize({ width: w, height: h });
      assert.ok(await noHorizontalScroll(page), `no horizontal scroll at ${w}`);
    }
    assert.deepStrictEqual(problems, []);
  } finally { await browser.close(); }
});
