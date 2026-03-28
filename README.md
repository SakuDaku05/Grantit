AI-Powered Funding Intelligence Pipeline

GSoC 2026 Screening Task Submission | Corresponding Project: Project_ISSR (Institute for Social Science Research)

The Mission

Researchers at the Institute for Social Science Research (ISSR) frequently miss critical cross-disciplinary funding opportunities because announcements (FOAs) are locked inside disparate government portals, buried in complex PDFs, or hidden behind dynamic web interfaces.

This repository contains a robust, single-file ETL (Extract, Transform, Load) pipeline designed to autonomously ingest, normalize, and semantically tag FOAs. By transforming unstructured government data into a highly queryable, AI-ready database, this tool allows ISSR researchers to focus on scientific impact rather than manual portal searching.

Quick Start: Installation & Execution

This pipeline is built to be lightweight and portable. It features a graceful degradation architecture—meaning if you don't provide an API key or lack the machine learning dependencies, the script will never crash. It simply falls back to standard, deterministic execution.

1. Install Dependencies:

pip install -r requirements.txt


(Dependencies: requests, beautifulsoup4, python-dateutil, google-generativeai, sentence-transformers)

2. Standard Execution (Rule-Based Extraction):
Run the script to test the core ingestion engine. Output saves automatically to ./out.

# Test an active Grants.gov FOA
python main.py --url "[https://www.grants.gov/search-results-detail/360665](https://www.grants.gov/search-results-detail/360665)"

# Test an active NSF FOA
python main.py --url "[https://www.nsf.gov/funding/opportunities/nsf-finders-foundry-national-science-foundation-fostering-interdisciplinary/nsf26-507/solicitation](https://www.nsf.gov/funding/opportunities/nsf-finders-foundry-national-science-foundation-fostering-interdisciplinary/nsf26-507/solicitation)"


3. Advanced Execution (Testing the AI Stretch Goals):
To evaluate the Gemini LLM tagging and Semantic Vector generation, export your Gemini API key to your environment before running. The pipeline will automatically detect the key and upgrade its logic.

# Mac/Linux
export GEMINI_API_KEY="your-api-key-here"
python main.py --url "[https://www.grants.gov/search-results-detail/360665](https://www.grants.gov/search-results-detail/360665)"

# Windows
set GEMINI_API_KEY=your-api-key-here
python main.py --url "[https://www.grants.gov/search-results-detail/360665](https://www.grants.gov/search-results-detail/360665)"


🏗️ Architecture: Why It Was Built This Way

In the real world, data engineering isn't just about downloading a webpage; websites change, servers timeout, and schemas evolve. That’s why I structured the entire project around a single, robust Object-Oriented class: FOAPipeline.

Using a class allowed me to encapsulate the state of the extraction and cleanly separate the ingestion logic (_parse_nsf, _parse_grants_gov) from the transformation logic (apply_tags, generate_vector_embedding). If Grants.gov changes their website tomorrow, I only have to update one isolated method, and the rest of the pipeline remains completely untouched.

Working Smarter: The Grants.gov Pivot

Initially, I planned to scrape Grants.gov using BeautifulSoup. However, while inspecting their network traffic, I noticed the front-end React app was actually pulling data from a hidden internal REST API (fetchOpportunity). Instead of writing brittle HTML scraping logic that breaks when a CSS class changes, I pivoted. I wrote code to extract the 6-digit opportunity ID from the URL and query their internal API directly. This instantly provided 100% accurate data—including exact financial ceilings and floors—without parsing a single line of messy HTML.

The NSF "Boss Fights" & Heuristics

NSF pages required traditional DOM parsing, which introduced several classic scraping hurdles. The code was executing perfectly, but the data required heuristic interventions:

The "s" Deadline Bug: My initial scraper looked for the word "Deadline" and grabbed the adjacent text. One page read: "Full Proposal Deadline(s):". The scraper split the string, grabbed the "s", and tried to save it as a date. The Fix: I implemented a strict Regex pattern (Month DD, YYYY) that explicitly hunts for actual dates, ignoring surrounding boilerplate.

The Congressional Law Bug: To find the official grant PDF, the script looked for the first link ending in .pdf. But on NSF 26-507, the grant referenced a public law, causing the scraper to grab a congress.gov PDF instead of the grant itself. The Fix: I added strict domain filtering, ensuring the pipeline only saves href links belonging to nsf.gov.

