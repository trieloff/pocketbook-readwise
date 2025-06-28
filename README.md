# PocketBook to Readwise Sync

Automatically sync highlights from your PocketBook e-reader to Readwise.

## Setup

1. Install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. Get your Readwise access token from https://readwise.io/access_token

3. Add your token to `.credentials` file:
   ```
   READWISE_ACCESS_TOKEN=your-token-here
   ```

4. Connect your PocketBook to your computer. It should mount at `/Volumes/PB700K3/`

## Usage

Run the sync script:
```bash
./sync.sh
```

Or manually:
```bash
source venv/bin/activate
python pocketbook_sync.py
```

The script will:
- Find all HTML note files in `/Volumes/PB700K3/Notes/`
- Group files by book title (handling duplicates by using the newest)
- Parse highlights from the HTML files
- Upload new highlights to Readwise
- Cache processed highlights to avoid duplicates
- Track file changes to speed up repeated syncs

## Features

- **Duplicate Detection**: Tracks synced highlights by content hash
- **Smart File Handling**: Uses newest file when multiple versions exist
- **Incremental Sync**: Only processes changed files
- **Batch Upload**: Sends highlights in batches of 100
- **Error Handling**: Graceful handling of missing device or API errors
- **Color Tags**: Automatically converts PocketBook highlight colors to Readwise tags (e.g., magenta → .magenta, yellow → .yellow, cian → .cian)
- **Complete Metadata**: Preserves page numbers, highlight timestamps, and notes

## Cache

The script maintains a cache file (`.sync_cache.json`) that stores:
- Hashes of processed files
- IDs of synced highlights
- Sync timestamps

Delete this file to force a full re-sync.