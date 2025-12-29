#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import re
import time
from typing import Dict, List, Tuple, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options

def setup_driver() -> webdriver.Chrome:
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Run in background
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

    driver = webdriver.Chrome(options=chrome_options)
    return driver


def extract_circulars_from_page(driver: webdriver.Chrome) -> List[Tuple[str, str]]:
    circular_links = []

    # Wait for page to load
    time.sleep(2)

    # Get page source and parse with BeautifulSoup
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    # Find all circular links
    links = soup.find_all('a', href=True)

    for link in links:
        href = link.get('href', '')
        # Filter for circular detail pages
        if 'HomeAction.do?doListingDetails=yes' in href or 'circular' in href.lower():
            title = link.get_text(strip=True)
            if title and len(title) > 10:  # Filter out empty or very short links
                full_url = href if href.startswith('http') else f"https://www.sebi.gov.in{href}"
                circular_links.append((title, full_url))

    return circular_links


def get_circular_links_all_pages(base_url: str, max_pages: Optional[int] = None) -> List[Tuple[str, str]]:
    print("Initializing browser automation...")
    driver = setup_driver()

    all_circular_links = []
    current_page = 1

    try:
        print(f"Fetching page {current_page}...")
        driver.get(base_url)

        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        while True:
            # Extract circulars from current page
            page_circulars = extract_circulars_from_page(driver)
            print(f"  Found {len(page_circulars)} circulars on page {current_page}")
            all_circular_links.extend(page_circulars)

            # Check if we've reached max pages
            if max_pages and current_page >= max_pages:
                print(f"Reached maximum page limit: {max_pages}")
                break

            # Try to find and click "Next" button
            try:
                # Find all links in pagination
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                pagination_links = soup.find_all('a', href=True)

                next_found = False
                for link in pagination_links:
                    if 'Next' in link.get_text(strip=True):
                        # Extract the JavaScript function call
                        href = link.get('href', '')
                        if 'searchFormNewsList' in href:
                            # Execute JavaScript to go to next page
                            driver.execute_script(href.replace('javascript:', '').strip())
                            current_page += 1
                            print(f"Navigating to page {current_page}...")
                            time.sleep(3)  # Wait for page to load
                            next_found = True
                            break

                if not next_found:
                    print("No more pages available (Next button not found)")
                    break

            except (NoSuchElementException, TimeoutException) as e:
                print(f"Reached last page or error navigating: {e}")
                break

    except Exception as e:
        print(f"Error during scraping: {e}")
    finally:
        driver.quit()
        print(f"\nTotal circulars collected from {current_page} page(s): {len(all_circular_links)}")

    return all_circular_links


def extract_circular_number(url: str) -> str:
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Common patterns for SEBI circular numbers
        patterns = [
            r'SEBI/HO/[A-Z0-9/-]+/\d+',  # Standard SEBI format
            r'HO/[A-Z0-9/-]+/\d+',  # Without SEBI prefix
            r'[A-Z]{2,}/[A-Z0-9/-]+/\d+',  # Other formats
            r'No\.\s*([A-Z0-9/-]+/\d+)',  # With "No." prefix
            r'Ref\.\s*No\.\s*:?\s*([A-Z0-9/-]+/\d+)',  # With "Ref. No."
            r'Circular\s*No\.\s*:?\s*([A-Z0-9/-]+/\d+)',  # With "Circular No."
        ]

        text_content = soup.get_text()

        # Try each pattern
        for pattern in patterns:
            matches = re.findall(pattern, text_content)
            if matches:
                # Return the first match
                return matches[0] if isinstance(matches[0], str) else matches[0]

        # If no pattern matches, look for common indicators
        # Search in first 2000 characters where circular numbers usually appear
        preview = text_content[:2000]

        # Look for lines containing "Circular" or "Reference"
        lines = preview.split('\n')
        for line in lines:
            if any(keyword in line for keyword in ['Circular No', 'Ref. No', 'Reference No', 'SEBI/HO']):
                # Extract anything that looks like a reference number
                ref_match = re.search(r'[A-Z]{2,}[/][A-Z0-9/()-]+/\d+', line)
                if ref_match:
                    return ref_match.group(0)

        return "Not Found"

    except Exception as e:
        print(f"Error extracting from {url}: {str(e)}")
        return "Error"


def main():
    base_url = "https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=1&ssid=7&smid=0"

    # Set max_pages to limit scraping (None for all pages, or specify a number like 5)
    # Note: There are 109+ pages total, so scraping all may take a while
    max_pages = 2  # Change to None to scrape all pages

    print("=" * 80)
    print("SEBI Circular Scraper with Pagination Support")
    print("=" * 80)
    print()

    # Get circular links from all pages
    circular_links = get_circular_links_all_pages(base_url, max_pages)

    if not circular_links:
        print("No circular links found!")
        return

    print(f"\nExtracting circular numbers from {len(circular_links)} circulars...")
    print("-" * 80)
    print()

    results: Dict[str, str] = {}

    # Extract circular numbers
    for idx, (title, url) in enumerate(circular_links, 1):
        print(f"[{idx}/{len(circular_links)}] Processing: {title[:60]}...")
        circular_number = extract_circular_number(url)
        results[title] = circular_number

        # Be polite to the server
        time.sleep(0.5)

    # Display results
    print("\n" + "=" * 80)
    print("RESULTS: Circular Title -> Circular Number")
    print("=" * 80)
    print()

    # Save to file
    output_file = "sebi_circular_numbers.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("SEBI Circular Numbers Mapping\n")
        f.write("=" * 80 + "\n\n")

        for idx, (title, number) in enumerate(results.items(), 1):
            # Print to console
            print(f"{idx}. {title}")
            print(f"   Circular No: {number}")
            print()

            # Write to file
            f.write(f"{idx}. {title}\n")
            f.write(f"   Circular No: {number}\n\n")

        # Summary
        found_count = sum(1 for num in results.values() if num not in ["Not Found", "Error"])

        f.write("=" * 80 + "\n")
        f.write(f"Summary: Successfully extracted {found_count}/{len(results)} circular numbers\n")
        f.write("=" * 80 + "\n")

    print("=" * 80)
    print(f"Summary: Successfully extracted {found_count}/{len(results)} circular numbers")
    print("=" * 80)
    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()
