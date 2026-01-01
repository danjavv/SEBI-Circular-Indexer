#!/usr/bin/env python3

import re
import os
import json
from typing import List, Dict, Tuple, Set
import PyPDF2
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic

# Load environment variables
load_dotenv()

# Configure Anthropic API
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY not found in .env file")
client = Anthropic(api_key=ANTHROPIC_API_KEY)


class CircularDatabase:
    def __init__(self, database_file: str):
        self.circulars: List[Dict[str, str]] = []
        self.load_database(database_file)

    def load_database(self, database_file: str):
        print(f"Loading circular database from {database_file}...")

        try:
            with open(database_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Parse the file to extract circular entries using regex
            # This is more reliable for structured data than LLM parsing
            # Pattern: numbered entry followed by title and circular number
            pattern = r'\d+\.\s+(.*?)\n\s+Circular No:\s+(.*?)(?=\n\n|\n\d+\.|\Z)'
            matches = re.findall(pattern, content, re.DOTALL)

            for title, circular_no in matches:
                title = title.strip()
                circular_no = circular_no.strip()

                if circular_no not in ["Not Found", "Error"]:
                    self.circulars.append({
                        'title': title,
                        'circular_no': circular_no
                    })

            print(f"Loaded {len(self.circulars)} circulars into database")

        except FileNotFoundError:
            print(f"Error: Database file {database_file} not found!")
            self.circulars = []

    def search(self, reference: str) -> List[Dict[str, str]]:
        matches = []

        # Normalize the reference for searching
        ref_normalized = reference.strip().replace(' ', '').upper()

        for circular in self.circulars:
            circ_no_normalized = circular['circular_no'].replace(' ', '').upper()

            # Check if the circular number contains the reference
            if ref_normalized in circ_no_normalized or circ_no_normalized in ref_normalized:
                matches.append(circular)

        return matches


class PDFCircularExtractor:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.text_content = ""
        self.circular_number = ""

    def extract_text(self) -> str:
        print(f"Extracting text from {self.pdf_path}...")

        try:
            with open(self.pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text_parts = []

                for page_num, page in enumerate(pdf_reader.pages, 1):
                    text = page.extract_text()
                    text_parts.append(text)

                self.text_content = '\n'.join(text_parts)
                print(f"Extracted text from {len(pdf_reader.pages)} pages")

        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
            self.text_content = ""

        return self.text_content

    def get_circular_number(self) -> str:
        # Check first 500 characters for circular number
        header = self.text_content[:500]

        try:
            # Use Claude to extract circular number
            prompt = f"""Extract the SEBI circular number from the following text, which is from the header of a PDF document.
SEBI circular numbers typically follow formats like:
- SEBI/HO/[DEPT]/[TYPE]/CIR/YYYY/NNN
- HO/[DEPT]/[TYPE]/CIR/YYYY/NNN
- [DEPT]/[TYPE]/YYYY/NNN

The circular number is usually near the top of the document, possibly after the word "CIRCULAR".

Return ONLY the circular number itself, nothing else. If you cannot find a circular number, return exactly "Unknown".

Text:
{header}

Circular Number:"""

            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=100,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            raw_response = response.content[0].text.strip()

            # Extract just the circular number from Claude's response
            # Remove common explanatory phrases using regex
            import re

            # Remove common prefixes (more comprehensive patterns)
            cleaned = raw_response

            # Remove various forms of explanatory text
            patterns = [
                r'^.*?circular\s+number\s+(?:is\s+|extracted.*?is\s*)?:?\s*',  # "The circular number is" or "extracted from ... is"
                r'^.*?circular\s+number\s*:?\s*',  # General "circular number:"
                r'^Here\s+is\s+.*?:?\s*',  # "Here is the..."
            ]

            for pattern in patterns:
                cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
                if cleaned != raw_response:
                    break  # Stop after first match

            # Take the first line if multiline
            cleaned = cleaned.split('\n')[0].strip()

            # Remove trailing punctuation
            cleaned = cleaned.rstrip('.,;:')

            # Remove ALL spaces from circular number for consistency
            cleaned = cleaned.replace(' ', '')

            self.circular_number = cleaned

            # Validate the response
            if not self.circular_number or len(self.circular_number) > 150:
                self.circular_number = "Unknown"

            return self.circular_number

        except Exception as e:
            print(f"Error extracting circular number with Claude: {e}")
            return "Unknown"

    def extract_circular_references(self) -> Set[str]:
        print("Extracting circular references...")

        references = set()

        try:
            # Use Claude to extract circular references
            prompt = f"""Extract ALL SEBI circular reference numbers mentioned in the following document text.

SEBI circular numbers typically follow formats like:
- SEBI/HO/[DEPT]/[TYPE]/CIR/YYYY/NNN
- HO/[DEPT]/[TYPE]/CIR/YYYY/NNN
- [DEPT]/[TYPE]/CIR/YYYY/NNN
- CIR/YYYY/NNN

Look for circular references that appear:
- After phrases like "Circular No.", "Ref. No.", "Reference No."
- In phrases like "dated [date]" following a circular number
- In "Gazette Notification No."
- References to other circulars in paragraphs
- Anywhere in the text where a circular number appears

Return ONLY a JSON array of circular numbers found, one per line.
If no circular references are found, return an empty array: []

Example format:
["SEBI/HO/DDHS/DDHS/CIR/P/2024/123", "HO/MIRSD/CRADT/CIR/P/2024/45", "CIR/2023/78"]

Text:
{self.text_content}

Circular References (JSON array):"""

            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=2048,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            response_text = response.content[0].text.strip()

            # Parse the JSON response
            # Try to extract JSON from the response
            # Sometimes the model might wrap it in markdown code blocks or add explanatory text
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            else:
                # Look for JSON array in the response (starts with [ and ends with ])
                start_idx = response_text.find('[')
                end_idx = response_text.rfind(']')
                if start_idx != -1 and end_idx != -1:
                    response_text = response_text[start_idx:end_idx+1]

            try:
                circular_refs = json.loads(response_text)
                if isinstance(circular_refs, list):
                    # Remove spaces from all references for consistency
                    normalized_refs = [ref.replace(' ', '') for ref in circular_refs]
                    references.update(normalized_refs)
                    print(f"  Claude extracted {len(circular_refs)} circular references")
                else:
                    print("  Warning: Claude response was not a list")
            except json.JSONDecodeError as je:
                print(f"  Error parsing Claude JSON response: {je}")
                print(f"  Response was: {response_text[:200]}")

        except Exception as e:
            print(f"Error extracting circular references with Claude: {e}")

        print(f"Found {len(references)} unique circular references")
        return references


def main():
    # Configuration
    # Get the project root directory (parent of scripts directory)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    pdf_file = project_root / "1765535283954.pdf"
    database_file = project_root / "sebi_circular_numbers.txt"
    output_file = project_root / "circular_references_found.txt"

    print("=" * 80)
    print("SEBI Circular Reference Extractor")
    print("=" * 80)
    print()

    # Check if files exist
    if not pdf_file.exists():
        print(f"Error: PDF file '{pdf_file}' not found!")
        return

    if not database_file.exists():
        print(f"Error: Database file '{database_file}' not found!")
        return

    # Load circular database
    db = CircularDatabase(database_file)

    if not db.circulars:
        print("Error: No circulars loaded from database!")
        return

    # Extract circular references from PDF
    extractor = PDFCircularExtractor(pdf_file)
    extractor.extract_text()

    # Debug: Save extracted text to file
    debug_file = project_root / "debug_extracted_text.txt"
    with open(debug_file, "w", encoding='utf-8') as f:
        f.write(extractor.text_content)
    print(f"Debug: Extracted text saved to {debug_file}")

    # Get the circular number of the current PDF
    current_circular = extractor.get_circular_number()
    print(f"Current circular: {current_circular}")
    print()

    # Extract references
    all_references = extractor.extract_circular_references()

    # Filter out references to the current circular itself (only exact matches)
    references = set()

    # Normalize current circular number for comparison
    # Remove all non-alphanumeric characters for accurate matching
    def normalize_circular_no(circ_no):
        if not circ_no:
            return ""
        # Keep only alphanumeric characters
        import re
        normalized = re.sub(r'[^A-Z0-9]', '', circ_no.upper())
        return normalized

    current_circ_normalized = normalize_circular_no(current_circular)

    for ref in all_references:
        # Normalize reference for comparison
        ref_normalized = normalize_circular_no(ref)

        # Skip only if it's an exact match (same circular number)
        # This allows references to other circulars from the same department
        if current_circ_normalized and current_circ_normalized == ref_normalized:
            print(f"Skipping self-reference: {ref}")
            continue  # Skip self-reference

        # Add all non-self references
        references.add(ref)

    if not references:
        print("No circular references to other circulars found in the PDF!")
        print("(Self-references to current circular have been filtered out)")
        return

    print(f"\nFound {len(references)} references to other circulars")
    print("\n" + "=" * 80)
    print("Matching references with database...")
    print("=" * 80)
    print()

    # Match references with database
    matched_circulars = []
    unmatched_references = []

    for ref in sorted(references):
        matches = db.search(ref)

        if matches:
            for match in matches:
                matched_circulars.append({
                    'reference': ref,
                    'title': match['title'],
                    'circular_no': match['circular_no']
                })
        else:
            unmatched_references.append(ref)

    # Generate output
    print(f"Matched: {len(matched_circulars)} references")
    print(f"Unmatched: {len(unmatched_references)} references")
    print()

    # Save results to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("SEBI Circular References Extraction Report\n")
        f.write("=" * 80 + "\n\n")

        f.write(f"Source PDF: {pdf_file}\n")
        f.write(f"Current Circular No: {current_circular}\n")
        f.write(f"Date: {Path(pdf_file).stat().st_mtime}\n")
        f.write("\n" + "=" * 80 + "\n\n")

        if matched_circulars:
            f.write("MATCHED CIRCULAR REFERENCES\n")
            f.write("=" * 80 + "\n\n")

            for idx, circ in enumerate(matched_circulars, 1):
                f.write(f"{idx}. Reference Found in PDF: {circ['reference']}\n")
                f.write(f"   Circular No: {circ['circular_no']}\n")
                f.write(f"   Title: {circ['title']}\n")
                f.write("\n")

                # Also print to console
                print(f"{idx}. {circ['reference']}")
                print(f"   -> {circ['circular_no']}: {circ['title'][:70]}...")
                print()

        if unmatched_references:
            f.write("\n" + "=" * 80 + "\n")
            f.write("UNMATCHED REFERENCES (Not found in current database)\n")
            f.write("=" * 80 + "\n\n")
            f.write("Note: These circulars may not be in the database yet.\n")
            f.write("The database was created by scraping a limited number of pages.\n")
            f.write("To find these circulars, scrape more pages or search SEBI website.\n\n")

            for idx, ref in enumerate(unmatched_references, 1):
                f.write(f"{idx}. {ref}\n")

            f.write("\n")

        f.write("=" * 80 + "\n")
        f.write(f"Summary:\n")
        f.write(f"Total references found: {len(references)}\n")
        f.write(f"Matched with database: {len(matched_circulars)}\n")
        f.write(f"Unmatched: {len(unmatched_references)}\n")
        f.write("=" * 80 + "\n")

    print("=" * 80)
    print(f"Results saved to: {output_file}")
    print("=" * 80)


if __name__ == "__main__":
    main()
