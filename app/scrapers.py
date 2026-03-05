"""
Scrapers for Philippine government business registration systems.
Uses Playwright for browser automation.
"""

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import asyncio
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("bizreg.scrapers")


class ScraperError(Exception):
    """Base exception for scraper errors"""
    pass


class DTIBNRSScraper:
    """Scraper for DTI Business Name Registration System (BNRS)"""

    BASE_URL = "https://bnrs.dti.gov.ph/"

    async def check_name(self, business_name: str, scope: str = "national") -> Dict[str, Any]:
        """
        Check if a business name is available in DTI BNRS.

        Args:
            business_name: The proposed business name to check
            scope: Territorial scope - 'barangay', 'city', 'regional', or 'national'

        Returns:
            Dict with keys: available (bool), message (str), details (dict)
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                logger.info(f"Navigating to DTI BNRS: {self.BASE_URL}")
                await page.goto(self.BASE_URL, timeout=30000)

                # Wait for the page to load
                await page.wait_for_load_state("networkidle", timeout=15000)

                # Look for name search functionality - the actual selectors may need adjustment
                # Based on typical BNRS interface:
                # 1. Click on "Search Business Name" or similar
                # 2. Enter business name in text field
                # 3. Select scope/territory
                # 4. Submit and read result

                # Try to find and use the search feature
                # This is a template implementation - actual selectors need real testing

                # Look for common search patterns
                search_input = await page.query_selector("input[name*='search'], input[name*='business'], input[placeholder*='Business']")
                if search_input:
                    await search_input.fill(business_name)
                else:
                    # Alternative: try to find a search button first
                    search_button = await page.query_selector("button:has-text('Search'), a:has-text('Search'), button:has-text('Name'), a:has-text('Name')")
                    if search_button:
                        await search_button.click()
                        await page.wait_for_timeout(2000)
                        # After clicking search, we might get a search form
                        search_input = await page.query_selector("input[type='text']")
                        if search_input:
                            await search_input.fill(business_name)

                # Scope selection - if present
                scope_select = await page.query_selector("select[name*='scope'], select[name*='territory'], select")
                if scope_select:
                    await scope_select.select_option(label=scope.title())

                # Submit the search
                submit_button = await page.query_selector("button[type='submit'], input[type='submit'], button:has-text('Check'), button:has-text('Search')")
                if submit_button:
                    await submit_button.click()
                    await page.wait_for_timeout(3000)

                # Parse results
                # The actual result parsing depends on the website's response format
                # We'll look for indicators of availability

                content = await page.content()
                text_content = await page.text_content("body")

                # Simple heuristics - these would need refinement based on actual site behavior
                available = False
                message = "Unable to determine availability"

                if "available" in text_content.lower():
                    available = True
                    message = "Business name appears to be available"
                elif "not available" in text_content.lower() or "already exists" in text_content.lower() or "taken" in text_content.lower():
                    available = False
                    message = "Business name is not available"
                else:
                    # If we got this far without clear indicators, assume we need to check differently
                    # For MVP, we'll simulate a reasonable response based on common patterns
                    logger.warning("Could not determine DTI result from content, using fallback")
                    # In production, this would throw an error or require manual review
                    raise ScraperError("Could not parse DTI response - website layout may have changed")

                return {
                    "available": available,
                    "message": message,
                    "source": "DTI BNRS",
                    "url": self.BASE_URL,
                    "scope": scope
                }

            except PlaywrightTimeoutError as e:
                logger.error(f"DTI scraper timeout: {e}")
                raise ScraperError(f"Timeout accessing DTI BNRS: {e}")
            except Exception as e:
                logger.error(f"DTI scraper error: {e}")
                raise ScraperError(f"Error scraping DTI: {e}")
            finally:
                await browser.close()


class SECCRSScraper:
    """Scraper for SEC Company Registration System (CRS) and eSPARC"""

    BASE_URL_CRS = "https://crs.sec.gov.ph/"
    BASE_URL_ESPARC = "https://esparc.sec.gov.ph/application/name-verification"

    async def check_name(self, business_name: str, company_type: str = "corporation") -> Dict[str, Any]:
        """
        Check if a company name is available in SEC.

        Args:
            business_name: The proposed company name to check
            company_type: Type of entity - 'corporation', 'partnership', 'foreign', etc.

        Returns:
            Dict with keys: available (bool), message (str), details (dict)
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                # Prefer eSPARC for domestic corporations
                url = self.BASE_URL_ESPARC if company_type == "corporation" else self.BASE_URL_CRS
                logger.info(f"Navigating to SEC: {url}")
                await page.goto(url, timeout=30000)
                await page.wait_for_load_state("networkidle", timeout=15000)

                # eSPARC has a public name verification search
                # Look for the name verification input field

                name_input = await page.query_selector("input[name*='name'], input[id*='name'], input[placeholder*='Company'], input[type='text']:visible")
                if name_input:
                    await name_input.fill(business_name)
                else:
                    # Try to navigate to a search page
                    search_link = await page.query_selector("a:has-text('Search'), a:has-text('Verify')")
                    if search_link:
                        await search_link.click()
                        await page.wait_for_timeout(2000)
                        name_input = await page.query_selector("input[type='text']:visible")
                        if name_input:
                            await name_input.fill(business_name)

                # Submit the verification
                submit_button = await page.query_selector("button[type='submit'], input[type='submit'], button:has-text('Verify'), button:has-text('Search')")
                if submit_button:
                    await submit_button.click()
                    await page.wait_for_timeout(3000)

                # Parse results
                content = await page.content()
                text_content = await page.text_content("body")

                available = False
                message = "Unable to determine availability"

                if "available" in text_content.lower() or "may be used" in text_content.lower() or "approved" in text_content.lower():
                    available = True
                    message = "Company name appears to be available"
                elif "not available" in text_content.lower() or "already exists" in text_content.lower() or "reserved" in text_content.lower() or "similar" in text_content.lower():
                    available = False
                    message = "Company name is not available"
                else:
                    logger.warning("Could not determine SEC result from content, using fallback")
                    raise ScraperError("Could not parse SEC response - website layout may have changed")

                return {
                    "available": available,
                    "message": message,
                    "source": "SEC eSPARC/CRS",
                    "url": url,
                    "company_type": company_type
                }

            except PlaywrightTimeoutError as e:
                logger.error(f"SEC scraper timeout: {e}")
                raise ScraperError(f"Timeout accessing SEC: {e}")
            except Exception as e:
                logger.error(f"SEC scraper error: {e}")
                raise ScraperError(f"Error scraping SEC: {e}")
            finally:
                await browser.close()


# Synchronous wrapper functions for easy calling from FastAPI

def check_dti_name(business_name: str, scope: str = "national") -> Dict[str, Any]:
    """Synchronous wrapper for DTI name check"""
    return asyncio.run(DTIBNRSScraper().check_name(business_name, scope))


def check_sec_name(business_name: str, company_type: str = "corporation") -> Dict[str, Any]:
    """Synchronous wrapper for SEC name check"""
    return asyncio.run(SECCRSScraper().check_name(business_name, company_type))
