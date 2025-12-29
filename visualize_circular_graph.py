#!/usr/bin/env python3
"""
SEBI Circular Knowledge Graph Visualizer
Reads the knowledge graph JSON and creates visual representations
"""

import json
from pathlib import Path
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import matplotlib.patches as mpatches


def load_graph_from_json(json_file: str) -> nx.DiGraph:
    """Load knowledge graph from JSON file into NetworkX graph"""
    print(f"Loading graph from {json_file}...")

    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Create directed graph
    G = nx.DiGraph()

    # Add nodes
    for node in data['nodes']:
        G.add_node(
            node['id'],
            circular_no=node['circular_no'],
            filename=node['filename'],
            reference_count=node['reference_count']
        )

    # Add edges
    for edge in data['edges']:
        # Create target node if it doesn't exist (referenced but not in our dataset)
        if edge['target_reference'] not in G:
            G.add_node(
                edge['target_reference'],
                circular_no=edge['target_reference'],
                filename='external',
                reference_count=0,
                is_external=True
            )

        G.add_edge(
            edge['source'],
            edge['target_reference'],
            type=edge['type']
        )

    print(f"Loaded graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    return G


def visualize_full_graph(G: nx.DiGraph, output_file: str):
    """Create a visualization of the full knowledge graph"""
    print("Creating full graph visualization...")

    # Set up the plot
    plt.figure(figsize=(20, 16))
    plt.title("SEBI Circular Reference Network", fontsize=20, fontweight='bold', pad=20)

    # Calculate node positions using force-directed layout
    print("  Calculating layout (this may take a moment)...")
    pos = nx.spring_layout(G, k=2, iterations=50, seed=42)

    # Separate internal and external nodes
    internal_nodes = [n for n in G.nodes() if not G.nodes[n].get('is_external', False)]
    external_nodes = [n for n in G.nodes() if G.nodes[n].get('is_external', False)]

    # Calculate node sizes based on degree (both in and out)
    node_sizes_internal = [300 + (G.degree(n) * 100) for n in internal_nodes]
    node_sizes_external = [200 for _ in external_nodes]

    # Draw external nodes (referenced but not in our dataset)
    if external_nodes:
        nx.draw_networkx_nodes(
            G, pos,
            nodelist=external_nodes,
            node_color='lightgray',
            node_size=node_sizes_external,
            alpha=0.3,
            label='External References'
        )

    # Draw internal nodes (from our dataset)
    if internal_nodes:
        # Color based on out-degree (how many others they reference)
        out_degrees = [G.out_degree(n) for n in internal_nodes]
        nx.draw_networkx_nodes(
            G, pos,
            nodelist=internal_nodes,
            node_color=out_degrees,
            node_size=node_sizes_internal,
            cmap='YlOrRd',
            alpha=0.8,
            label='Circulars in Dataset'
        )

    # Draw edges
    nx.draw_networkx_edges(
        G, pos,
        edge_color='gray',
        arrows=True,
        arrowsize=10,
        arrowstyle='->',
        alpha=0.4,
        width=1,
        connectionstyle='arc3,rad=0.1'
    )

    # Add labels for high-degree nodes only (to avoid clutter)
    high_degree_nodes = [n for n in G.nodes() if G.degree(n) >= 2]
    labels = {n: G.nodes[n].get('circular_no', n)[:20] for n in high_degree_nodes}
    nx.draw_networkx_labels(
        G, pos,
        labels=labels,
        font_size=6,
        font_weight='bold'
    )

    # Add colorbar
    sm = plt.cm.ScalarMappable(cmap='YlOrRd', norm=plt.Normalize(vmin=min(out_degrees) if out_degrees else 0, vmax=max(out_degrees) if out_degrees else 1))
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=plt.gca(), label='Number of Outgoing References')

    # Add legend
    internal_patch = mpatches.Patch(color='red', label='Circulars in Dataset', alpha=0.8)
    external_patch = mpatches.Patch(color='lightgray', label='External References', alpha=0.3)
    plt.legend(handles=[internal_patch, external_patch], loc='upper left', fontsize=10)

    plt.axis('off')
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"  ✅ Saved: {output_file}")
    plt.close()


