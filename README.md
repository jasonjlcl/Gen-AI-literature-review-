# Gen-AI-literature-review-
# Automated Literature Review Pipeline

This repository contains the code and documentation for the automated literature-review pipeline used in our A-grade “Business Transformation with Generative AI” project.

## 📖 Overview
We ingested 50,200 OpenAlex records on “AI in Manufacturing” and distilled them into a structured 23-field dataset, enabling both quantitative and qualitative analysis of generative AI’s impact on manufacturing.

---

## 🚀 Directory Structure

```text
.
├── data/
│   ├── openalex_raw.csv
│   └── abstracts_filtered.csv
├── doi_resolver/
│   ├── resolve_dois.py
│   └── gui.py
├── extractor/
│   └── extract_fields.py
├── utils/
├── notebooks/
└── README.md


---

## 🔍 Methodology

1. **Data Acquisition**  
   - Downloaded **50,200** records from OpenAlex with query `"AI in Manufacturing"`.  
   - Stored as `data/openalex_raw.csv`.

2. **Initial Pre-processing**  
   - Loaded raw CSV into a Pandas DataFrame.  
   - Filtered out entries without abstracts → **17,324** records (`data/abstracts_filtered.csv`).

3. **Asynchronous DOI Resolution**  
   - Script: `doi_resolver/resolve_dois.py` uses `asyncio` + `aiohttp`.  
   - GUI: `doi_resolver/gui.py` (Tkinter) for selecting input file, monitoring progress, and exporting `resolved_dois.json`.

4. **23-Field Extraction**  
   - Script: `extractor/extract_fields.py`  
   - Calls Gemini 1.5 via API to parse each abstract into fields such as:  
     - Use Cases  
     - Opportunities  
     - Challenges  
     - (…and 20 more)  
   - Processes records concurrently with `ThreadPoolExecutor`.

5. **Recovery & QA**  
   - Failed API calls are logged and retried via `utils/recovery.py`.  
   - Manual spot-checks performed in `notebooks/qa_checks.ipynb`.

6. **Final Aggregation**  
   - Merged all JSON outputs into `data/final_dataset.csv` (23 fields per record).  
   - Computed evaluation metrics (e.g., technical complexity, ROI impact) in `notebooks/analysis.ipynb`.

---

## 📈 Results & Insights
- **Coverage:** 8,128 abstracts related to manufacturing context.  
- **Key Findings:**  
  - Only 231 papers explicitly mention “generative AI.”  
  - Predominant use cases: predictive maintenance, defect detection, digital twins.  
- **Implications:** Gap between traditional AI adoption and generative AI potential—see [Key Findings Table](notebooks/analysis.ipynb).

---

## 🛠️ How to Run
1. Clone this repo and create a virtual environment:  
   ```bash
   git clone https://github.com/yourusername/lit-review-pipeline.git
   cd lit-review-pipeline
   python3 -m venv venv && source venv/bin/activate
   pip install -r requirements.txt


