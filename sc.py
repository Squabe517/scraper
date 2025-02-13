import asyncio
from playwright.async_api import async_playwright


async def capture_high_detail_screenshot(url: str, output_path: str):
    async with async_playwright() as p:
        # Launch a headless Chromium browser
        browser = await p.chromium.launch(headless=True)
        
        # Create a new browser context with a high-resolution viewport.
        # device_scale_factor increases pixel density for a crisper image.
        context = await browser.new_context(
            viewport={"width": 1024, "height": 800},
            device_scale_factor=2
        )
        
        
        page = await context.new_page()
        # Navigate to the URL and wait until network is idle
        try:
            # Attempt to wait until the network is idle.
            await asyncio.wait_for(
                page.goto(url, wait_until="networkidle"),
                timeout=2  # Wait at most 2 seconds.
            )
        except asyncio.TimeoutError:
            print("Network did not settle within 2 seconds; capturing screenshot anyway.")
            # Optionally, add a brief pause to allow any final rendering
            await asyncio.sleep(0.5)
        
        # Capture a full-page screenshot and save it as a PNG file.
        await page.screenshot(path=output_path, full_page=False)
        print(f"Screenshot saved to {output_path}")
        
        await browser.close()

# Example usage:
async def main():
    url = "https://coinmarketcap.com/currencies/solana/"
    output_path = "screenshot.png"
    await capture_high_detail_screenshot(url, output_path)

if __name__ == "__main__":
    asyncio.run(main())
