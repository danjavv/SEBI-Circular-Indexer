#!/usr/bin/env python3

import re
import os
import json
from typing import List, Dict, Set, Tuple
from pathlib import Path
import PyPDF2
from collections import defaultdict
from dotenv import load_dotenv
from anthropic import Anthropic

# Load environment variables
load_dotenv()

# Configure Anthropic API
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY not found in .env file")
client = Anthropic(api_key=ANTHROPIC_API_KEY)


class CircularKnowledgeGraph:
    def __init__(self):
        self.nodes = {}
        self.edges = []
        self.extraction_stats = {
            'total_pdfs': 0,
            'successful_extractions': 0,
            'failed_extractions': 0,
            'total_references': 0
        }

    def add_circular(self, filename: str, circular_no: str, title: str, date: str, references: Set[str]):
        node_id = filename
        self.nodes[node_id] = {
            'filename': filename,
            'circular_no': circular_no,
            'title': title,
            'date': date,
            'references': list(references),
            'reference_count': len(references)
        }

        # Add edges for each reference
        for ref in references:
            self.edges.append({
                'source': node_id,
                'source_circular_no': circular_no,
                'target_reference': ref,
                'type': 'references'
            })

    def get_statistics(self) -> Dict:
        return {
            'total_nodes': len(self.nodes),
            'total_edges': len(self.edges),
            'avg_references_per_circular': round(len(self.edges) / len(self.nodes), 2) if self.nodes else 0,
            'extraction_stats': self.extraction_stats,
            'most_referenced_circulars': self._get_most_referenced(),
            'circulars_with_most_outgoing_refs': self._get_most_outgoing_refs()
        }

    def _get_most_referenced(self) -> List[Tuple[str, int]]:
        ref_counts = defaultdict(int)
        for edge in self.edges:
            ref_counts[edge['target_reference']] += 1

        # Return top 10
        sorted_refs = sorted(ref_counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_refs[:10]

    def _get_most_outgoing_refs(self) -> List[Tuple[str, int]]:
        sorted_nodes = sorted(
            self.nodes.items(),
            key=lambda x: x[1]['reference_count'],
            reverse=True
        )
        return [(node[1]['circular_no'], node[1]['reference_count']) for node in sorted_nodes[:10]]

    def export_to_json(self, output_file: str):
        graph_data = {
            'nodes': [
                {
                    'id': node_id,
                    **node_data
                }
                for node_id, node_data in self.nodes.items()
            ],
            'edges': self.edges,
            'statistics': self.get_statistics()
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(graph_data, f, indent=2, ensure_ascii=False)

        print(f"Graph exported to JSON: {output_file}")

    def export_to_graphml(self, output_file: str):
        graphml = ['<?xml version="1.0" encoding="UTF-8"?>']
        graphml.append('<graphml xmlns="http://graphml.graphdrawing.org/xmlns">')
        graphml.append('  <key id="circular_no" for="node" attr.name="circular_no" attr.type="string"/>')
        graphml.append('  <key id="title" for="node" attr.name="title" attr.type="string"/>')
        graphml.append('  <key id="date" for="node" attr.name="date" attr.type="string"/>')
        graphml.append('  <key id="filename" for="node" attr.name="filename" attr.type="string"/>')
        graphml.append('  <key id="reference_count" for="node" attr.name="reference_count" attr.type="int"/>')
        graphml.append('  <key id="target_reference" for="edge" attr.name="target_reference" attr.type="string"/>')
        graphml.append('  <graph id="G" edgedefault="directed">')

        # Add nodes
        for node_id, node_data in self.nodes.items():
            graphml.append(f'    <node id="{node_id}">')
            graphml.append(f'      <data key="circular_no">{self._escape_xml(node_data["circular_no"])}</data>')
            graphml.append(f'      <data key="title">{self._escape_xml(node_data.get("title", ""))}</data>')
            graphml.append(f'      <data key="date">{self._escape_xml(node_data.get("date", ""))}</data>')
            graphml.append(f'      <data key="filename">{self._escape_xml(node_data["filename"])}</data>')
            graphml.append(f'      <data key="reference_count">{node_data["reference_count"]}</data>')
            graphml.append('    </node>')

        # Add edges
        for i, edge in enumerate(self.edges):
            graphml.append(f'    <edge id="e{i}" source="{edge["source"]}" target="{edge["target_reference"]}">')
            graphml.append(f'      <data key="target_reference">{self._escape_xml(edge["target_reference"])}</data>')
            graphml.append('    </edge>')

        graphml.append('  </graph>')
        graphml.append('</graphml>')

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(graphml))

        print(f"Graph exported to GraphML: {output_file}")

    def _escape_xml(self, text: str) -> str:
        """Escape XML special characters"""
        return (str(text)
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&apos;'))

    def export_to_cytoscape(self, output_file: str):
        cytoscape_data = {
            'elements': {
                'nodes': [
                    {
                        'data': {
                            'id': node_id,
                            'label': node_data['circular_no'],
                            'title': node_data.get('title', ''),
                            'date': node_data.get('date', ''),
                            'filename': node_data['filename'],
                            'reference_count': node_data['reference_count']
                        }
                    }
                    for node_id, node_data in self.nodes.items()
                ],
                'edges': [
                    {
                        'data': {
                            'id': f"e{i}",
                            'source': edge['source'],
                            'target': edge['target_reference'],
                            'label': 'references'
                        }
                    }
                    for i, edge in enumerate(self.edges)
                ]
            }
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(cytoscape_data, f, indent=2, ensure_ascii=False)

        print(f"Graph exported to Cytoscape format: {output_file}")


class PDFCircularExtractor:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.filename = Path(pdf_path).name
        self.text_content = ""
        self.circular_number = ""
        self.circular_title = ""
        self.circular_date = ""

    def extract_text(self) -> str:
        try:
            with open(self.pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text_parts = []

                for page in pdf_reader.pages:
                    text = page.extract_text()
                    text_parts.append(text)

                self.text_content = '\n'.join(text_parts)
                return self.text_content

        except Exception as e:
            print(f"  Error extracting text: {e}")
            return ""

    def get_circular_number(self) -> str:
        # Check first 1000 characters for circular number
        header = self.text_content[:1000]

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
            if not self.circular_number or len(self.circular_number) > 150 or self.circular_number == "Unknown":
                return f"UNKNOWN_{self.filename}"

            return self.circular_number

        except Exception as e:
            print(f"  Error extracting circular number with Claude: {e}")
            return f"UNKNOWN_{self.filename}"

    def get_circular_title(self) -> str:
        # Check first 2000 characters for title
        header = self.text_content[:2000]

        try:
            # Use Claude to extract circular title
            prompt = f"""Extract the subject/title of this SEBI circular from the text below.

The title usually appears after "Subject:" or "Sub:" in the document header.
Return ONLY the title itself, without "Subject:" or "Sub:" prefix.

If you cannot find a clear title, return exactly "Unknown".

Text:
{header}

Title:"""

            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=200,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            raw_response = response.content[0].text.strip()

            # Clean up the response - extract actual title
            import re

            # Look for quoted text which is likely the title
            quoted_match = re.search(r'["\']([^"\']+)["\']', raw_response)
            if quoted_match:
                cleaned = quoted_match.group(1).strip()
            else:
                # Remove everything up to "is:" or just ":"
                cleaned = re.sub(r'^.*?(?:is|are)\s*:?\s*', '', raw_response, flags=re.IGNORECASE)
                # Take only first line
                cleaned = cleaned.split('\n')[0].strip().strip('"\'')

            self.circular_title = cleaned if cleaned and cleaned != "Unknown" else ""
            return self.circular_title

        except Exception as e:
            print(f"  Error extracting title with Claude: {e}")
            return ""

    def get_circular_date(self) -> str:
        # Check first 1500 characters for date
        header = self.text_content[:1500]

        try:
            # Use Claude to extract circular date
            prompt = f"""Extract the issue date of this SEBI circular from the text below.

The date usually appears near the top of the document, after the circular number.
Common formats: "January 15, 2025", "15/01/2025", "Jan 15, 2025", etc.

Return the date in format: "Month DD, YYYY" (e.g., "January 15, 2025")
If you cannot find a clear date, return exactly "Unknown".

Text:
{header}

Date:"""

            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=100,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            raw_response = response.content[0].text.strip()

            # Clean up the response - extract actual date using pattern matching
            import re

            # Look for date patterns: "Month DD, YYYY" or "DD Month YYYY" or "DD/MM/YYYY"
            date_patterns = [
                r'((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})',
                r'(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})',
                r'(\d{1,2}/\d{1,2}/\d{4})',
                r'(\d{4}-\d{1,2}-\d{1,2})',
            ]

            cleaned = ""
            for pattern in date_patterns:
                match = re.search(pattern, raw_response, re.IGNORECASE)
                if match:
                    cleaned = match.group(1).strip()
                    break

            # If no pattern matched, try to remove explanatory text
            if not cleaned:
                cleaned = re.sub(r'^.*?(?:is|are)\s*:?\s*', '', raw_response, flags=re.IGNORECASE)
                cleaned = cleaned.split('\n')[0].strip().rstrip('.')

            self.circular_date = cleaned if cleaned and cleaned != "Unknown" else ""
            return self.circular_date

        except Exception as e:
            print(f"  Error extracting date with Claude: {e}")
            return ""

    def extract_circular_references(self) -> Set[str]:
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
                else:
                    print("  Warning: Claude response was not a list")
            except json.JSONDecodeError as je:
                print(f"  Warning: Error parsing Claude JSON response: {je}")

        except Exception as e:
            print(f"  Error extracting circular references with Claude: {e}")

        # Filter out self-references (only exact matches)
        filtered_references = set()

        # Normalize current circular number for comparison
        # Remove spaces, hyphens, underscores, slashes, and convert to uppercase
        def normalize_circular_no(circ_no):
            if not circ_no:
                return ""
            # Keep only alphanumeric characters
            import re
            normalized = re.sub(r'[^A-Z0-9]', '', circ_no.upper())
            return normalized

        current_circ_normalized = normalize_circular_no(self.circular_number)

        for ref in references:
            # Normalize reference for comparison
            ref_normalized = normalize_circular_no(ref)

            # Skip only if it's an exact match (same circular number)
            # This allows references to other circulars from the same department
            if current_circ_normalized and current_circ_normalized == ref_normalized:
                continue  # Skip self-reference

            # Add all non-self references
            filtered_references.add(ref)

        return filtered_references


def process_circular(pdf_path: Path, graph: CircularKnowledgeGraph) -> bool:
    print(f"Processing: {pdf_path.name}")

    try:
        extractor = PDFCircularExtractor(str(pdf_path))

        text = extractor.extract_text()
        if not text:
            print("  No text extracted")
            return False

        circular_no = extractor.get_circular_number()
        print(f"  Circular: {circular_no}")

        title = extractor.get_circular_title()
        print(f"  Title: {title[:80] if title else 'N/A'}{'...' if title and len(title) > 80 else ''}")

        date = extractor.get_circular_date()
        print(f"  Date: {date if date else 'N/A'}")

        references = extractor.extract_circular_references()
        print(f"  References: {len(references)}")

        if references:
            for ref in sorted(references):
                print(f"    -> {ref}")

        graph.add_circular(pdf_path.name, circular_no, title, date, references)
        return True

    except Exception as e:
        print(f"  Error: {e}")
        return False


def main():
    # Get the project root directory (parent of scripts directory)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    circulars_dir = project_root / "circulars"
    output_dir = project_root / "graph_outputs"
    output_dir.mkdir(exist_ok=True)

    if not circulars_dir.exists():
        print(f"Error: Directory '{circulars_dir}' not found")
        return

    pdf_files = list(circulars_dir.glob("*.pdf")) + list(circulars_dir.glob("*.PDF"))

    if not pdf_files:
        print(f"Error: No PDF files found in '{circulars_dir}'")
        return

    print(f"Found {len(pdf_files)} PDFs in '{circulars_dir}'\n")

    graph = CircularKnowledgeGraph()
    graph.extraction_stats['total_pdfs'] = len(pdf_files)

    for pdf_path in sorted(pdf_files):
        success = process_circular(pdf_path, graph)
        if success:
            graph.extraction_stats['successful_extractions'] += 1
        else:
            graph.extraction_stats['failed_extractions'] += 1

    stats = graph.get_statistics()

    print("\n--- Statistics ---")
    print(f"Circulars processed: {stats['total_nodes']}")
    print(f"Reference relationships: {stats['total_edges']}")
    print(f"Avg references per circular: {stats['avg_references_per_circular']}")
    print(f"Successful: {stats['extraction_stats']['successful_extractions']}, Failed: {stats['extraction_stats']['failed_extractions']}")

    if stats['most_referenced_circulars']:
        print("\nMost referenced:")
        for i, (ref, count) in enumerate(stats['most_referenced_circulars'][:5], 1):
            print(f"  {i}. {ref} ({count}x)")

    if stats['circulars_with_most_outgoing_refs']:
        print("\nMost outgoing references:")
        for i, (circ, count) in enumerate(stats['circulars_with_most_outgoing_refs'][:5], 1):
            print(f"  {i}. {circ} ({count}x)")

    print("\nExporting...")
    graph.export_to_json(output_dir / "circular_knowledge_graph.json")
    graph.export_to_graphml(output_dir / "circular_knowledge_graph.graphml")
    graph.export_to_cytoscape(output_dir / "circular_knowledge_graph_cytoscape.json")

    print(f"\nOutputs saved to '{output_dir}/'")
    print("  - circular_knowledge_graph.json")
    print("  - circular_knowledge_graph.graphml")
    print("  - circular_knowledge_graph_cytoscape.json")


if __name__ == "__main__":
    main()
