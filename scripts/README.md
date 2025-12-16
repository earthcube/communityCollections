# JSON-LD Generation Scripts

## Setup

### Getting the datasets.csv file

The script requires a `datasets.csv` file exported from the Google Sheet. To create it:

**Option 1: Download directly (Recommended)**
1. Open the Google Sheet: https://docs.google.com/spreadsheets/d/1pqZpMWqQFwUrleHXPbvXqXX59Xcj1Yrtqt2nJTh1reM/edit?gid=1162616600
2. Go to the "Datasets" tab
3. File → Download → Comma Separated Values (.csv)
4. Save as `datasets.csv` in the project root directory

**Option 2: Use Python to download**
```bash
# Download the CSV export directly
python -c "import urllib.request; urllib.request.urlretrieve('https://docs.google.com/spreadsheets/d/1pqZpMWqQFwUrleHXPbvXqXX59Xcj1Yrtqt2nJTh1reM/export?format=csv&gid=1162616600', 'datasets.csv'); print('Downloaded datasets.csv')"
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
   pip install openai requests beautifulsoup4 python-dotenv
   # OR
   pip install anthropic requests beautifulsoup4 python-dotenv
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
   export NRP_API_KEY="your-key-here"
   
   # Windows (PowerShell)
   $env:NRP_API_KEY="your-key-here"
   
   # Windows (CMD)
   set NRP_API_KEY=your-key-here
   ```
   
   **For NRP**: Get your API key from https://nrp.ai/documentation/userdocs/ai/llm-managed/

## Usage

### Test with a single URL
```bash
# Using NRP (default, no --ai-service needed)
python scripts/generate_jsonld.py --test-url "http://hydro.iis.u-tokyo.ac.jp/~yamadai/MERIT_DEM/"

# Or use OpenAI/Anthropic if you have their API keys
python scripts/generate_jsonld.py --ai-service openai --test-url "http://hydro.iis.u-tokyo.ac.jp/~yamadai/MERIT_DEM/"
```

### Process datasets from CSV
```bash
# Process all datasets that need JSON-LD (using NRP by default)
python scripts/generate_jsonld.py --csv datasets.csv

# Process only first 5 datasets (for testing)
python scripts/generate_jsonld.py --csv datasets.csv --limit 5

# Alternative: Use OpenAI or Anthropic if you have their API keys
python scripts/generate_jsonld.py --ai-service openai --csv datasets.csv
python scripts/generate_jsonld.py --ai-service anthropic --csv datasets.csv
```

### Options
- `--csv`: Path to CSV file (default: `datasets.csv`)
- `--output-dir`: Output directory for JSON-LD files (default: `data/objects/summoned/generated`)
- `--ai-service`: Choose `nrp` (default), `openai`, or `anthropic` (optional - defaults to `nrp`)
- `--api-key`: API key (or use environment variable)
- `--model`: Model name (optional, uses defaults)
  - NRP default: `qwen3` (other options: `llama3-sdsc`, `gpt-oss`, `gorilla`, `olmo`, `gemma3`, `kimi`, etc.)
  - OpenAI default: `gpt-4`
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
   - Fetches the webpage
   - Uses AI to detect datasets and extract metadata
   - Generates JSON-LD using the extracted metadata
   - Saves the JSON-LD file

