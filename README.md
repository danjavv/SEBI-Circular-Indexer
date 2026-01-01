Demo Link - https://www.loom.com/share/dab4ceaf1c23481fb7a73dc1fd1f5e90

Presently, the demo is running on 50 circulars from page 1 and 2 of the sebi circulars website
to simplify the model. It could as well run on all circulars, around 2000 of them, but it would
take too much time. I have used LLM APIs for the task - Anthropic Claude API KEY, like analyzing the scanned text of a PDF, extracting relevant information from the circulars, like references, title, data etc.

Tools used - No LLM APIs were used. The solution is entirely rule-based using:

  - PyPDF2 - PDF text extraction
  - Selenium + BeautifulSoup - Web scraping from SEBI website
  - NetworkX - Graph construction and network analysis
  - Matplotlib - Visualization and plotting
  - Regex patterns - 8 different patterns for circular reference extraction
  (rule-based, not LLM-based)
  - Python - Core implementation language


How to run:-

1. Activate the virtual environment

```bash
     cp .env.example .env
     # Then edit .env and add your Anthropic API key:
     # ANTHROPIC_API_KEY=your_actual_api_key_here

     python3 -m venv venv
     source venv/bin/activate
```

2. Install the dependencies

```bash
     python3 -m pip install -r requirements.txt
```

3. Run the files one by one 

```bash
     python3 sebi_circular_scraper.py
```

What this file does?

  Scrapes circular metadata from the SEBI website using Selenium-powered 
  browser automation. Navigates through paginated listings (109+ pages 
  available), extracts circular titles and reference numbers from detail 
  pages, and saves the data to sebi_circular_numbers.txt as a searchable 
  database. Includes configurable page limits and rate limiting to be
  respectful of server resources. 

```bash
     python3 circular_reference_extractor.py
```

What this file does?

  Analyzes a single SEBI circular PDF to extract all references to other 
  circulars using 8 different regex patterns. Loads the circular database 
  from sebi_circular_numbers.txt and matches extracted references against 
  it. Filters out self-references and generates a detailed report
  (circular_references_found.txt) showing which references were matched in
  the database and which are external/unmatched.


TO RUN THE CIRCULAR KNOWLEDGE GRAPH WORKFLOW - 

It builds a directed graph where each circular is a node and each reference creates a directed edge from the source circular to the referenced circular

```bash
     python3 circular_knowledge_graph.py
     python3 visualize_circular_graph.py
```

What these files do?

  circular_knowledge_graph.py scans all PDF circulars in the circulars/ 
  directory, extracts references between them using llm and regex patterns, and
  builds a comprehensive directed graph showing how circulars reference each
  other. Creates a file in graph_outputs/ directory - circular_knowledge_graph.json containing references of each pdf file. Exports the graph in multiple formats (JSON, GraphML, Cytoscape) with detailed statistics. 
  
  visualize_circular_graph.py loads this graph data and generates visual network diagrams showing the full reference network, highlights top connected circulars, and produces statistical analysis charts with network metrics like degree distribution and connectivity.

In the future, we could implement a script to download all the circulars from the website. Presently, my script was downloading the same circular over and over again so I downloaded the latest 50 circulars manually and kept them in circulars/ directory.

NOW THE FINAL FILE - RUN THIS AFTER CREATING THE KNOWLEDGE GRAPH

```bash
     # Analyze a specific circular
    python3 analyze_circular_references.py circulars/1754651443956.pdf
```

What this does?

Analyzes a single SEBI circular PDF to discover all its direct and 
indirect references by leveraging the knowledge graph. Extracts references
using regex patterns, checks which ones exist in the knowledge graph, and
traces multi-level dependency chains (references of references) up to 5 
levels deep using BFS. Generates a reference tree visualization showing 
the complete regulatory context and saves a detailed report to 
circular_reference_analysis.txt.

ANALYSIS :-

Why running python3 analyze_circular_references.py circulars/1749727622982.PDF will show no indirect references:

  - Direct references found: SEBI/HO/DDHS/DDHS_Div3/P/CIR/2021/672 and
  SEBI/HO/DDHS/DDHS_Div3/P/CIR/2021/690
  - Problem: These are circulars from 2021 that we don't have PDFs for
  - Result: They are "external references" - we can't extract what
  references they make
  - Indirect references: None (because we don't have their PDFs)

Why running python3 analyze_circular_references.py circulars/1758794128066.pdf showed indirect references:

  - Direct references found: SEBI/HO/ITD-1/ITD_VIAP/P/CIR/2025/111 and
  SEBI/HO/ITD-1/ITD_VIAP/P/CIR/2025/121
  - Status: Both are "in graph" (we have their PDFs!)
  - Indirect references: 1 found at level 2
    - Circular 121 references circular 111
    - So 111 appears as both a direct reference (level 1) AND an indirect
  reference (level 2) via circular 121
  - Result: Complete reference chain shown in tree structure

Graph Statistics:

  - Total edges: 56
  - Internal edges (point to circulars we have): 10
  - External edges (point to circulars we don't have): 46

So 82% of references point to circulars outside our dataset (older circulars, gazette notifications, etc.), which is why most analyses won't show indirect references.