def visualize_top_circulars(G: nx.DiGraph, output_file: str, top_n: int = 15):
    """Create a focused visualization of the most connected circulars"""
    print(f"Creating top {top_n} circulars visualization...")

    # Get nodes with highest degree
    degrees = dict(G.degree())
    top_nodes = sorted(degrees.items(), key=lambda x: x[1], reverse=True)[:top_n]
    top_node_ids = [node for node, _ in top_nodes]

    # Create subgraph with top nodes and their direct neighbors
    subgraph_nodes = set(top_node_ids)
    for node in top_node_ids:
        subgraph_nodes.update(G.predecessors(node))
        subgraph_nodes.update(G.successors(node))

    G_sub = G.subgraph(subgraph_nodes)

    # Set up the plot
    plt.figure(figsize=(18, 14))
    plt.title(f"Top {top_n} Most Connected SEBI Circulars", fontsize=18, fontweight='bold', pad=20)

    # Calculate positions
    pos = nx.spring_layout(G_sub, k=3, iterations=50, seed=42)

    # Separate top nodes from others
    other_nodes = [n for n in G_sub.nodes() if n not in top_node_ids]

    # Draw other nodes
    if other_nodes:
        node_sizes_other = [100 + (G_sub.degree(n) * 50) for n in other_nodes]
        nx.draw_networkx_nodes(
            G_sub, pos,
            nodelist=other_nodes,
            node_color='lightblue',
            node_size=node_sizes_other,
            alpha=0.5
        )

    # Draw top nodes
    node_sizes_top = [500 + (G_sub.degree(n) * 100) for n in top_node_ids]
    nx.draw_networkx_nodes(
        G_sub, pos,
        nodelist=top_node_ids,
        node_color='red',
        node_size=node_sizes_top,
        alpha=0.8
    )

    # Draw edges
    nx.draw_networkx_edges(
        G_sub, pos,
        edge_color='gray',
        arrows=True,
        arrowsize=15,
        arrowstyle='->',
        alpha=0.5,
        width=2,
        connectionstyle='arc3,rad=0.1'
    )

    # Add labels
    labels = {n: G_sub.nodes[n].get('circular_no', n)[:30] for n in G_sub.nodes()}
    nx.draw_networkx_labels(
        G_sub, pos,
        labels=labels,
        font_size=7,
        font_weight='bold'
    )

    # Add legend
    top_patch = mpatches.Patch(color='red', label=f'Top {top_n} Connected', alpha=0.8)
    other_patch = mpatches.Patch(color='lightblue', label='Related Circulars', alpha=0.5)
    plt.legend(handles=[top_patch, other_patch], loc='upper left', fontsize=12)

    plt.axis('off')
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"  ✅ Saved: {output_file}")
    plt.close()


def create_statistics_report(G: nx.DiGraph, output_file: str):
    """Create a detailed statistics report with visualizations"""
    print("Creating statistics report...")

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('SEBI Circular Knowledge Graph - Network Analysis', fontsize=16, fontweight='bold')

    # 1. Degree distribution
    ax1 = axes[0, 0]
    degrees = [G.degree(n) for n in G.nodes()]
    ax1.hist(degrees, bins=20, color='steelblue', alpha=0.7, edgecolor='black')
    ax1.set_xlabel('Node Degree (Total Connections)', fontsize=11)
    ax1.set_ylabel('Number of Circulars', fontsize=11)
    ax1.set_title('Degree Distribution', fontsize=12, fontweight='bold')
    ax1.grid(True, alpha=0.3)

    # 2. In-degree vs Out-degree
    ax2 = axes[0, 1]
    in_degrees = [G.in_degree(n) for n in G.nodes() if not G.nodes[n].get('is_external', False)]
    out_degrees = [G.out_degree(n) for n in G.nodes() if not G.nodes[n].get('is_external', False)]
    ax2.scatter(out_degrees, in_degrees, alpha=0.6, s=100, color='coral')
    ax2.set_xlabel('Out-degree (References Made)', fontsize=11)
    ax2.set_ylabel('In-degree (Times Referenced)', fontsize=11)
    ax2.set_title('Reference Patterns', fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.3)

    # 3. Top 10 most referenced circulars
    ax3 = axes[1, 0]
    in_degree_dict = dict(G.in_degree())
    top_referenced = sorted(in_degree_dict.items(), key=lambda x: x[1], reverse=True)[:10]
    if top_referenced:
        nodes, counts = zip(*top_referenced)
        labels = [G.nodes[n].get('circular_no', n)[:25] for n in nodes]
        y_pos = range(len(labels))
        ax3.barh(y_pos, counts, color='green', alpha=0.7)
        ax3.set_yticks(y_pos)
        ax3.set_yticklabels(labels, fontsize=8)
        ax3.set_xlabel('Number of Incoming References', fontsize=11)
        ax3.set_title('Top 10 Most Referenced Circulars', fontsize=12, fontweight='bold')
        ax3.invert_yaxis()
        ax3.grid(True, alpha=0.3, axis='x')

    # 4. Top 10 circulars with most outgoing references
    ax4 = axes[1, 1]
    out_degree_dict = dict(G.out_degree())
    top_referencing = sorted(out_degree_dict.items(), key=lambda x: x[1], reverse=True)[:10]
    if top_referencing:
        nodes, counts = zip(*top_referencing)
        labels = [G.nodes[n].get('circular_no', n)[:25] for n in nodes]
        y_pos = range(len(labels))
        ax4.barh(y_pos, counts, color='orange', alpha=0.7)
        ax4.set_yticks(y_pos)
        ax4.set_yticklabels(labels, fontsize=8)
        ax4.set_xlabel('Number of Outgoing References', fontsize=11)
        ax4.set_title('Top 10 Circulars Making Most References', fontsize=12, fontweight='bold')
        ax4.invert_yaxis()
        ax4.grid(True, alpha=0.3, axis='x')

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"  ✅ Saved: {output_file}")
    plt.close()


