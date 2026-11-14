import { chromium } from 'playwright';

const BASE = 'http://127.0.0.1:8000';
const consoleMessages = [];
const pageErrors = [];
const failedRequests = [];
const fileProtocolRequests = [];

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  page.on('console', msg => {
    const line = `BROWSER CONSOLE: ${msg.type()} ${msg.text()}`;
    consoleMessages.push(line);
    console.log(line);
  });

  page.on('pageerror', err => {
    const line = `PAGE ERROR: ${err.message}`;
    pageErrors.push(line);
    console.log(line);
  });

  page.on('requestfailed', req => {
    const line = `REQUEST FAILED: ${req.url()} ${req.failure()?.errorText ?? 'unknown'}`;
    failedRequests.push(line);
    console.log(line);
  });

  page.on('request', req => {
    if (req.url().startsWith('file:///')) {
      fileProtocolRequests.push(req.url());
      console.log(`FILE PROTOCOL REQUEST: ${req.url()}`);
    }
  });

  console.log('--- Navigating to /dashboard ---');
  await page.goto(`${BASE}/dashboard`, { waitUntil: 'networkidle', timeout: 30000 });

  await page.evaluate(() => {
    window.__cspViolations = [];
    document.addEventListener('securitypolicyviolation', (e) => {
      window.__cspViolations.push({
        blockedURI: e.blockedURI,
        violatedDirective: e.violatedDirective,
        originalPolicy: e.originalPolicy,
        sourceFile: e.sourceFile,
        lineNumber: e.lineNumber
      });
    });
  });

  await page.waitForTimeout(1000);

  const navTargets = [
    'overview-view',
    'analytics-view',
    'network-view',
    'live-collector-view',
    'devices-view',
    'soc-alerts-view',
    'topology-view',
    'investigations-view',
    'stego-view',
    'forensics-view',
    'integrity-view',
    'reports-view',
    'settings-view',
  ];

  console.log('\n--- Switching sidebar views ---');
  for (const target of navTargets) {
    try {
      const navItem = await page.$(`a.nav-item[data-target="${target}"]`);
      if (navItem) {
        await navItem.click();
        await page.waitForTimeout(500);
        console.log(`  Switched to: ${target}`);
      } else {
        console.log(`  Nav item not found: ${target}`);
      }
    } catch (err) {
      console.log(`  Error switching to ${target}: ${err.message}`);
    }
  }

  console.log('\n--- Testing search bar ---');
  try {
    const searchInput = await page.$('#global-search');
    if (searchInput) {
      await searchInput.click();
      await searchInput.fill('test search query');
      await page.waitForTimeout(500);
      await searchInput.fill('');
    }
  } catch (err) {
    console.log(`  Search error: ${err.message}`);
  }

  console.log('\n--- Testing buttons ---');
  const buttonIds = [
    'telemetry-toggle-btn',
    'telemetry-attack-btn',
    'telemetry-reset-btn',
    'load-sample-csv-btn',
    'refresh-history-btn',
    'refresh-collector-btn',
    'refresh-devices-btn',
    'refresh-investigations-btn',
    'export-report-btn',
    'preview-report-btn',
    'refresh-soc-alerts-btn',
    'refresh-topology-btn',
    'export-analytics-btn',
  ];

  for (const btnId of buttonIds) {
    try {
      const navTarget = await page.$(`a.nav-item[data-target="${getViewForButton(btnId)}"]`);
      if (navTarget) {
        await navTarget.click();
        await page.waitForTimeout(300);
      }

      const btn = await page.$(`#${btnId}`);
      if (btn && await btn.isVisible()) {
        await btn.click();
        await page.waitForTimeout(300);
        console.log(`  Clicked: ${btnId}`);
      } else {
        console.log(`  Button not visible/found: ${btnId}`);
      }
    } catch (err) {
      console.log(`  Button error (${btnId}): ${err.message}`);
    }
  }

  console.log('\n--- Testing modals ---');
  try {
    const navInv = await page.$('a.nav-item[data-target="investigations-view"]');
    if (navInv) await navInv.click();
    await page.waitForTimeout(300);
    const addInvBtn = await page.$('#add-investigation-modal-btn');
    if (addInvBtn && await addInvBtn.isVisible()) {
      await addInvBtn.click();
      await page.waitForTimeout(500);
      console.log('  Opened investigation modal');
      const closeBtn = await page.$('#close-investigation-modal-btn');
      if (closeBtn) {
        await closeBtn.click();
        await page.waitForTimeout(300);
        console.log('  Closed investigation modal');
      }
    }
  } catch (err) {
    console.log(`  Modal error: ${err.message}`);
  }

  try {
    const navDev = await page.$('a.nav-item[data-target="devices-view"]');
    if (navDev) await navDev.click();
    await page.waitForTimeout(300);
    const addDevBtn = await page.$('#add-device-modal-btn');
    if (addDevBtn && await addDevBtn.isVisible()) {
      await addDevBtn.click();
      await page.waitForTimeout(500);
      console.log('  Opened device modal');
      const closeBtn = await page.$('#close-device-modal-btn');
      if (closeBtn) {
        await closeBtn.click();
        await page.waitForTimeout(300);
        console.log('  Closed device modal');
      }
    }
  } catch (err) {
    console.log(`  Device modal error: ${err.message}`);
  }

  console.log('\n--- Testing file inputs (change event simulation) ---');
  const fileInputIds = ['log-file-input', 'embed-image', 'extract-image', 'forensics-file', 'integrity-file'];
  for (const inputId of fileInputIds) {
    try {
      const viewMap = {
        'log-file-input': 'network-view',
        'embed-image': 'stego-view',
        'extract-image': 'stego-view',
        'forensics-file': 'forensics-view',
        'integrity-file': 'integrity-view',
      };
      const navTarget = await page.$(`a.nav-item[data-target="${viewMap[inputId]}"]`);
      if (navTarget) {
        await navTarget.click();
        await page.waitForTimeout(300);
      }
      const input = await page.$(`#${inputId}`);
      if (input) {
        console.log(`  Found file input: ${inputId}`);
      } else {
        console.log(`  File input not found: ${inputId}`);
      }
    } catch (err) {
      console.log(`  File input error (${inputId}): ${err.message}`);
    }
  }

  console.log('\n--- Testing drop zone ---');
  try {
    const navNet = await page.$('a.nav-item[data-target="network-view"]');
    if (navNet) await navNet.click();
    await page.waitForTimeout(300);
    const dropZone = await page.$('#network-drop-zone');
    if (dropZone) {
      console.log('  Found network drop zone');
      await dropZone.dispatchEvent('dragover');
      await page.waitForTimeout(200);
      await dropZone.dispatchEvent('dragleave');
      await page.waitForTimeout(200);
      console.log('  Dispatched drag events on drop zone');
    }
  } catch (err) {
    console.log(`  Drop zone error: ${err.message}`);
  }

  console.log('\n--- Testing quick tool buttons ---');
  try {
    const navOv = await page.$('a.nav-item[data-target="overview-view"]');
    if (navOv) await navOv.click();
    await page.waitForTimeout(300);
    const toolBtns = await page.$$('button.tool-btn[data-action="switch-view"]');
    for (const tb of toolBtns) {
      const text = await tb.textContent();
      await tb.click();
      await page.waitForTimeout(300);
      console.log(`  Clicked quick tool: ${text.trim()}`);
      await navOv.click();
      await page.waitForTimeout(200);
    }
  } catch (err) {
    console.log(`  Quick tool error: ${err.message}`);
  }

  await page.waitForTimeout(1500);

  console.log('\n--- Collecting CSP Violations ---');
  const cspViolations = await page.evaluate(() => window.__cspViolations);
  console.log(`CSP Violations found: ${cspViolations.length}`);
  if (cspViolations.length > 0) {
    for (const v of cspViolations) {
      console.log(`  blockedURI: ${v.blockedURI}`);
      console.log(`  violatedDirective: ${v.violatedDirective}`);
      console.log(`  sourceFile: ${v.sourceFile}:${v.lineNumber}`);
      console.log(`  originalPolicy: ${v.originalPolicy}`);
      console.log('  ---');
    }
  }

  console.log('\n--- file:/// protocol requests ---');
  if (fileProtocolRequests.length > 0) {
    for (const url of fileProtocolRequests) {
      console.log(`  ${url}`);
    }
  } else {
    console.log('  None detected');
  }

  console.log('\n\n========== FINAL REPORT ==========');
  console.log(`\nBrowser Console Messages: ${consoleMessages.length}`);
  for (const m of consoleMessages) console.log(`  ${m}`);

  console.log(`\nPage Errors: ${pageErrors.length}`);
  for (const e of pageErrors) console.log(`  ${e}`);

  console.log(`\nFailed Requests: ${failedRequests.length}`);
  for (const f of failedRequests) console.log(`  ${f}`);

  console.log(`\nCSP Violations: ${cspViolations.length}`);
  for (const v of cspViolations) {
    console.log(`  Blocked: ${v.blockedURI} | Directive: ${v.violatedDirective} | Source: ${v.sourceFile}:${v.lineNumber}`);
  }

  console.log(`\nfile:/// Protocol Requests: ${fileProtocolRequests.length}`);
  for (const f of fileProtocolRequests) console.log(`  ${f}`);

  console.log('\n===================================');

  await browser.close();
  process.exit(0);
})();

function getViewForButton(btnId) {
  const map = {
    'telemetry-toggle-btn': 'overview-view',
    'telemetry-attack-btn': 'overview-view',
    'telemetry-reset-btn': 'overview-view',
    'load-sample-csv-btn': 'network-view',
    'refresh-history-btn': 'network-view',
    'refresh-collector-btn': 'live-collector-view',
    'refresh-devices-btn': 'devices-view',
    'refresh-investigations-btn': 'investigations-view',
    'export-report-btn': 'reports-view',
    'preview-report-btn': 'reports-view',
    'refresh-soc-alerts-btn': 'soc-alerts-view',
    'refresh-topology-btn': 'topology-view',
    'export-analytics-btn': 'analytics-view',
  };
  return map[btnId] || 'overview-view';
}
