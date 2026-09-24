const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();
  
  // Set viewport for a nice desktop screenshot
  await page.setViewport({ width: 1280, height: 800 });

  // 1. Dashboard
  await page.goto('http://localhost:5173/');
  // Wait a bit for the frontend to fetch cases from the backend
  await new Promise(r => setTimeout(r, 2000));
  await page.screenshot({ path: '../reports/figures/dashboard.png', fullPage: true });
  console.log('Saved dashboard.png');

  // 2. Analytics
  await page.goto('http://localhost:5173/analytics');
  await new Promise(r => setTimeout(r, 2000));
  await page.screenshot({ path: '../reports/figures/analytics.png', fullPage: true });
  console.log('Saved analytics.png');

  // 3. Settings
  await page.goto('http://localhost:5173/settings');
  await new Promise(r => setTimeout(r, 1000));
  await page.screenshot({ path: '../reports/figures/settings.png', fullPage: true });
  console.log('Saved settings.png');

  await browser.close();
})();
