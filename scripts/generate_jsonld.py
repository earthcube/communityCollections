#!/usr/bin/env python3
"""
Generate JSON-LD descriptions for datasets from Google Sheet using AI.

This script reads a CSV export of the Google Sheet, processes datasets
that need JSON-LD (hasJSONLD? = FALSE or #ERROR!), and generates
JSON-LD descriptions using AI prompts.
"""

import csv
import json
import os
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional

# Try to import AI client libraries (user needs to install)
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# Standard libraries
import requests
from bs4 import BeautifulSoup


class AIClient:
    """Abstract base class for AI clients."""
    
    def detect_datasets(self, url: str, webpage_content: str, context: Dict) -> Dict:
        """Detect datasets on a webpage and extract metadata."""
        raise NotImplementedError
    
    def generate_jsonld(self, metadata: Dict, example_jsonld: str) -> str:
        """Generate JSON-LD from metadata."""
        raise NotImplementedError


class OpenAIClient(AIClient):
    """OpenAI API client."""
    
    def __init__(self, api_key: str, model: str = "gpt-4", base_url: str = None):
        self.client = openai.OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
    
    def _call_api(self, prompt: str, system_prompt: str = None) -> str:
        """Make API call to OpenAI."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        print(f"  Sending request to API (this may take a minute)...")
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.3,
            timeout=120.0  # 2 minute timeout
        )
        print(f"  Received response")
        return response.choices[0].message.content
    
    def detect_datasets(self, url: str, webpage_content: str, context: Dict) -> Dict:
        """Detect datasets using OpenAI."""
        prompt_path = Path(__file__).parent.parent / "prompts" / "dataset-detection-prompt.txt"
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
        
        # Limit content to 5000 chars to speed up API calls
        limited_content = webpage_content[:5000]
        prompt = prompt_template.format(
            URL=url,
            CONTENT=limited_content,
            DATASET_NAME=context.get('Dataset Name', ''),
            GROUP=context.get('Group', ''),
            DESCRIPTION=context.get('Description', '')
        )
        
        response = self._call_api(prompt)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {"raw_response": response, "error": "Failed to parse JSON"}
    
    def generate_jsonld(self, metadata: Dict, example_jsonld: str) -> str:
        """Generate JSON-LD using OpenAI."""
        prompt_path = Path(__file__).parent.parent / "prompts" / "jsonld-generation-prompt.txt"
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
        
        prompt = prompt_template.format(
            DATASET_NAME=metadata.get('name', ''),
            URL=metadata.get('url', ''),
            DESCRIPTION=metadata.get('description', ''),
            GROUP=metadata.get('group', ''),
            CREATOR=metadata.get('creator', ''),
            PROVIDER=metadata.get('provider', ''),
            PUBLISHER=metadata.get('publisher', ''),
            KEYWORDS=metadata.get('keywords', ''),
            SPATIAL_COVERAGE=metadata.get('spatial_coverage', ''),
            EXTRACTED_METADATA=json.dumps(metadata.get('extracted', {}), indent=2),
            EXAMPLE_JSONLD=example_jsonld[:2000]  # Limit example size
        )
        
        response = self._call_api(prompt)
        # Try to extract JSON from response
        try:
            # Look for JSON block in response
            if '{' in response:
                start = response.find('{')
                end = response.rfind('}') + 1
                json_str = response[start:end]
                # Validate it's valid JSON
                json_data = json.loads(json_str)
                # Fix spatial coverage format if needed
                json_data = self._fix_spatial_coverage(json_data)
                return json.dumps(json_data, indent=2)
            return response
        except (json.JSONDecodeError, ValueError):
            return response
    
    def _fix_spatial_coverage(self, data: Dict) -> Dict:
        """Fix spatial coverage box format to match Schema.org standard."""
        if isinstance(data, dict) and 'spatialCoverage' in data:
            spatial = data['spatialCoverage']
            if isinstance(spatial, dict) and 'geo' in spatial:
                geo = spatial['geo']
                if isinstance(geo, dict) and 'box' in geo:
                    box = geo['box']
                    if isinstance(box, str):
                        # Fix format: "20 -40 50 10" -> "20,-40 50,10"
                        # Check if it's space-separated (wrong format)
                        parts = box.split()
                        if len(parts) == 4 and ',' not in box:
                            try:
                                # Convert to proper format: "west,south east,north"
                                west, south, east, north = map(float, parts)
                                geo['box'] = f"{west},{south} {east},{north}"
                            except (ValueError, TypeError):
                                pass  # If conversion fails, leave as is
        return data


class NRPClient(OpenAIClient):
    """National Research Platform (NRP) LLM client - OpenAI-compatible."""
    
    def __init__(self, api_key: str, model: str = "meta-llama/Llama-3.1-70B-Instruct"):
        # NRP uses OpenAI-compatible API at ellm.nrp-nautilus.io
        base_url = "https://ellm.nrp-nautilus.io/v1"
        super().__init__(api_key=api_key, model=model, base_url=base_url)
        print(f"Using NRP LLM endpoint: {base_url}")
        print(f"Using model: {model}")


class AnthropicClient(AIClient):
    """Anthropic (Claude) API client."""
    
    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
    
    def _call_api(self, prompt: str, system_prompt: str = None) -> str:
        """Make API call to Anthropic."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_prompt or "You are a helpful assistant that generates structured data.",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    
    def detect_datasets(self, url: str, webpage_content: str, context: Dict) -> Dict:
        """Detect datasets using Anthropic."""
        prompt_path = Path(__file__).parent.parent / "prompts" / "dataset-detection-prompt.txt"
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
        
        prompt = prompt_template.format(
            URL=url,
            CONTENT=webpage_content[:10000],
            DATASET_NAME=context.get('Dataset Name', ''),
            GROUP=context.get('Group', ''),
            DESCRIPTION=context.get('Description', '')
        )
        
        response = self._call_api(prompt)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {"raw_response": response, "error": "Failed to parse JSON"}
    
    def generate_jsonld(self, metadata: Dict, example_jsonld: str) -> str:
        """Generate JSON-LD using Anthropic."""
        prompt_path = Path(__file__).parent.parent / "prompts" / "jsonld-generation-prompt.txt"
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
        
        prompt = prompt_template.format(
            DATASET_NAME=metadata.get('name', ''),
            URL=metadata.get('url', ''),
            DESCRIPTION=metadata.get('description', ''),
            GROUP=metadata.get('group', ''),
            CREATOR=metadata.get('creator', ''),
            PROVIDER=metadata.get('provider', ''),
            PUBLISHER=metadata.get('publisher', ''),
            KEYWORDS=metadata.get('keywords', ''),
            SPATIAL_COVERAGE=metadata.get('spatial_coverage', ''),
            EXTRACTED_METADATA=json.dumps(metadata.get('extracted', {}), indent=2),
            EXAMPLE_JSONLD=example_jsonld[:2000]
        )
        
        response = self._call_api(prompt)
        try:
            if '{' in response:
                start = response.find('{')
                end = response.rfind('}') + 1
                json_str = response[start:end]
                json_data = json.loads(json_str)
                # Fix spatial coverage format if needed
                json_data = self._fix_spatial_coverage(json_data)
                return json.dumps(json_data, indent=2)
            return response
        except (json.JSONDecodeError, ValueError):
            return response
    
    def _fix_spatial_coverage(self, data: Dict) -> Dict:
        """Fix spatial coverage box format to match Schema.org standard.
        
        Converts "20 -40 50 10" to "20,-40 50,10" format.
        """
        if isinstance(data, dict) and 'spatialCoverage' in data:
            spatial = data['spatialCoverage']
            if isinstance(spatial, dict) and 'geo' in spatial:
                geo = spatial['geo']
                if isinstance(geo, dict) and 'box' in geo:
                    box = geo['box']
                    if isinstance(box, str):
                        # Fix format: "20 -40 50 10" -> "20,-40 50,10"
                        # Check if it's space-separated without commas (wrong format)
                        parts = box.split()
                        if len(parts) == 4 and ',' not in box:
                            try:
                                # Convert to proper format: "west,south east,north"
                                west, south, east, north = map(float, parts)
                                geo['box'] = f"{west},{south} {east},{north}"
                            except (ValueError, TypeError):
                                pass  # If conversion fails, leave as is
        return data


