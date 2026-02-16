# JSON-LD Generation Scripts

## Setup

### Getting the datasets.csv file

The script requires a `datasets.csv` file exported from the Google Sheet. To create it:

**Option 1: Download directly (Recommended)**
1. Open the Google Sheet: https://docs.google.com/spreadsheets/d/1pqZpMWqQFwUrleHXPbvXqXX59Xcj1Yrtqt2nJTh1reM/edit?gid=1162616600
2. Go to the "Datasets" tab
3. File → Download → Comma Separated Values (.csv)
4. Save as `datasets.csv` in the project root directory

**Option 2: Use the fetch script (recommended)**
```bash
# Download the spreadsheet as datasets.csv (sheet must be shared so "Anyone with the link" can view)
python scripts/fetch_spreadsheet.py
# Or save to a different file:
python scripts/fetch_spreadsheet.py path/to/datasets.csv
```

**Option 3: Use the sheet URL directly when generating**
```bash
# Use the Google Sheets export URL as the CSV source (no local file needed)
python scripts/generate_jsonld.py --csv "https://docs.google.com/spreadsheets/d/1pqZpMWqQFwUrleHXPbvXqXX59Xcj1Yrtqt2nJTh1reM/export?format=csv&gid=1162616600" --next
```

**Note**: The `datasets.csv` file is gitignored and will not be committed to the repository.

1. Activate the virtual environment (if using one):
   ```bash
   # Windows
   venv\Scripts\activate
   
   # Linux/Mac
   source venv/bin/activate
   ```

2. Install required packages:
   ```bash
   pip install -r scripts/requirements.txt
   ```

   Or install specific AI service:
   ```bash
   # For NRP or OpenAI
   pip install openai requests beautifulsoup4 python-dotenv
   # OR for Anthropic
   pip install anthropic requests beautifulsoup4 python-dotenv
   # OR for Gemini
   pip install google-generativeai requests beautifulsoup4 python-dotenv
   ```

3. Set up your API key:
   
   **Use .env file (Recommended)**
   ```bash
   # Copy the example file
   cp .env.example .env
   
   # Edit .env and add your API key
   # See .env.example for all available options and NRP model information
   ```
   
   **Alternative: Set environment variable directly**
   ```bash
   # Linux/Mac
   export OPENAI_API_KEY="your-key-here"
   export NRP_API_KEY="your-key-here"
   export GEMINI_API_KEY="your-key-here"
   
   # Windows (PowerShell)
   $env:OPENAI_API_KEY="your-key-here"
   $env:NRP_API_KEY="your-key-here"
   $env:GEMINI_API_KEY="your-key-here"
   
   # Windows (CMD)
   set OPENAI_API_KEY=your-key-here
   set NRP_API_KEY=your-key-here
   set GEMINI_API_KEY=your-key-here
   ```
   
   **For NRP**: Get your API key from https://nrp.ai/documentation/userdocs/ai/llm-managed/
   
   **For OpenAI/ChatGPT**: Get your API key from https://platform.openai.com/api-keys
   
   **For Gemini**: Get your API key from https://aistudio.google.com/apikey (free tier available with .edu email)

## Usage

### Test with a single URL
```bash
# Using Gemini (default, no --ai-service needed)
python scripts/generate_jsonld.py --test-url "http://hydro.iis.u-tokyo.ac.jp/~yamadai/MERIT_DEM/"

# Or use OpenAI/ChatGPT, NRP, or Anthropic if you have their API keys
python scripts/generate_jsonld.py --ai-service openai --test-url "http://hydro.iis.u-tokyo.ac.jp/~yamadai/MERIT_DEM/"
python scripts/generate_jsonld.py --ai-service nrp --test-url "http://hydro.iis.u-tokyo.ac.jp/~yamadai/MERIT_DEM/"
python scripts/generate_jsonld.py --ai-service gemini --test-url "http://hydro.iis.u-tokyo.ac.jp/~yamadai/MERIT_DEM/"
```

### Process datasets from CSV
```bash
# Process all datasets that need JSON-LD (using Gemini by default)
python scripts/generate_jsonld.py --csv datasets.csv

# Process only first 5 datasets (for testing)
python scripts/generate_jsonld.py --csv datasets.csv --limit 5

# Alternative: Use OpenAI, Anthropic, or Gemini if you have their API keys
python scripts/generate_jsonld.py --ai-service openai --csv datasets.csv
python scripts/generate_jsonld.py --ai-service anthropic --csv datasets.csv
python scripts/generate_jsonld.py --ai-service gemini --csv datasets.csv
```

### Options
- `--csv`: Path to CSV file (default: `datasets.csv`)
- `--output-dir`: Output directory for JSON-LD files (default: `data/objects/summoned/generated`)
- `--ai-service`: Choose `gemini` (default), `nrp`, `openai`, or `anthropic` (optional - defaults to `gemini`)
- `--api-key`: API key (or use environment variable)
- `--model`: Model name (optional, uses defaults)
  - Gemini default: `gemini-2.0-flash` (other options: `gemini-2.5-flash`, `gemini-2.5-pro`)
  - NRP default: `qwen3` (other options: `llama3-sdsc`, `gpt-oss`, `gorilla`, `olmo`, `gemma3`, `kimi`, etc.)
  - OpenAI default: `gpt-4o`
  - Anthropic default: `claude-3-5-sonnet-20241022`
- `--limit`: Limit number of datasets to process
- `--test-url`: Test with a single URL instead of CSV

## Output

Generated JSON-LD files are saved to the output directory with filenames like:
`DatasetName_hash.jsonld`

## Workflow

1. Script reads the CSV file
2. Filters datasets where `hasJSONLD?` is `FALSE`, `#ERROR!`, or empty
3. For each dataset:
   - **Gemini (default)**: Passes URL directly to AI, which uses URL Context Tool to browse/analyze the webpage
   - **Other AI services (OpenAI, Anthropic, NRP)**: Fetches HTML, extracts text content using BeautifulSoup, then sends to AI
   - Uses AI to detect datasets and extract metadata
   - Generates JSON-LD using the extracted metadata
   - Saves the JSON-LD file

**Note**: Gemini is the default because it can browse URLs directly. Other services require HTML fetching and text extraction.

