#!/usr/bin/env python3
"""
Generate JSON-LD descriptions for datasets from Google Sheet using AI.

This script reads a CSV export of the Google Sheet, processes datasets
that need JSON-LD (hasJSONLD? = FALSE or #ERROR!), and generates
JSON-LD descriptions using AI prompts.
"""

import csv
import hashlib
import json
import os
import re
import sys
import time
import argparse
import threading
from pathlib import Path
from typing import Dict, List, Optional

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    # Load .env from project root (parent of scripts directory)
    PROJECT_ROOT_FOR_ENV = Path(__file__).parent.parent
    dotenv_path = PROJECT_ROOT_FOR_ENV / '.env'
    # Use override=True to ensure environment variables are loaded
    load_dotenv(dotenv_path, override=True)
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

# Try to import Gemini (try new package first, fallback to deprecated)
try:
    # Try new google.genai package (supports URL Context Tool)
    from google import genai as new_genai
    from google.genai.types import Tool, UrlContext
    from google.genai import errors as new_genai_errors
    GEMINI_NEW_API = True
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_NEW_API = False
    new_genai_errors = None
    try:
        # Fallback to deprecated google.generativeai package
        import google.generativeai as genai
        from google.api_core import exceptions as google_exceptions
        GEMINI_AVAILABLE = True
    except ImportError:
        GEMINI_AVAILABLE = False
        google_exceptions = None
        new_genai = None
        Tool = None
        UrlContext = None

# Standard libraries
import requests
from bs4 import BeautifulSoup

# Constants
API_TIMEOUT_SECONDS = 360.0  # 6 minutes
MAX_RETRIES = 1
CONTENT_LIMIT_DETECTION = 3000  # Characters for detection prompt (reduced to avoid timeouts)
CONTENT_LIMIT_ANTHROPIC = 10000  # Characters for Anthropic detection
EXAMPLE_JSONLD_LIMIT = 2000  # Characters for example JSON-LD in prompt
WEBPAGE_TIMEOUT = 30  # Seconds for webpage fetching
FILENAME_MAX_LENGTH = 50  # Maximum length for dataset name in filename
URL_HASH_LENGTH = 8  # Length of URL hash in filename
HTML_FALLBACK_LIMIT = 10000  # Characters to return if HTML parsing fails

# Server error codes to detect
SERVER_ERROR_CODES = ['500', '502', '503', '504', 'internal server error']

# Connection error patterns (should be retried)
CONNECTION_ERROR_PATTERNS = [
    'connection refused', 'connection reset', 'connection error',
    'upstream connect error', 'disconnect/reset', 'delayed connect error'
]

# CSV field names
CSV_FIELDS = {
    'HAS_JSONLD': 'hasJSONLD?',
    'WEBPAGE_URL': 'Dataset Webpage URL',
    'NAME': 'Dataset Name',
    'DESCRIPTION': 'Description',
    'GROUP': 'Group',
    'CREATOR': 'Creator',
    'PROVIDER': 'Provider',
    'PUBLISHER': 'Publisher',
    'KEYWORDS': 'Keywords',
    'BOX_LON_MIN': 'box_lon_min',
    'BOX_LAT_MIN': 'box_lat_min',
    'BOX_LON_MAX': 'box_lon_max',
    'BOX_LAT_MAX': 'box_lat_max',
}

# Project root path (parent of scripts directory)
PROJECT_ROOT = Path(__file__).parent.parent
PROMPTS_DIR = PROJECT_ROOT / "prompts"
DATA_DIR = PROJECT_ROOT / "data" / "objects" / "summoned"