def print_network_metrics(G: nx.DiGraph):
    """Print detailed network analysis metrics"""
    print("\n" + "=" * 80)
    print("NETWORK ANALYSIS METRICS")
    print("=" * 80)

    # Basic metrics
    print(f"\nBasic Metrics:")
    print(f"  Total Nodes: {G.number_of_nodes()}")
    print(f"  Total Edges: {G.number_of_edges()}")
    print(f"  Density: {nx.density(G):.4f}")

    # Degree metrics
    degrees = [G.degree(n) for n in G.nodes()]
    if degrees:
        print(f"\nDegree Statistics:")
        print(f"  Average Degree: {sum(degrees) / len(degrees):.2f}")
        print(f"  Max Degree: {max(degrees)}")
        print(f"  Min Degree: {min(degrees)}")

    # Connectivity
    print(f"\nConnectivity:")
    print(f"  Is Directed Acyclic Graph (DAG): {nx.is_directed_acyclic_graph(G)}")
    print(f"  Number of Weakly Connected Components: {nx.number_weakly_connected_components(G)}")
    print(f"  Number of Strongly Connected Components: {nx.number_strongly_connected_components(G)}")

    # Centrality
    print(f"\nCentrality Analysis:")
    try:
        pagerank = nx.pagerank(G)
        top_pagerank = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)[:5]
        print(f"  Top 5 by PageRank:")
        for i, (node, score) in enumerate(top_pagerank, 1):
            circ_no = G.nodes[node].get('circular_no', node)
            print(f"    {i}. {circ_no[:40]} (score: {score:.4f})")
    except:
        print("  PageRank calculation failed")

    print("=" * 80)


def main():
    """Main function to visualize the knowledge graph"""

    print("=" * 80)
    print("SEBI Circular Knowledge Graph Visualizer")
    print("=" * 80)
    print()

    # Configuration
    json_file = "graph_outputs/circular_knowledge_graph.json"
    output_dir = Path("graph_outputs")

    # Check if input file exists
    if not Path(json_file).exists():
        print(f"❌ Error: Input file '{json_file}' not found!")
        print("Please run 'python3 circular_knowledge_graph.py' first to generate the graph.")
        return

    # Load graph
    G = load_graph_from_json(json_file)

    if G.number_of_nodes() == 0:
        print("❌ Error: Graph is empty!")
        return

    # Generate visualizations
    print("\n" + "=" * 80)
    print("Generating visualizations...")
    print("=" * 80)
    print()

    visualize_full_graph(G, output_dir / "graph_visualization_full.png")
    visualize_top_circulars(G, output_dir / "graph_visualization_top_circulars.png", top_n=15)
    create_statistics_report(G, output_dir / "graph_statistics.png")

    # Print network metrics
    print_network_metrics(G)

    print("\n" + "=" * 80)
    print("✅ Visualization complete!")
    print("=" * 80)
    print(f"\nOutputs saved to '{output_dir}/':")
    print(f"  • graph_visualization_full.png (Full network)")
    print(f"  • graph_visualization_top_circulars.png (Top connected circulars)")
    print(f"  • graph_statistics.png (Statistical analysis)")
    print()


if __name__ == "__main__":
    main()