def fetch_webpage(url: str) -> Optional[str]:
    """Fetch webpage content."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None


def extract_text_content(html: str) -> str:
    """Extract text content from HTML."""
    try:
        soup = BeautifulSoup(html, 'html.parser')
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        return soup.get_text(separator=' ', strip=True)
    except Exception as e:
        print(f"Error parsing HTML: {e}")
        return html[:10000]  # Return first 10k chars if parsing fails


def load_example_jsonld() -> str:
    """Load an example JSON-LD file for reference."""
    example_path = Path(__file__).parent.parent / "data" / "objects" / "summoned" / "gpp" / "2d78c4242a108f70ea2c0604964dc095b34bfd7b.jsonld"
    if example_path.exists():
        with open(example_path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""


def read_csv(csv_path: str) -> List[Dict]:
    """Read the datasets CSV file."""
    datasets = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            datasets.append(row)
    return datasets


def save_jsonld(jsonld_str: str, output_dir: Path, dataset_name: str, url: str) -> Path:
    """Save JSON-LD to file."""
    # Create safe filename from dataset name
    safe_name = "".join(c for c in dataset_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    safe_name = safe_name.replace(' ', '_')[:50]  # Limit length
    
    # Use URL hash as fallback
    import hashlib
    url_hash = hashlib.sha1(url.encode()).hexdigest()[:8]
    
    filename = f"{safe_name}_{url_hash}.jsonld"
    output_path = output_dir / filename
    
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(jsonld_str)
    
    return output_path


def main():
    parser = argparse.ArgumentParser(description='Generate JSON-LD for datasets')
    parser.add_argument('--csv', default='datasets.csv', help='Path to CSV file')
    parser.add_argument('--output-dir', default='data/objects/summoned/generated', help='Output directory for JSON-LD files')
    parser.add_argument('--ai-service', choices=['openai', 'anthropic', 'nrp'], default='nrp', help='AI service to use (default: nrp)')
    parser.add_argument('--api-key', help='API key (or set environment variable)')
    parser.add_argument('--model', help='Model name (optional)')
    parser.add_argument('--limit', type=int, help='Limit number of datasets to process')
    parser.add_argument('--test-url', help='Test with a single URL instead of CSV')
    
    args = parser.parse_args()
    
    # Initialize AI client
    api_key = args.api_key or os.getenv(f"{args.ai_service.upper()}_API_KEY") or os.getenv("NRP_API_KEY")
    if not api_key:
        print(f"Error: API key required. Set {args.ai_service.upper()}_API_KEY environment variable or use --api-key")
        sys.exit(1)
    
    if args.ai_service == 'openai':
        if not OPENAI_AVAILABLE:
            print("Error: openai package not installed. Run: pip install openai")
            sys.exit(1)
        client = OpenAIClient(api_key, args.model or "gpt-4")
    elif args.ai_service == 'nrp':
        if not OPENAI_AVAILABLE:
            print("Error: openai package not installed. Run: pip install openai")
            sys.exit(1)
        # Default NRP models: qwen3, llama3-sdsc, gpt-oss, etc.
        # Available models: qwen3, llama3-sdsc, gpt-oss, gorilla, olmo, gemma3, kimi, etc.
        client = NRPClient(api_key, args.model or "qwen3")
    elif args.ai_service == 'anthropic':
        if not ANTHROPIC_AVAILABLE:
            print("Error: anthropic package not installed. Run: pip install anthropic")
            sys.exit(1)
        client = AnthropicClient(api_key, args.model or "claude-3-5-sonnet-20241022")
    
    output_dir = Path(args.output_dir)
    example_jsonld = load_example_jsonld()
    
    # Test mode with single URL
    if args.test_url:
        print(f"Testing with URL: {args.test_url}")
        html = fetch_webpage(args.test_url)
        if html:
            content = extract_text_content(html)
            context = {'Dataset Name': 'Test Dataset', 'Group': 'test', 'Description': ''}
            result = client.detect_datasets(args.test_url, content, context)
            print("\n=== Detection Result ===")
            print(json.dumps(result, indent=2))
        return
    
    # Process CSV
    datasets = read_csv(args.csv)
    print(f"Found {len(datasets)} datasets in CSV")
    
    # Filter datasets that need JSON-LD
    to_process = [
        d for d in datasets 
        if d.get('hasJSONLD?', '').upper() in ('FALSE', '#ERROR!', '')
        and d.get('Dataset Webpage URL', '').strip()
    ]
    
    if args.limit:
        to_process = to_process[:args.limit]
    
    print(f"Processing {len(to_process)} datasets that need JSON-LD")
    
    for i, dataset in enumerate(to_process, 1):
        url = dataset.get('Dataset Webpage URL', '').strip()
        name = dataset.get('Dataset Name', 'Unknown')
        
        if not url:
            print(f"[{i}/{len(to_process)}] Skipping {name}: No URL")
            continue
        
        print(f"\n[{i}/{len(to_process)}] Processing: {name}")
        print(f"  URL: {url}")
        
        # Fetch webpage
        print("  Fetching webpage...")
        html = fetch_webpage(url)
        if not html:
            print(f"  Warning: Failed to fetch webpage")
            continue
        
        content = extract_text_content(html)
        print(f"  Fetched {len(content)} characters")
        
        # Detect datasets
        print("  Detecting datasets with AI...")
        detection_result = client.detect_datasets(url, content, dataset)
        print(f"  Detection complete")
        
        # Prepare metadata
        metadata = {
            'name': name,
            'url': url,
            'description': dataset.get('Description', ''),
            'group': dataset.get('Group', ''),
            'creator': dataset.get('Creator', ''),
            'provider': dataset.get('Provider', ''),
            'publisher': dataset.get('Publisher', ''),
            'keywords': dataset.get('Keywords', ''),
            'spatial_coverage': f"{dataset.get('box_lon_min', '')},{dataset.get('box_lat_min', '')},{dataset.get('box_lon_max', '')},{dataset.get('box_lat_max', '')}" if dataset.get('box_lon_min') else '',
            'extracted': detection_result
        }
        
        # Generate JSON-LD
        print("  Generating JSON-LD...")
        jsonld = client.generate_jsonld(metadata, example_jsonld)
        
        # Validate JSON
        try:
            json.loads(jsonld)
            print("  Valid JSON")
        except json.JSONDecodeError as e:
            print(f"  Warning: Generated JSON may be invalid: {e}")
        
        # Save
        output_path = save_jsonld(jsonld, output_dir, name, url)
        print(f"  Saved to: {output_path}")


if __name__ == '__main__':
    main()