The AI Pivot: Why Gemini & Vectors? (Stretch Goals)

1. Gemini 2.5 Flash (LLM Integration)

To prove my readiness for Phase 3 of the GSoC project, I integrated an LLM stretch goal. I specifically chose Google's Gemini 2.5 Flash for a very specific data-engineering reason: Native JSON Mode.

In an automated data pipeline, you don't want an AI that "chats"; you want an AI that formats. By utilizing response_mime_type="application/json", I forced the Gemini model at the API level to strictly output parsable JSON arrays. No markdown backticks, no conversational fluff. This allows the LLM to logically deduce ISSR research categories based on context, guaranteeing structural integrity downstream.

2. Semantic Search Readiness (FAISS/Chroma)

Keyword tagging is limiting. If a grant only mentions "neural networks," a standard search for "AI" will miss it. To solve this, I integrated sentence-transformers (all-MiniLM-L6-v2) to convert the grant descriptions into 384-dimensional mathematical vectors. By exporting this embedding directly into the JSON file, the data is instantly prepped for ingestion into a FAISS or ChromaDB vector database for natural language similarity search.

Developer's Note: The "Text Blob" Anomaly & The Road Ahead

When testing against active NSF solicitations, I hit an interesting anomaly: the program_description occasionally pulled in a massive, unformatted text blob containing tables of contents and "Print to PDF" instructions.

At first glance, this felt like a bug. But it is actually the ultimate proof of why this GSoC project exists. My pipeline is designed to prioritize JSON-LD (hidden structured SEO data) because it is usually highly accurate. However, on certain NSF pages, the webmasters simply copy-pasted the entire document into the background JSON description tag. My code didn't fail; it extracted exactly what the webmaster published.

This highlights a fundamental reality: deterministic web scraping leaves you entirely at the mercy of the webmaster's formatting. You cannot build a beautiful, searchable database for ISSR researchers if descriptions are littered with boilerplate text. This is exactly why Phase 3 is required. We need Artificial Intelligence to sit between the raw extraction and the database to read that massive text blob, comprehend it, and summarize it into a clean, two-paragraph abstract.


### 3. Evaluating Tagging Consistency (Test Suite)
Per the project requirements, a basic evaluation script is included to measure the accuracy of the deterministic semantic tagger against a ground-truth dataset (which includes edge-cases and false-positive traps). 

To run the evaluation suite and view the Precision, Recall, and F1-Scores, run:

python evaluate.py

---

## 🕸️ Design Note: Scope & Scalability (Parser vs. Crawler)

A common pitfall in data engineering tasks is conflating a **Parser** with a **Crawler**. This screening submission explicitly focuses on delivering a flawless **Parser**. 

Why doesn't this script automatically download all 10,000 active grants from Grants.gov at once?

1. **Strict Adherence to Requirements:** The task specifically requested a minimal script that accepts a single `--url` argument to evaluate the core metadata extraction logic. 
2. **Separation of Concerns:** In an enterprise ETL pipeline, navigating pagination (Crawling) and cleaning messy HTML/JSON (Parsing) are entirely separate microservices. Building a bulletproof parser that handles edge cases (like $0 ceilings and hidden JSON-LD schemas) is the most computationally complex hurdle.
3. **Resource Respect:** Executing a recursive web-spider during a local screening evaluation risks rate limiting the mentor's IP address or overloading government servers.

**The Roadmap to Scale:** Wrapping a perfectly functioning parser inside an asynchronous crawler is a highly solvable scaling problem.**Phase 1** of the summer project will involve migrating this exact single URL logic into a distributed `Scrapy` or `Celery` worker queue to enable continuous, automated ingestion of the entire agency directory.

Why I'm the Right Fit for this problem??

When I look at the goals of the Institute for Social Science Research, I don't just see a Python coding task; I see a massive bottleneck in the scientific process. Researchers are spending hours digging through archaic portals instead of designing studies.

I would excel in this GSoC role because I don't just write scripts that work on the "happy path." I anticipate the edge cases. I build fail safes and graceful degradations so the pipeline never crashes. I know when to use a fast, cheap Regex heuristic, and when to deploy a heavy, mathematical LLM vectorization.

If provided the opportunity this summer, I won't be spending the first month learning how to scrape; I will be spending it scaling this pipeline to ingest thousands of grants, giving the ISSR an enterprise grade funding intelligence engine from day one.

