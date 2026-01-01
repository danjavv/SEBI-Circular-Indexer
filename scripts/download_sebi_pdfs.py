#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import time
import os
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
from typing import List, Tuple

def setup_driver() -> webdriver.Chrome:
    """Set up Chrome driver for web scraping"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Run in background
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

    # Enable downloading in headless mode
    chrome_options.add_experimental_option('prefs', {
        'download.prompt_for_download': False,
        'download.directory_upgrade': True,
        'safebrowsing.enabled': True
    })

    driver = webdriver.Chrome(options=chrome_options)
    return driver


def get_circular_detail_links(driver: webdriver.Chrome, max_pages: int = 5) -> List[str]:
    """Extract all circular detail page links from the first N pages"""
    all_detail_links = []
    current_page = 1

    try:
        while current_page <= max_pages:
            print(f"Scraping page {current_page}/{max_pages}...")

            # Wait for page to load
            time.sleep(2)

            # Get page source and parse with BeautifulSoup
            soup = BeautifulSoup(driver.page_source, 'html.parser')

            # Find the main table with circulars
            tables = soup.find_all('table')
            if tables:
                main_table = max(tables, key=lambda t: len(t.find_all('tr')))
                rows = main_table.find_all('tr')

                # Extract links from table rows
                for row in rows[1:]:  # Skip header row
                    links = row.find_all('a', href=True)
                    for link in links:
                        href = link.get('href', '')
                        # Look for circular detail pages (HTML pages under /legal/circulars/)
                        if '/legal/circulars/' in href and '.html' in href:
                            full_url = href if href.startswith('http') else f"https://www.sebi.gov.in{href}"
                            if full_url not in all_detail_links:
                                all_detail_links.append(full_url)

            print(f"  Found {len(all_detail_links)} unique circulars so far")

            # Check if we've reached max pages
            if current_page >= max_pages:
                print(f"Reached page limit: {max_pages}")
                break

            # Try to find and click "Next" button
            try:
                # Re-parse page to get fresh links
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                pagination_links = soup.find_all('a', href=True)

                next_found = False
                for link in pagination_links:
                    link_text = link.get_text(strip=True)
                    if 'Next' in link_text:
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
        print(f"Error during page scraping: {e}")

    return all_detail_links


def find_pdf_link(detail_url: str) -> Tuple[str, str]:
    """
    Visit a circular detail page and find the PDF download link
    Returns: (pdf_url, filename)
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(detail_url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Look for iframe with embedded PDF (SEBI embeds PDFs in iframes)
        iframes = soup.find_all('iframe')
        for iframe in iframes:
            src = iframe.get('src', '')
            if 'file=' in src:
                # Extract PDF URL from iframe src (format: ../../../web/?file=https://www.sebi.gov.in/sebi_data/...)
                import re
                match = re.search(r'file=(https?://[^\s&"\']+\.pdf)', src)
                if match:
                    pdf_url = match.group(1)

                    # Generate filename from URL
                    if '/' in pdf_url:
                        filename = pdf_url.split('/')[-1]
                        # Clean filename
                        filename = filename.split('?')[0]  # Remove query parameters
                    else:
                        filename = f"{int(time.time() * 1000)}.pdf"

                    return pdf_url, filename

        # Fallback: Look for direct PDF links
        pdf_links = []

        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            if '.pdf' in href.lower():
                full_url = href if href.startswith('http') else f"https://www.sebi.gov.in{href}"
                pdf_links.append(full_url)

        if pdf_links:
            # Use the first PDF link found
            pdf_url = pdf_links[0]

            # Generate filename from URL or timestamp
            if '/' in pdf_url:
                filename = pdf_url.split('/')[-1]
                filename = filename.split('?')[0]
            else:
                filename = f"{int(time.time() * 1000)}.pdf"

            return pdf_url, filename

        return None, None

    except Exception as e:
        print(f"  Error finding PDF link: {e}")
        return None, None


def download_pdf(pdf_url: str, filename: str, output_dir: str) -> bool:
    """Download a PDF file to the specified directory"""
    try:
        # Create output directory if it doesn't exist
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        output_path = os.path.join(output_dir, filename)

        # Skip if file already exists
        if os.path.exists(output_path):
            print(f"  File already exists: {filename}")
            return True

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(pdf_url, headers=headers, timeout=30, stream=True)
        response.raise_for_status()

        # Write PDF to file
        total_size = 0
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    total_size += len(chunk)

        print(f"  Downloaded: {filename} ({total_size / 1024:.1f} KB)")
        return True

    except Exception as e:
        print(f"  Error downloading PDF: {e}")
        return False


def main():
    base_url = "https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=1&ssid=7&smid=0"
    max_pages = 5
    output_dir = "downloaded_circulars"

    print("=" * 80)
    print("SEBI Circular PDF Downloader")
    print("=" * 80)
    print(f"Downloading circulars from first {max_pages} pages")
    print(f"Output directory: {output_dir}")
    print()

    # Step 1: Get all circular detail page links
    print("Step 1: Collecting circular detail page links...")
    print("-" * 80)

    driver = setup_driver()

    try:
        driver.get(base_url)

        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        detail_links = get_circular_detail_links(driver, max_pages)

    finally:
        driver.quit()

    if not detail_links:
        print("No circular detail links found!")
        return

    print(f"\nFound {len(detail_links)} circular detail pages")
    print()

    # Step 2: Download PDFs
    print("Step 2: Downloading PDF files...")
    print("-" * 80)
    print()

    downloaded_count = 0
    skipped_count = 0
    failed_count = 0

    for idx, detail_url in enumerate(detail_links, 1):
        print(f"[{idx}/{len(detail_links)}] Processing circular...")

        # Find PDF link on detail page
        pdf_url, filename = find_pdf_link(detail_url)

        if not pdf_url:
            print(f"  No PDF link found")
            failed_count += 1
            continue

        # Download the PDF
        if download_pdf(pdf_url, filename, output_dir):
            if os.path.exists(os.path.join(output_dir, filename)):
                file_size = os.path.getsize(os.path.join(output_dir, filename))
                if file_size > 0:
                    downloaded_count += 1
                else:
                    skipped_count += 1
        else:
            failed_count += 1

        # Be polite to the server
        time.sleep(1)

    # Summary
    print()
    print("=" * 80)
    print("DOWNLOAD SUMMARY")
    print("=" * 80)
    print(f"Total circulars processed: {len(detail_links)}")
    print(f"Successfully downloaded: {downloaded_count}")
    print(f"Skipped (already exists): {skipped_count}")
    print(f"Failed: {failed_count}")
    print(f"\nPDFs saved to: {output_dir}/")
    print("=" * 80)


if __name__ == "__main__":
    main()
