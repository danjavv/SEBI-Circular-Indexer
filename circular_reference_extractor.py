#!/usr/bin/env python3
"""
SEBI Circular Reference Extractor
Reads a SEBI circular PDF and extracts references to other circulars,
then matches them against a database of known circulars
"""

import re
from typing import List, Dict, Tuple, Set
import PyPDF2
from pathlib import Path


class CircularDatabase:
    """Manages the database of circulars from the text file"""

    def __init__(self, database_file: str):
        self.circulars: List[Dict[str, str]] = []
        self.load_database(database_file)

    def load_database(self, database_file: str):
        """Load circular data from the generated text file"""
        print(f"Loading circular database from {database_file}...")

        try:
            with open(database_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Parse the file to extract circular entries
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
        """Search for circulars matching a reference pattern"""
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
    """Extracts circular references from a PDF document"""

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.text_content = ""
        self.circular_number = ""

    def extract_text(self) -> str:
        """Extract text content from PDF"""
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
        """Extract the circular number of the current PDF"""
        # Pattern to match circular number at the top of the document
        # Look for pattern right after "CIRCULAR" heading
        patterns = [
            r'CIRCULAR\s*\n\s*([A-Z]{2}/\d+/\d+/\d+[^\n]+)',  # After CIRCULAR heading
            r'^([A-Z]{2}/\d+/\d+/\d+[^\n]+)',  # At start of line
            r'Circular\s+No\.?\s*:?\s*([A-Z]{2,}/[A-Z0-9/-]+/\d+)',
            r'(HO/\d+/\d+/\d+[^\n]*)',  # HO format
        ]

        # Check first 500 characters for circular number
        header = self.text_content[:500]

        for pattern in patterns:
            match = re.search(pattern, header, re.MULTILINE | re.IGNORECASE)
            if match:
                self.circular_number = match.group(1).strip()
                return self.circular_number

        return "Unknown"

    def extract_circular_references(self) -> Set[str]:
        """Extract all references to other SEBI circulars"""
        print("Extracting circular references...")

        references = set()

        # Normalize text - remove excessive whitespace while preserving structure
        normalized_text = re.sub(r'\s+', ' ', self.text_content)

        # Pattern 1: Full circular reference with SEBI/HO/... (most specific)
        pattern1 = r'(?:SEBI\s+)?Circular\s+No\.?\s+(SEBI/HO/[A-Z0-9]+(?:/[A-Z0-9-]+)+/\d+)'
        matches1 = re.findall(pattern1, normalized_text, re.IGNORECASE)
        if matches1:
            print(f"  Pattern 1 matched: {matches1}")
        references.update(matches1)

        # Pattern 2: Circular number format SEBI/HO/.../CIR/YYYY/NNN
        pattern2 = r'SEBI/HO/[A-Z0-9]+(?:/[A-Z0-9-]+)*/(?:P/)?CIR/\d{4}/\d+'
        matches2 = re.findall(pattern2, normalized_text, re.IGNORECASE)
        if matches2:
            print(f"  Pattern 2 matched: {matches2}")
        references.update(matches2)

        # Pattern 3: Short form without SEBI prefix but with HO/
        pattern3 = r'(?:Circular\s+No\.?\s*:?\s*)?(HO/[A-Z0-9]+(?:/[A-Z0-9-]+)+/\d+)'
        matches3 = re.findall(pattern3, normalized_text, re.IGNORECASE)
        if matches3:
            print(f"  Pattern 3 matched: {matches3}")
        references.update(matches3)

        # Pattern 4: Dated references like "dated November 22, 2024"
        pattern4 = r'Circular\s+No\.?\s+([A-Z]{2,}/[A-Z0-9/-]+/\d+)\s+dated'
        matches4 = re.findall(pattern4, normalized_text, re.IGNORECASE)
        if matches4:
            print(f"  Pattern 4 matched: {matches4}")
        references.update(matches4)

        # Pattern 5: Gazette notification references
        pattern5 = r'Gazette\s+Notifications?\s+No\.?\s+([A-Z]{2,}/[A-Z0-9/-]+/\d+)'
        matches5 = re.findall(pattern5, normalized_text, re.IGNORECASE)
        if matches5:
            print(f"  Pattern 5 matched: {matches5}")
        references.update(matches5)

        # Pattern 6: Paragraph references to other circulars
        pattern6 = r'(?:paragraph|para)\s+[\d.]+\s+of\s+(?:SEBI\s+)?Circular\s+(?:No\.?\s*)?([A-Z]{2,}/[A-Z0-9/-]+/\d+)'
        matches6 = re.findall(pattern6, normalized_text, re.IGNORECASE)
        if matches6:
            print(f"  Pattern 6 matched: {matches6}")
        references.update(matches6)

        # Pattern 7: General SEBI circular number anywhere in text
        pattern7 = r'\b(SEBI/HO/[A-Z]+(?:-[A-Z]+)?(?:/[A-Z0-9-]+)*/(?:P/)?CIR/\d{4}/\d+)\b'
        matches7 = re.findall(pattern7, normalized_text, re.IGNORECASE)
        if matches7:
            print(f"  Pattern 7 matched: {matches7}")
        references.update(matches7)

        # Pattern 8: Standalone circular numbers with various formats
        pattern8 = r'\b(CIR/\d{4}/\d+)\b'
        matches8 = re.findall(pattern8, normalized_text)
        if matches8:
            print(f"  Pattern 8 matched: {matches8}")
        references.update(matches8)

        print(f"Found {len(references)} unique circular references")
        return references


def main():
    """Main function to extract and match circular references"""

    # Configuration
    pdf_file = "1765535283954.pdf"
    database_file = "sebi_circular_numbers.txt"
    output_file = "circular_references_found.txt"

    print("=" * 80)
    print("SEBI Circular Reference Extractor")
    print("=" * 80)
    print()

    # Check if files exist
    if not Path(pdf_file).exists():
        print(f"Error: PDF file '{pdf_file}' not found!")
        return

    if not Path(database_file).exists():
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
    with open("debug_extracted_text.txt", "w", encoding='utf-8') as f:
        f.write(extractor.text_content)
    print("Debug: Extracted text saved to debug_extracted_text.txt")

    # Get the circular number of the current PDF
    current_circular = extractor.get_circular_number()
    print(f"Current circular: {current_circular}")
    print()

    # Extract references
    all_references = extractor.extract_circular_references()

    # Filter out references to the current circular itself
    references = set()
    current_circ_short = current_circular.split('(')[0] if '(' in current_circular else current_circular
    current_circ_short = current_circ_short.split('-')[0].strip() if '-' in current_circ_short else current_circ_short

    for ref in all_references:
        # Skip if this reference matches the current circular
        if current_circ_short in ref or ref in current_circ_short:
            print(f"Skipping self-reference: {ref}")
            continue
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
