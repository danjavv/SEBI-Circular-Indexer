Demo Link - https://www.loom.com/share/dab4ceaf1c23481fb7a73dc1fd1f5e90

Presently, the demo is running on 50 circulars from page 1 and 2 of the sebi circulars website
to simplify the model. It could as well run on all circulars, around 2000 of them, but it would
take too much time. I have not used LLM APIs for any task, like analyzing the scanned text of a PDF and etc. because I didnt have any LLM API. The GEMINI API has reduced the free tier to just 20 requests per day. I have implemented rule-based extraction of circular numbers from the circulars based on regex patterns. But LLM processing can be integrated in the steps between the entire workflow to reduce the errors if any.

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
  directory, extracts references between them using regex patterns, and
  builds a comprehensive directed graph showing how circulars reference each
   other. Exports the graph in multiple formats (JSON, GraphML, Cytoscape)
  with detailed statistics. visualize_circular_graph.py loads this graph
  data and generates visual network diagrams showing the full reference
  network, highlights top connected circulars, and produces statistical
  analysis charts with network metrics like degree distribution and
  connectivity.

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