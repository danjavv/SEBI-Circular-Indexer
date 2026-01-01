#!/usr/bin/env python3

import json
import os
import re
from typing import List, Dict, Set, Tuple
from pathlib import Path
import PyPDF2
from collections import defaultdict, deque
from dotenv import load_dotenv
from anthropic import Anthropic

# Load environment variables
load_dotenv()

# Configure Anthropic API
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY not found in .env file")
client = Anthropic(api_key=ANTHROPIC_API_KEY)


class PDFCircularExtractor:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.filename = Path(pdf_path).name
        self.text_content = ""
        self.circular_number = ""

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
            cleaned = raw_response

            # Remove common prefixes
            patterns = [
                r'^.*?circular\s+number\s+(?:is\s+|extracted.*?is\s*)?:?\s*',
                r'^.*?circular\s+number\s*:?\s*',
                r'^Here\s+is\s+.*?:?\s*',
            ]

            for pattern in patterns:
                cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
                if cleaned != raw_response:
                    break

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
        # Remove all non-alphanumeric characters for accurate matching
        def normalize_circular_no(circ_no):
            if not circ_no:
                return ""
            # Keep only alphanumeric characters
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


class KnowledgeGraphAnalyzer:
    def __init__(self, graph_file: str):
        self.graph_file = graph_file
        self.nodes = {}
        self.edges = []
        self.reference_map = defaultdict(list)  # Maps reference -> list of source nodes
        self.load_graph()

    def load_graph(self):
        try:
            with open(self.graph_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.nodes = {node['id']: node for node in data['nodes']}
            self.edges = data['edges']

            # Build reference map for quick lookup (target ref -> sources that reference it)
            for edge in self.edges:
                target = edge['target_reference']
                source = edge['source']
                self.reference_map[target].append(source)

            # Build circular_no to node_id mapping
            self.circular_to_node = {}
            for node_id, node in self.nodes.items():
                circ_no = node.get('circular_no', '')
                if circ_no:
                    self.circular_to_node[circ_no] = node_id

        except FileNotFoundError:
            print(f"Error: Graph file '{self.graph_file}' not found!")
            print("Please run 'python3 circular_knowledge_graph.py' first.")
            raise

    def find_direct_references(self, circular_references: Set[str]) -> Dict[str, Dict]:
        direct_refs = {}

        for ref in circular_references:
            # Try exact match by node ID first
            if ref in self.nodes:
                direct_refs[ref] = {
                    'type': 'in_graph',
                    'node_id': ref,
                    'node': self.nodes[ref],
                    'references': self.nodes[ref].get('references', [])
                }
            # Try matching by circular_no
            elif ref in self.circular_to_node:
                node_id = self.circular_to_node[ref]
                direct_refs[ref] = {
                    'type': 'in_graph',
                    'node_id': node_id,
                    'node': self.nodes[node_id],
                    'references': self.nodes[node_id].get('references', [])
                }
            # Check if it exists as a target reference (referenced but not in our dataset)
            elif ref in self.reference_map:
                direct_refs[ref] = {
                    'type': 'referenced_external',
                    'message': f'Referenced by {len(self.reference_map[ref])} circular(s) in graph',
                    'referenced_by': self.reference_map[ref],
                    'references': []  # Don't have the actual PDF, so no references
                }
            else:
                # Try fuzzy match (partial matching)
                matches = self._fuzzy_match_reference(ref)
                if matches:
                    direct_refs[ref] = {
                        'type': 'fuzzy_match',
                        'matches': matches,
                        'references': []
                    }
                else:
                    direct_refs[ref] = {
                        'type': 'external',
                        'message': 'Not in knowledge graph',
                        'references': []
                    }

        return direct_refs

    def _get_node_references(self, node_id: str) -> List[str]:
        refs = []
        for edge in self.edges:
            if edge['source'] == node_id:
                refs.append(edge['target_reference'])
        return refs

    def _fuzzy_match_reference(self, ref: str) -> List[str]:
        # Normalize by keeping only alphanumeric characters (same as self-reference filtering)
        def normalize(circ_no):
            if not circ_no:
                return ""
            return re.sub(r'[^A-Z0-9]', '', circ_no.upper())

        ref_normalized = normalize(ref)
        matches = []

        for node_id, node in self.nodes.items():
            circ_no = node.get('circular_no', '')
            circ_no_normalized = normalize(circ_no)
            if ref_normalized in circ_no_normalized or circ_no_normalized in ref_normalized:
                matches.append(node_id)

        return matches

    def find_indirect_references(self, direct_refs: Dict[str, Dict], max_depth: int = 5) -> Dict[int, Set[str]]:
        indirect_by_level = defaultdict(set)
        visited = set()
        queue = deque()

        # Initialize queue with direct references that have references
        for ref, details in direct_refs.items():
            visited.add(ref)
            if details.get('references'):
                # Add all the references this circular makes
                for next_ref in details['references']:
                    if next_ref not in visited:
                        indirect_by_level[2].add(next_ref)
                        visited.add(next_ref)
                        queue.append((next_ref, 2))

        # BFS traversal
        while queue:
            current_ref, level = queue.popleft()

            if level >= max_depth:
                continue

            # Find if this reference has more references
            # Check if it's in our nodes
            node_id = None
            if current_ref in self.nodes:
                node_id = current_ref
            elif current_ref in self.circular_to_node:
                node_id = self.circular_to_node[current_ref]

            if node_id:
                refs = self.nodes[node_id].get('references', [])
                for ref in refs:
                    if ref not in visited:
                        indirect_by_level[level + 1].add(ref)
                        visited.add(ref)
                        queue.append((ref, level + 1))

        return dict(indirect_by_level)

    def get_reference_details(self, ref: str) -> Dict:
        if ref in self.nodes:
            return self.nodes[ref]
        return {'circular_no': ref, 'filename': 'Not in graph', 'reference_count': 0}


def print_tree_structure(ref: str, level: int = 0, prefix: str = "", is_last: bool = True):
    connector = "└── " if is_last else "├── "
    print(f"{prefix}{connector}{ref}")
    return prefix + ("    " if is_last else "│   ")


def main():
    import sys
    if len(sys.argv) > 1:
        pdf_file = sys.argv[1]
    else:
        pdf_file = input("Enter PDF file path (or press Enter for default): ").strip()
        if not pdf_file:
            pdf_file = "1765535283954.pdf"

    graph_file = "graph_outputs/circular_knowledge_graph.json"
    output_file = "circular_reference_analysis.txt"

    if not Path(pdf_file).exists():
        print(f"Error: PDF file '{pdf_file}' not found")
        return

    if not Path(graph_file).exists():
        print(f"Error: Knowledge graph '{graph_file}' not found")
        print("Run 'python3 circular_knowledge_graph.py' first")
        return

    print(f"Analyzing: {pdf_file}")

    extractor = PDFCircularExtractor(pdf_file)
    extractor.extract_text()

    circular_no = extractor.get_circular_number()
    print(f"Circular: {circular_no}")

    references = extractor.extract_circular_references()
    print(f"Found {len(references)} direct reference(s)\n")

    if not references:
        print("No references found")
        return

    analyzer = KnowledgeGraphAnalyzer(graph_file)
    print(f"Loaded graph: {len(analyzer.nodes)} nodes, {len(analyzer.edges)} edges\n")

    print("--- Direct References (Level 1) ---")

    direct_refs = analyzer.find_direct_references(references)

    for i, (ref, details) in enumerate(sorted(direct_refs.items()), 1):
        if details['type'] == 'in_graph':
            node = details['node']
            print(f"{i}. {ref}")
            print(f"   In graph: {node['filename']}")
            print(f"   References: {len(details['references'])} circulars")
        elif details['type'] == 'referenced_external':
            print(f"{i}. {ref}")
            print(f"   {details['message']}")
            for source in details['referenced_by'][:3]:
                source_node = analyzer.nodes.get(source, {})
                print(f"     -> {source_node.get('circular_no', source)}")
            if len(details['referenced_by']) > 3:
                print(f"     ... +{len(details['referenced_by']) - 3} more")
        elif details['type'] == 'fuzzy_match':
            print(f"{i}. {ref}")
            print(f"   Fuzzy match: {len(details['matches'])} node(s)")
            for match in details['matches']:
                print(f"     -> {analyzer.nodes[match]['circular_no']}")
        else:
            print(f"{i}. {ref}")
            print(f"   External (not in graph)")
        print()

    print("\n--- Indirect References (Level 2+) ---")

    indirect_refs = analyzer.find_indirect_references(direct_refs, max_depth=5)

    if indirect_refs:
        total_indirect = sum(len(refs) for refs in indirect_refs.values())
        print(f"Found {total_indirect} across {len(indirect_refs)} level(s)\n")

        for level in sorted(indirect_refs.keys()):
            refs = indirect_refs[level]
            print(f"Level {level}: {len(refs)}")
            for ref in sorted(refs):
                details = analyzer.get_reference_details(ref)
                print(f"  -> {ref}")
                if ref in analyzer.nodes:
                    print(f"     {details['filename']}")
            print()
    else:
        print("None found\n")

    print("\n--- Reference Tree ---")
    print(f"{circular_no}")
    print("|")

    for i, ref in enumerate(sorted(references)):
        is_last = (i == len(references) - 1)
        prefix = print_tree_structure(ref, 0, "", is_last)

        # Show level 2 references
        if ref in direct_refs and direct_refs[ref].get('references'):
            level2_refs = direct_refs[ref]['references']
            for j, level2_ref in enumerate(sorted(level2_refs)):
                is_last_l2 = (j == len(level2_refs) - 1)
                new_prefix = print_tree_structure(level2_ref, 1, prefix, is_last_l2)

                # Show level 3 references if they exist
                if level2_ref in indirect_refs.get(2, set()):
                    # Find the node for this level 2 ref
                    node_id = None
                    if level2_ref in analyzer.nodes:
                        node_id = level2_ref
                    elif level2_ref in analyzer.circular_to_node:
                        node_id = analyzer.circular_to_node[level2_ref]

                    if node_id:
                        level3_refs = analyzer.nodes[node_id].get('references', [])[:3]  # Show max 3
                        for k, level3_ref in enumerate(level3_refs):
                            is_last_l3 = (k == len(level3_refs) - 1)
                            print_tree_structure(level3_ref, 2, new_prefix, is_last_l3)

    print("\n--- Summary ---")
    print(f"Circular: {circular_no}")
    print(f"Direct: {len(references)}")
    indirect_total = sum(len(refs) for refs in indirect_refs.values()) if indirect_refs else 0
    print(f"Indirect: {indirect_total}")
    print(f"Total: {len(references) + indirect_total}")
    print(f"Max depth: {max(indirect_refs.keys()) if indirect_refs else 1}")
    in_graph = sum(1 for d in direct_refs.values() if d['type'] in ['in_graph', 'fuzzy_match'])
    print(f"In graph: {in_graph}/{len(references)}")

    # Save to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("SEBI Circular Reference Analysis Report\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Analyzed Circular: {circular_no}\n")
        f.write(f"Source File: {pdf_file}\n\n")

        f.write("DIRECT REFERENCES\n")
        f.write("-" * 80 + "\n")
        for ref, details in sorted(direct_refs.items()):
            f.write(f"• {ref}\n")
            if details['type'] == 'in_graph':
                f.write(f"  Status: In knowledge graph\n")
                f.write(f"  Makes {len(details['references'])} reference(s)\n")
            elif details['type'] == 'fuzzy_match':
                f.write(f"  Status: Fuzzy matched\n")
            else:
                f.write(f"  Status: External reference\n")
            f.write("\n")

        if indirect_refs:
            f.write("\nINDIRECT REFERENCES\n")
            f.write("-" * 80 + "\n")
            for level in sorted(indirect_refs.keys()):
                f.write(f"\nLevel {level}:\n")
                for ref in sorted(indirect_refs[level]):
                    f.write(f"  • {ref}\n")

        f.write("\n" + "=" * 80 + "\n")
        f.write("SUMMARY\n")
        f.write("=" * 80 + "\n")
        f.write(f"Direct References: {len(references)}\n")
        f.write(f"Indirect References: {sum(len(refs) for refs in indirect_refs.values()) if indirect_refs else 0}\n")
        f.write(f"Total References: {len(references) + sum(len(refs) for refs in indirect_refs.values()) if indirect_refs else len(references)}\n")
        f.write(f"Maximum Depth: {max(indirect_refs.keys()) if indirect_refs else 1}\n")

    print(f"\nReport saved: {output_file}")


if __name__ == "__main__":
    main()
