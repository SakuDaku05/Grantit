import argparse
import requests
from bs4 import BeautifulSoup
import re
import json
import csv
import os
from dateutil.parser import parse

# We'll try to load the Gemini API for advanced tagging if it's available.
try:
    import google.genai as genai
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

# If we have the right libraries, we'll also prepare vector embeddings for searching later.
try:
    from sentence_transformers import SentenceTransformer
    VECTOR_AVAILABLE = True
    print("[*] Loading ML Embedding Model (all-MiniLM-L6-v2)...")
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
except ImportError:
    VECTOR_AVAILABLE = False
    embedding_model = None

# This defines the standard format for all the grant data we'll be collecting.
SCHEMA_KEYS = [
    "foa_id", "title", "agency", "open_date", "close_date", 
    "eligibility", "program_description", "award_range", "pdf_url", "url", "tags", "embedding"
]

class FOAPipeline:
    """A robust data pipeline for ingesting and tagging Funding Opportunity Announcements (FOAs)."""
    
    def __init__(self):
        # We use standard headers so the server sees us as a regular visitor.
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.base_schema = {key: None for key in SCHEMA_KEYS}
        self.base_schema["tags"] = []

    def _normalize_date(self, date_str):
        """Converts extracted dates into ISO format (YYYY-MM-DD)."""
        if not date_str: return None
        try:
            # Provide timezone context so dateutil doesn't throw a warning for EDT/EST
            tz_mapping = {"EDT": -4 * 3600, "EST": -5 * 3600}
            parsed_date = parse(date_str, fuzzy=True, tzinfos=tz_mapping)
            return parsed_date.strftime("%Y-%m-%d")
        except Exception:
            return date_str

    def ingest(self, url):
        """Routes the URL to the appropriate agency parser."""
        print(f"\n[*] Starting ingestion pipeline for: {url}")
        if "grants.gov" in url:
            return self._parse_grants_gov(url)
        elif "nsf.gov" in url:
            return self._parse_nsf(url)
        else:
            raise ValueError("Unsupported URL. Please provide a valid NSF or Grants.gov URL.")

    def _parse_nsf(self, url):
        """Scrapes NSF using JSON-LD metadata, DOM parsing, and heuristic fallbacks."""
        print("[*] Strategy: NSF HTML DOM Parsing with JSON-LD extraction...")
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        data = self.base_schema.copy()
        data["url"] = url
        data["agency"] = "National Science Foundation (NSF)"

        try:
            # Let's see if the page has structured meta-data we can easily pull from.....
            for script in soup.find_all('script', type='application/ld+json'):
                try:
                    schema_data = json.loads(script.string)
                    if isinstance(schema_data, list): schema_data = schema_data[0]
                    
                    if schema_data.get('@type') in ['FundingScheme', 'Grant', 'WebPage']:
                        if "name" in schema_data: data["title"] = schema_data["name"]
                        if "description" in schema_data: data["program_description"] = schema_data["description"]
                        if "expires" in schema_data: data["close_date"] = self._normalize_date(schema_data["expires"])
                except Exception:
                    pass 

            # If structured data is missing, we'll try to find what we need in the page layout.
            if not data["title"]:
                title_tag = soup.find('h1')
                data["title"] = title_tag.text.strip() if title_tag else "Unknown Title"

            id_match = re.search(r'NSF \d{2}-\d{3}', response.text)
            data["foa_id"] = id_match.group(0) if id_match else f"Generated-NSF-{str(hash(url))[:6]}"

            main_content = soup.find('main')
            if main_content:
                # We'll skip over short snippets and look for the actual program description.
                if not data["program_description"]:
                    paragraphs = main_content.find_all('p')
                    valid_text = [p.text.strip() for p in paragraphs if len(p.text.strip()) > 200]
                    if valid_text:
                        data["program_description"] = " ".join(valid_text[:2]) 

                # We'll look specifically for the deadline date in the text.
                if not data["close_date"]:
                    for tag in main_content.find_all(string=re.compile("Deadline", re.I)):
                        full_text = tag.parent.text.strip()
                        date_match = re.search(r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s\d{1,2},\s\d{4}', full_text, re.I)
                        if date_match:
                            data["close_date"] = self._normalize_date(date_match.group(0))
                            break
                            
            # Finally, let's look for a link to the official PDF document.
            if not data.get("pdf_url"):
                for link in soup.find_all('a', href=re.compile(r'\.pdf', re.I)):
                    href = link.get('href', '')
                    if 'nsf.gov' in href or href.startswith('/'):
                        data["pdf_url"] = "https://www.nsf.gov" + href if href.startswith('/') else href
                        break

        except Exception as e:
            print(f"[!] Warning: Partial extraction failure for NSF: {e}")

        return data

    def _parse_grants_gov(self, url):
        """Fetches Grants.gov data using their internal fetchOpportunity REST API."""
        print("[*] Strategy: Grants.gov REST API (fetchOpportunity)...")
        data = self.base_schema.copy()
        data["url"] = url
        
        opp_id_match = re.search(r'\d{5,7}', url)
        if not opp_id_match:
            print("[!] Could not extract Grants.gov internal Opportunity ID from URL.")
            return data
            
        opp_id = opp_id_match.group(0)
        api_url = "https://api.grants.gov/v1/api/fetchOpportunity"
        payload = {"opportunityId": int(opp_id)} 
        
        try:
            response = requests.post(api_url, json=payload, headers=self.headers)
            response.raise_for_status()
            api_data = response.json()
            
            if "data" in api_data and api_data["data"]:
                opp = api_data["data"]
                synopsis = opp.get("synopsis", {})
                
                data["foa_id"] = opp.get("opportunityNumber", f"Generated-GG-{opp_id}")
                data["title"] = opp.get("opportunityTitle", "Unknown Title")
                data["agency"] = synopsis.get("agencyName", opp.get("owningAgencyCode", "Unknown Agency"))
                
                data["open_date"] = self._normalize_date(synopsis.get("postingDate"))
                data["close_date"] = self._normalize_date(synopsis.get("closeDate"))
                
                data["program_description"] = synopsis.get("synopsisDesc", "Description not provided.")
                data["eligibility"] = synopsis.get("applicantEligibilityDesc")
                
                # We'll make sure to handle cases where the value is literally written as "none".
                floor = synopsis.get('awardFloor', 0)
                ceiling = synopsis.get('awardCeiling', 0)
                if str(floor).lower() == 'none': floor = 0
                if str(ceiling).lower() == 'none': ceiling = 0
                
                if floor or ceiling:
                    data["award_range"] = f"${floor} - ${ceiling}"
            else:
                print(f"[!] Grants.gov API returned no data for internal ID: {opp_id}.")
                
        except Exception as e:
            print(f"[!] Grants.gov API fetch failed: {e}")

        return data

    def apply_tags(self, data):
        """Applies deterministic, rule-based semantic tags."""
        print("[*] Applying rule-based semantic tags (ISSR Taxonomy)...")
        tags = set()
        text_to_analyze = f"{data.get('title', '')} {data.get('program_description', '')}".lower()
        
        # These categories help the Institute for Social Science Research (ISSR) organize these grants.
        rules = {
            "Social Sciences & Humanities": ["social science", "sociology", "psychology", "public policy", "humanities", "behavioral", "economics"],
            "AI/Machine Learning": ["artificial intelligence", "machine learning", "cyberinfrastructure", "algorithm", "neural network"],
            "Climate & Environment": ["climate change", "environmental sustainability", "ecology", "carbon"],
            "Biomedical/Health": ["clinical", "biomedical", "disease", "health outcomes", "medical"],
            "STEM Education": ["undergraduate", "curriculum", "stem education", "k-12", "education"]
        }
        
        for tag, keywords in rules.items():
            if any(keyword in text_to_analyze for keyword in keywords):
                tags.add(tag)
                
        data["tags"] = list(tags)
        return data

    def apply_llm_tags(self, data):
        """Stretch Goal: Uses Gemini API to dynamically categorize the grant in strict JSON."""
        print("[*] Attempting advanced LLM Semantic Tagging with Gemini...")
        
        api_key = os.getenv("GEMINI_API_KEY")
        if not LLM_AVAILABLE or not api_key:
            print("[-] No GEMINI_API_KEY found or library missing. Gracefully falling back to rule-based tagging.")
            return self.apply_tags(data)

        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            prompt = f"""
            You are a grant taxonomy expert for the Institute for Social Science Research (ISSR).
            Analyze the following funding opportunity:
            
            Title: {data.get('title')}
            Description: {data.get('program_description')}
            
            Categorize it using ONLY the following official tags:
            - AI/Machine Learning
            - Climate & Environment
            - Biomedical/Health
            - STEM Education
            - Social Sciences & Humanities
            
            Return the output STRICTLY as a valid JSON array of strings. Do not include markdown formatting like ```json.
            Example: ["STEM Education", "AI/Machine Learning"]
            """
            
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                )
            )
            
            llm_tags = json.loads(response.text)
            data["tags"] = llm_tags
            print(f"[+] Gemini successfully applied tags: {llm_tags}")
            return data
            
        except Exception as e:
            print(f"[!] Gemini Tagging API failed: {e}. Gracefully falling back to rule-based tagging.")
            return self.apply_tags(data)

    def generate_vector_embedding(self, data):
        """Generates a mathematical representation of the data to help with smart searching."""
        if not VECTOR_AVAILABLE or not embedding_model:
            print("[-] sentence-transformers not installed. Skipping vector embeddings.")
            data["embedding"] = None
            return data
            
        print("[*] Generating semantic vector embedding for FAISS index prep...")
        try:
            text_to_embed = f"{data.get('title', '')}. {data.get('program_description', '')}"
            vector = embedding_model.encode([text_to_embed])[0]
            data["embedding"] = [round(float(num), 5) for num in vector] 
            print("[+] Successfully generated 384-dimensional embedding.")
        except Exception as e:
            print(f"[!] Embedding generation failed: {e}")
            data["embedding"] = None
            
        return data

    def export(self, data, out_dir):
        """Saves data to JSON and CSV formats."""
        os.makedirs(out_dir, exist_ok=True)
        json_path = os.path.join(out_dir, "foa.json")
        csv_path = os.path.join(out_dir, "foa.csv")
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
            
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=SCHEMA_KEYS)
            writer.writeheader()
            csv_data = data.copy()
            csv_data['tags'] = ", ".join(csv_data.get('tags', []))
            if csv_data.get('embedding'):
                csv_data['embedding'] = str(csv_data['embedding'])
            writer.writerow(csv_data)
            
        print(f"[+] Success! Extracted data saved to {os.path.abspath(out_dir)}")


def main():
    parser = argparse.ArgumentParser(description="FOA Ingestion and Tagging Pipeline (Project_ISSR)")
    parser.add_argument("--url", required=True, help="Target FOA URL (Grants.gov or NSF)")
    parser.add_argument("--out_dir", default="./out", help="Output directory for JSON/CSV results (default: ./out)")
    args = parser.parse_args()

    pipeline = FOAPipeline()

    try:
        # First, we'll fetch the data from the provided URL.
        extracted_data = pipeline.ingest(args.url)
        
        # Next, we'll categorize the grant based on its content.
        tagged_data = pipeline.apply_llm_tags(extracted_data) 
        
        # Then, we'll create a vector embedding for the grant's description.
        final_data = pipeline.generate_vector_embedding(tagged_data)
        
        # And finally, we'll save the results in both JSON and CSV formats.
        pipeline.export(final_data, args.out_dir)
        
    except Exception as e:
        print(f"\n[!] Pipeline Execution Failed: {e}")

if __name__ == "__main__":
    main()