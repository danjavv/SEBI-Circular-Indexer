#!/usr/bin/env python3

import re
import json
from typing import List, Dict, Set, Tuple
from pathlib import Path
import PyPDF2
from collections import defaultdict


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

    def add_circular(self, filename: str, circular_no: str, references: Set[str]):
        node_id = filename
        self.nodes[node_id] = {
            'filename': filename,
            'circular_no': circular_no,
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
        graphml.append('  <key id="filename" for="node" attr.name="filename" attr.type="string"/>')
        graphml.append('  <key id="reference_count" for="node" attr.name="reference_count" attr.type="int"/>')
        graphml.append('  <key id="target_reference" for="edge" attr.name="target_reference" attr.type="string"/>')
        graphml.append('  <graph id="G" edgedefault="directed">')

        # Add nodes
        for node_id, node_data in self.nodes.items():
            graphml.append(f'    <node id="{node_id}">')
            graphml.append(f'      <data key="circular_no">{self._escape_xml(node_data["circular_no"])}</data>')
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
        patterns = [
            r'CIRCULAR\s*\n\s*([A-Z]{2}/\d+/\d+/\d+[^\n]+)',
            r'^([A-Z]{2}/\d+/\d+/\d+[^\n]+)',
            r'Circular\s+No\.?\s*:?\s*([A-Z]{2,}/[A-Z0-9/-]+/\d+)',
            r'(HO/\d+/\d+/\d+[^\n]*)',
            r'SEBI/HO/[A-Z]+(?:-[A-Z]+)?(?:/[A-Z0-9-]+)*/(?:P/)?CIR/\d{4}/\d+',
        ]

        # Check first 1000 characters for circular number
        header = self.text_content[:1000]

        for pattern in patterns:
            match = re.search(pattern, header, re.MULTILINE | re.IGNORECASE)
            if match:
                self.circular_number = match.group(1).strip() if match.groups() else match.group(0).strip()
                return self.circular_number

        # If no pattern matches, use filename
        return f"UNKNOWN_{self.filename}"

    def extract_circular_references(self) -> Set[str]:
        references = set()

        # Normalize text
        normalized_text = re.sub(r'\s+', ' ', self.text_content)

        # Pattern 1: Full circular reference with "Circular No."
        pattern1 = r'(?:SEBI\s+)?Circular\s+No\.?\s+(SEBI/HO/[A-Z0-9]+(?:/[A-Z0-9-]+)+/\d+)'
        references.update(re.findall(pattern1, normalized_text, re.IGNORECASE))

        # Pattern 2: Standard SEBI/HO/.../CIR/YYYY/NNN format
        pattern2 = r'SEBI/HO/[A-Z0-9]+(?:/[A-Z0-9-]+)*/(?:P/)?CIR/\d{4}/\d+'
        references.update(re.findall(pattern2, normalized_text, re.IGNORECASE))

        # Pattern 3: Short form with HO/
        pattern3 = r'(?:Circular\s+No\.?\s*:?\s*)?(HO/[A-Z0-9]+(?:/[A-Z0-9-]+)+/\d+)'
        references.update(re.findall(pattern3, normalized_text, re.IGNORECASE))

        # Pattern 4: Dated references
        pattern4 = r'Circular\s+No\.?\s+([A-Z]{2,}/[A-Z0-9/-]+/\d+)\s+dated'
        references.update(re.findall(pattern4, normalized_text, re.IGNORECASE))

        # Pattern 5: Gazette notifications
        pattern5 = r'Gazette\s+Notifications?\s+No\.?\s+([A-Z]{2,}/[A-Z0-9/-]+/\d+)'
        references.update(re.findall(pattern5, normalized_text, re.IGNORECASE))

        # Pattern 6: Paragraph references
        pattern6 = r'(?:paragraph|para)\s+[\d.]+\s+of\s+(?:SEBI\s+)?Circular\s+(?:No\.?\s*)?([A-Z]{2,}/[A-Z0-9/-]+/\d+)'
        references.update(re.findall(pattern6, normalized_text, re.IGNORECASE))

        # Pattern 7: General SEBI circular number
        pattern7 = r'\b(SEBI/HO/[A-Z]+(?:-[A-Z]+)?(?:/[A-Z0-9-]+)*/(?:P/)?CIR/\d{4}/\d+)\b'
        references.update(re.findall(pattern7, normalized_text, re.IGNORECASE))

        # Pattern 8: Standalone CIR/YYYY/NNN
        pattern8 = r'\b(CIR/\d{4}/\d+)\b'
        references.update(re.findall(pattern8, normalized_text))

        # Filter out self-references
        filtered_references = set()
        current_circ_short = self.circular_number.split('(')[0].split('-')[0].strip() if self.circular_number else ""

        for ref in references:
            # Skip self-references
            if current_circ_short and (current_circ_short in ref or ref in current_circ_short):
                continue
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

        references = extractor.extract_circular_references()
        print(f"  References: {len(references)}")

        if references:
            for ref in sorted(references):
                print(f"    -> {ref}")

        graph.add_circular(pdf_path.name, circular_no, references)
        return True

    except Exception as e:
        print(f"  Error: {e}")
        return False


def main():
    circulars_dir = Path("circulars")
    output_dir = Path("graph_outputs")
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