class AIClient:
    """Abstract base class for AI clients."""
    
    def detect_datasets(self, url: str, context: Dict) -> Dict:
        """Detect datasets by analyzing the URL directly (AI will browse/analyze the webpage)."""
        raise NotImplementedError
    
    def generate_jsonld(self, metadata: Dict, example_jsonld: str) -> str:
        """Generate JSON-LD from metadata."""
        raise NotImplementedError
    
    def _retry_with_timeout(self, func, *args, **kwargs):
        """Helper method to retry a function call with timeout handling."""
        for attempt in range(MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except TimeoutError as e:
                if attempt < MAX_RETRIES - 1:
                    print(f"  Timeout occurred, retrying ({attempt + 1}/{MAX_RETRIES})...")
                    continue
                else:
                    raise
    
    def _extract_json_from_response(self, response: str) -> str:
        """Extract and validate JSON from API response."""
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
                        parts = box.split()
                        if len(parts) == 4 and ',' not in box:
                            try:
                                # Convert to proper format: "west,south east,north"
                                west, south, east, north = map(float, parts)
                                geo['box'] = f"{west},{south} {east},{north}"
                            except (ValueError, TypeError):
                                pass  # If conversion fails, leave as is
        return data
    
    def _is_server_error(self, error: Exception) -> bool:
        """Check if an exception represents a server error."""
        error_str = str(error).lower()
        return any(code in error_str for code in SERVER_ERROR_CODES)
    
    def _call_api_with_timeout(self, api_call_func):
        """Execute API call with threading-based timeout enforcement."""
        result = [None]
        exception = [None]
        
        def api_call():
            try:
                result[0] = api_call_func()
            except Exception as e:
                exception[0] = e
        
        thread = threading.Thread(target=api_call)
        thread.daemon = True
        thread.start()
        thread.join(timeout=API_TIMEOUT_SECONDS)
        
        if thread.is_alive():
            print(f"  Request exceeded {API_TIMEOUT_SECONDS/60:.0f} minute timeout")
            raise TimeoutError(f"API request timed out after {API_TIMEOUT_SECONDS/60:.0f} minutes")
        
        if exception[0]:
            error_msg = str(exception[0]).lower()
            # Check for timeout errors
            if "timeout" in error_msg or "timed out" in error_msg:
                raise TimeoutError("API request timed out")
            # Check for connection errors
            if any(err in error_msg for err in CONNECTION_ERROR_PATTERNS):
                raise TimeoutError(f"Connection error: {exception[0]}")
            # Check for server errors
            if self._is_server_error(exception[0]):
                raise Exception(f"API server error: {exception[0]}")
            # Re-raise other exceptions
            raise exception[0]
        
        if result[0] is None:
            raise TimeoutError("API request timed out")
        
        return result[0]
    
    def _load_prompt_template(self, filename: str) -> str:
        """Load a prompt template from the prompts directory."""
        prompt_path = PROMPTS_DIR / filename
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt template not found: {prompt_path}")
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def _format_detection_prompt(self, url: str, context: Dict) -> str:
        """Format the dataset detection prompt with URL only (no HTML content)."""
        template = self._load_prompt_template("dataset-detection-prompt.txt")
        return template.format(
            URL=url,
            DATASET_NAME=context.get(CSV_FIELDS['NAME'], ''),
            GROUP=context.get(CSV_FIELDS['GROUP'], ''),
            DESCRIPTION=context.get(CSV_FIELDS['DESCRIPTION'], '')
        )
    
    def _format_generation_prompt(self, metadata: Dict, example_jsonld: str) -> str:
        """Format the JSON-LD generation prompt."""
        template = self._load_prompt_template("jsonld-generation-prompt.txt")
        # Handle empty example_jsonld
        escaped_example = (example_jsonld[:EXAMPLE_JSONLD_LIMIT] if example_jsonld else '').replace('{', '{{').replace('}', '}}')
        escaped_metadata = json.dumps(metadata.get('extracted', {}), indent=2).replace('{', '{{').replace('}', '}}')
        
        return template.format(
            DATASET_NAME=metadata.get('name', ''),
            URL=metadata.get('url', ''),
            DESCRIPTION=metadata.get('description', ''),
            GROUP=metadata.get('group', ''),
            CREATOR=metadata.get('creator', ''),
            PROVIDER=metadata.get('provider', ''),
            PUBLISHER=metadata.get('publisher', ''),
            KEYWORDS=metadata.get('keywords', ''),
            SPATIAL_COVERAGE=metadata.get('spatial_coverage', ''),
            EXTRACTED_METADATA=escaped_metadata,
            EXAMPLE_JSONLD=escaped_example
        )


class OpenAIClient(AIClient):
    """OpenAI API client."""
    
    def __init__(self, api_key: str, model: str = "gpt-4", base_url: str = None):
        self.client = openai.OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
    
    def _call_api(self, prompt: str, system_prompt: str = None, operation: str = "processing") -> str:
        """Make API call to OpenAI with timeout enforcement."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        print(f"  Sending request to API for {operation} (this may take 1-6 minutes)...")
        
        def api_call():
            return self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                timeout=API_TIMEOUT_SECONDS
            )
        
        response = self._call_api_with_timeout(api_call)
        print(f"  Received response")
        if not response.choices or not response.choices[0].message.content:
            raise ValueError("Empty response from API")
        return response.choices[0].message.content
    
    def detect_datasets(self, url: str, context: Dict) -> Dict:
        """Detect datasets using OpenAI by analyzing the URL directly."""
        prompt = self._format_detection_prompt(url, context)
        
        # Debug: Log prompt size
        prompt_size = len(prompt)
        if prompt_size > 10000:
            print(f"  Warning: Large prompt size ({prompt_size} characters), this may cause timeouts")
        
        def call_detect():
            response = self._call_api(prompt, operation="dataset detection")
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                return {"raw_response": response, "error": "Failed to parse JSON"}
        
        return self._retry_with_timeout(call_detect)
    
    def generate_jsonld(self, metadata: Dict, example_jsonld: str) -> str:
        """Generate JSON-LD using OpenAI."""
        prompt = self._format_generation_prompt(metadata, example_jsonld)
        
        # Debug: Log prompt size
        prompt_size = len(prompt)
        if prompt_size > 15000:
            print(f"  Warning: Large prompt size ({prompt_size} characters), this may cause timeouts")
        
        def call_generate():
            response = self._call_api(prompt, operation="JSON-LD generation")
            return self._extract_json_from_response(response)
        
        return self._retry_with_timeout(call_generate)


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
    
    def _call_api(self, prompt: str, system_prompt: str = None, operation: str = "processing") -> str:
        """Make API call to Anthropic with timeout enforcement."""
        print(f"  Sending request to API for {operation} (this may take 1-6 minutes)...")
        
        def api_call():
            return self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt or "You are a helpful assistant that generates structured data.",
                messages=[{"role": "user", "content": prompt}],
                timeout=API_TIMEOUT_SECONDS
            )
        
        response = self._call_api_with_timeout(api_call)
        print(f"  Received response")
        if not response.content or not response.content[0].text:
            raise ValueError("Empty response from API")
        return response.content[0].text
    
    def detect_datasets(self, url: str, context: Dict) -> Dict:
        """Detect datasets using Anthropic by analyzing the URL directly."""
        prompt = self._format_detection_prompt(url, context)
        
        # Debug: Log prompt size
        prompt_size = len(prompt)
        if prompt_size > 20000:
            print(f"  Warning: Large prompt size ({prompt_size} characters), this may cause timeouts")
        
        def call_detect():
            response = self._call_api(prompt, operation="dataset detection")
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                return {"raw_response": response, "error": "Failed to parse JSON"}
        
        return self._retry_with_timeout(call_detect)
    
    def generate_jsonld(self, metadata: Dict, example_jsonld: str) -> str:
        """Generate JSON-LD using Anthropic."""
        prompt = self._format_generation_prompt(metadata, example_jsonld)
        
        # Debug: Log prompt size
        prompt_size = len(prompt)
        if prompt_size > 20000:
            print(f"  Warning: Large prompt size ({prompt_size} characters), this may cause timeouts")
        
        def call_generate():
            response = self._call_api(prompt, operation="JSON-LD generation")
            return self._extract_json_from_response(response)
        
        return self._retry_with_timeout(call_generate)


class GeminiClient(AIClient):
    """Google Gemini API client with URL Context Tool support."""
    
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model_name = model.replace("models/", "") if model.startswith("models/") else model
        
        # Try to use new API with URL Context Tool support
        if GEMINI_NEW_API:
            self.client = new_genai.Client(api_key=api_key)
            self.use_url_context = True
            print(f"Using Google Gemini API (new package with URL Context Tool)")
        else:
            # Fallback to deprecated package
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(self.model_name)
            self.use_url_context = False
            print(f"Using Google Gemini API (deprecated package - URL Context Tool not available)")
        
        print(f"Using model: {self.model_name}")
    
    def _call_api(self, prompt: str, system_prompt: str = None, operation: str = "processing", url: str = None) -> str:
        """Make API call to Gemini with timeout enforcement and quota error handling.
        
        If url is provided and using new API, will use URL Context Tool to fetch webpage content.
        """
        print(f"  Sending request to API for {operation} (this may take 1-6 minutes)...")
        
        # Combine system and user prompts if needed
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        
        def api_call():
            if self.use_url_context and url:
                # Use new API with URL Context Tool
                from google.genai.types import GenerateContentConfig
                url_context_tool = Tool(url_context=UrlContext())
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=full_prompt,
                    config=GenerateContentConfig(
                        tools=[url_context_tool],
                        temperature=0.3,
                        max_output_tokens=4096,
                    )
                )
                # Extract text from response
                if response.candidates and response.candidates[0].content.parts:
                    text_parts = [part.text for part in response.candidates[0].content.parts if hasattr(part, 'text')]
                    class Response:
                        def __init__(self, text):
                            self.text = text
                    return Response('\n'.join(text_parts))
                else:
                    raise ValueError("Empty response from API")
            else:
                # Use deprecated API (no URL Context Tool)
                response = self.model.generate_content(
                    full_prompt,
                    generation_config={
                        "temperature": 0.3,
                        "max_output_tokens": 4096,
                    }
                )
                return response
        
        # Retry up to 3 times for quota errors
        max_quota_retries = 3
        for quota_attempt in range(max_quota_retries):
            try:
                response = self._call_api_with_timeout(api_call)
                print(f"  Received response")
                if not response or not response.text:
                    raise ValueError("Empty response from API")
                return response.text
            except Exception as e:
                # Check if it's a quota error
                is_quota_error = False
                retry_delay = 30  # Default 30 seconds
                
                # Check for new API quota errors
                if self.use_url_context and new_genai_errors:
                    if isinstance(e, new_genai_errors.ClientError):
                        error_str = str(e)
                        if '429' in error_str or 'RESOURCE_EXHAUSTED' in error_str or 'quota' in error_str.lower():
                            is_quota_error = True
                            retry_match = re.search(r'retry in ([\d.]+)s', error_str, re.IGNORECASE)
                            if retry_match:
                                retry_delay = float(retry_match.group(1))
                                retry_delay = min(retry_delay + 5, 60)
                
                # Check for deprecated API quota errors
                if not is_quota_error and not self.use_url_context and google_exceptions:
                    if isinstance(e, google_exceptions.ResourceExhausted):
                        is_quota_error = True
                        error_str = str(e)
                        retry_match = re.search(r'retry in ([\d.]+)s', error_str, re.IGNORECASE)
                        if retry_match:
                            retry_delay = float(retry_match.group(1))
                            retry_delay = min(retry_delay + 5, 60)
                
                if is_quota_error:
                    error_str = str(e)
                    # Extract retry delay from error message if available
                    retry_match = re.search(r'retry in ([\d.]+)s', error_str, re.IGNORECASE)
                    if retry_match:
                        retry_delay = float(retry_match.group(1))
                        retry_delay = min(retry_delay + 5, 60)  # Add 5s buffer, max 60s
                    else:
                        retry_delay = 30  # Default 30 seconds
                    
                    if quota_attempt < max_quota_retries - 1:
                        print(f"  Quota limit reached. Waiting {retry_delay:.0f} seconds before retry ({quota_attempt + 1}/{max_quota_retries})...")
                        time.sleep(retry_delay)
                        continue
                    else:
                        print(f"  Quota limit reached after {max_quota_retries} attempts.")
                        print(f"  Please check your quota at: https://ai.dev/usage?tab=rate-limit")
                        raise Exception(f"Gemini API quota exceeded. Please wait and try again later, or check your quota limits.")
                else:
                    # Not a quota error, re-raise
                    raise
    
    def detect_datasets(self, url: str, context: Dict) -> Dict:
        """Detect datasets using Gemini by analyzing the URL directly.
        
        If using new API with URL Context Tool, Gemini will fetch and analyze the webpage.
        Otherwise, it will analyze the URL string only.
        """
        prompt = self._format_detection_prompt(url, context)
        
        # Debug: Log prompt size
        prompt_size = len(prompt)
        if prompt_size > 10000:
            print(f"  Warning: Large prompt size ({prompt_size} characters), this may cause timeouts")
        
        if self.use_url_context:
            print(f"  Using URL Context Tool - Gemini will fetch and analyze: {url}")
        
        def call_detect():
            # Pass URL to _call_api so it can use URL Context Tool if available
            response = self._call_api(prompt, operation="dataset detection", url=url)
            response_text = response.text if hasattr(response, 'text') else str(response)
            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                return {"raw_response": response_text, "error": "Failed to parse JSON"}
        
        return self._retry_with_timeout(call_detect)
    
    def generate_jsonld(self, metadata: Dict, example_jsonld: str) -> str:
        """Generate JSON-LD using Gemini."""
        prompt = self._format_generation_prompt(metadata, example_jsonld)
        
        # Debug: Log prompt size
        prompt_size = len(prompt)
        if prompt_size > 15000:
            print(f"  Warning: Large prompt size ({prompt_size} characters), this may cause timeouts")
        
        def call_generate():
            response = self._call_api(prompt, operation="JSON-LD generation")
            return self._extract_json_from_response(response)
        
        return self._retry_with_timeout(call_generate)


def fetch_webpage(url: str) -> Optional[str]:
    """Fetch webpage content."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=WEBPAGE_TIMEOUT)
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
        return html[:HTML_FALLBACK_LIMIT]  # Return first N chars if parsing fails


def load_example_jsonld() -> str:
    """Load an example JSON-LD file for reference."""
    example_path = DATA_DIR / "gpp" / "2d78c4242a108f70ea2c0604964dc095b34bfd7b.jsonld"
    if example_path.exists():
        with open(example_path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""


def read_csv(csv_path: str) -> List[Dict]:
    """Read the datasets CSV file."""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
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
    safe_name = safe_name.replace(' ', '_')[:FILENAME_MAX_LENGTH]
    
    # Use URL hash as fallback (always include hash for uniqueness)
    url_hash = hashlib.sha1(url.encode()).hexdigest()[:URL_HASH_LENGTH]
    
    # If safe_name is empty, use just the hash
    if not safe_name:
        filename = f"dataset_{url_hash}.jsonld"
    else:
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
    parser.add_argument('--ai-service', choices=['openai', 'anthropic', 'nrp', 'gemini'], default='gemini', help='AI service to use (default: gemini)')
    parser.add_argument('--api-key', help='API key (or set environment variable)')
    parser.add_argument('--model', help='Model name (optional)')
    parser.add_argument('--limit', type=int, help='Limit number of datasets to process')
    parser.add_argument('--test-url', help='Test with a single URL instead of CSV')
    
    args = parser.parse_args()
    
    # Initialize AI client
    env_var_name = f"{args.ai_service.upper()}_API_KEY"
    api_key = args.api_key or os.getenv(env_var_name) or os.getenv("NRP_API_KEY")
    
    # Debug: Check if API key was loaded (but don't print the actual key)
    if not api_key:
        print(f"Error: API key required.")
        print(f"  Looking for: {env_var_name} or NRP_API_KEY")
        # Check if .env file exists and has the variable
        env_file = PROJECT_ROOT / '.env'
        if env_file.exists():
            print(f"  Found .env file at: {env_file}")
            with open(env_file, 'r') as f:
                content = f.read()
                if env_var_name in content:
                    if f"{env_var_name}=your-" in content or f"{env_var_name}=your_" in content:
                        print(f"  Warning: .env file contains placeholder value. Please replace 'your-{args.ai_service.lower()}-api-key-here' with your actual API key.")
                    else:
                        print(f"  Note: {env_var_name} found in .env but not loaded. Check file format (no spaces around =).")
                else:
                    print(f"  Note: {env_var_name} not found in .env file.")
        else:
            print(f"  .env file not found at: {env_file}")
        print(f"  Set {env_var_name} environment variable or use --api-key")
        sys.exit(1)
    
    # Check if API key looks like a placeholder
    if api_key.startswith('your-') or 'your-' in api_key.lower():
        print(f"Warning: API key appears to be a placeholder. Please set a real API key.")
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
    elif args.ai_service == 'gemini':
        if not GEMINI_AVAILABLE:
            print("Error: google-generativeai package not installed. Run: pip install google-generativeai")
            sys.exit(1)
        # Default Gemini models: gemini-2.0-flash (fast), gemini-2.5-flash, gemini-2.5-pro (more capable)
        client = GeminiClient(api_key, args.model or "gemini-2.0-flash")
    
    output_dir = Path(args.output_dir)
    example_jsonld = load_example_jsonld()
    
    # Test mode with single URL
    if args.test_url:
        print(f"Testing with URL: {args.test_url}")
        print("  Sending URL to AI for analysis (AI will browse/analyze the webpage)...")
        context = {
            CSV_FIELDS['NAME']: 'Test Dataset',
            CSV_FIELDS['GROUP']: 'test',
            CSV_FIELDS['DESCRIPTION']: ''
        }
        result = client.detect_datasets(args.test_url, context)
        print("\n=== Detection Result ===")
        print(json.dumps(result, indent=2))
        return
    
    # Process CSV
    try:
        datasets = read_csv(args.csv)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        sys.exit(1)
    
    print(f"Found {len(datasets)} datasets in CSV")
    
    # Filter datasets that need JSON-LD
    to_process = [
        d for d in datasets 
        if d.get(CSV_FIELDS['HAS_JSONLD'], '').upper() in ('FALSE', '#ERROR!', '')
        and d.get(CSV_FIELDS['WEBPAGE_URL'], '').strip()
    ]
    
    if args.limit:
        to_process = to_process[:args.limit]
    
    print(f"Processing {len(to_process)} datasets that need JSON-LD")
    
    timed_out_urls = []
    
    for i, dataset in enumerate(to_process, 1):
        url = dataset.get(CSV_FIELDS['WEBPAGE_URL'], '').strip()
        name = dataset.get(CSV_FIELDS['NAME'], 'Unknown')
        
        if not url:
            print(f"[{i}/{len(to_process)}] Skipping {name}: No URL")
            continue
        
        print(f"\n[{i}/{len(to_process)}] Processing: {name}")
        print(f"  URL: {url}")
        
        # Detect datasets (AI will browse/analyze the URL directly)
        print("  Analyzing URL with AI (AI will browse/analyze the webpage)...")
        try:
            detection_result = client.detect_datasets(url, dataset)
            print(f"  Detection complete")
        except TimeoutError:
            print(f"  Error: Request timed out. Skipping this dataset.")
            timed_out_urls.append({'name': name, 'url': url, 'reason': 'timeout'})
            continue
        except Exception as e:
            # Check if it's a server error
            if any(code in str(e).lower() for code in SERVER_ERROR_CODES):
                print(f"  Error: API server error during detection. Skipping this dataset.")
                print(f"  Details: {e}")
                timed_out_urls.append({'name': name, 'url': url, 'reason': 'server_error'})
            else:
                print(f"  Error during detection: {e}")
                timed_out_urls.append({'name': name, 'url': url, 'reason': 'detection_error'})
            continue
        
        # Prepare metadata
        metadata = {
            'name': name,
            'url': url,
            'description': dataset.get(CSV_FIELDS['DESCRIPTION'], ''),
            'group': dataset.get(CSV_FIELDS['GROUP'], ''),
            'creator': dataset.get(CSV_FIELDS['CREATOR'], ''),
            'provider': dataset.get(CSV_FIELDS['PROVIDER'], ''),
            'publisher': dataset.get(CSV_FIELDS['PUBLISHER'], ''),
            'keywords': dataset.get(CSV_FIELDS['KEYWORDS'], ''),
            'spatial_coverage': (
                f"{dataset.get(CSV_FIELDS['BOX_LON_MIN'], '')},"
                f"{dataset.get(CSV_FIELDS['BOX_LAT_MIN'], '')},"
                f"{dataset.get(CSV_FIELDS['BOX_LON_MAX'], '')},"
                f"{dataset.get(CSV_FIELDS['BOX_LAT_MAX'], '')}"
                if dataset.get(CSV_FIELDS['BOX_LON_MIN']) else ''
            ),
            'extracted': detection_result
        }
        
        # Generate JSON-LD
        print("  Generating JSON-LD...")
        try:
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
        except TimeoutError:
            print(f"  Error: Request timed out. Skipping this dataset.")
            timed_out_urls.append({'name': name, 'url': url, 'reason': 'timeout'})
            continue
        except Exception as e:
            # Check if it's a server error
            if any(code in str(e).lower() for code in SERVER_ERROR_CODES):
                print(f"  Error: API server error. Skipping this dataset.")
                print(f"  Details: {e}")
                timed_out_urls.append({'name': name, 'url': url, 'reason': 'server_error'})
            else:
                print(f"  Error: {e}. Skipping this dataset.")
                timed_out_urls.append({'name': name, 'url': url, 'reason': 'other_error'})
            continue
    
    # Print summary of failed URLs
    if timed_out_urls:
        print(f"\n{'='*60}")
        print(f"Summary: {len(timed_out_urls)} dataset(s) failed:")
        print(f"{'='*60}")
        # Group by reason
        by_reason = {}
        for item in timed_out_urls:
            reason = item.get('reason', 'unknown')
            if reason not in by_reason:
                by_reason[reason] = []
            by_reason[reason].append(item)
        
        for reason, items in by_reason.items():
            reason_name = reason.replace('_', ' ').title()
            print(f"\n{reason_name} ({len(items)}):")
            for item in items:
                print(f"  - {item['name']}: {item['url']}")
        print(f"{'='*60}")
    else:
        print(f"\n{'='*60}")
        print("All datasets processed successfully!")
        print(f"{'='*60}")


if __name__ == '__main__':
    main()

