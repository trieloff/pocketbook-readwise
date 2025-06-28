#!/usr/bin/env python3
import os
import json
import hashlib
import re
import requests
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
from typing import List, Dict, Tuple, Optional


class PocketBookReadwiseSync:
    def __init__(self, readwise_token: str, cache_file: str = ".sync_cache.json"):
        self.readwise_token = readwise_token
        self.cache_file = cache_file
        self.cache = self._load_cache()
        self.pocketbook_path = Path("/Volumes/PB700K3/Notes")
        self.readwise_url = "https://readwise.io/api/v2/highlights/"
        
    def _load_cache(self) -> Dict:
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        return {"synced_highlights": {}, "file_hashes": {}}
    
    def _save_cache(self):
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f, indent=2)
    
    def _get_file_hash(self, filepath: Path) -> str:
        with open(filepath, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    
    def _get_latest_book_file(self, book_files: List[Path]) -> Path:
        return max(book_files, key=lambda f: f.stat().st_mtime)
    
    def _group_files_by_book(self) -> Dict[str, List[Path]]:
        if not self.pocketbook_path.exists():
            raise FileNotFoundError(f"PocketBook not mounted at {self.pocketbook_path}")
        
        book_groups = {}
        for html_file in self.pocketbook_path.glob("*.html"):
            # Skip macOS metadata files
            if html_file.name.startswith('._'):
                continue
                
            # Try to parse the file to get the title
            try:
                # Try different encodings
                encodings = ['utf-8', 'cp1252', 'iso-8859-1', 'utf-16']
                content = None
                for encoding in encodings:
                    try:
                        content = html_file.read_text(encoding=encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                
                if content is None:
                    print(f"Warning: Could not read {html_file} with any encoding, skipping")
                    continue
                    
                soup = BeautifulSoup(content, 'lxml')
                
                title_elem = soup.find('h1') or soup.find('title')
                if title_elem:
                    book_title = title_elem.get_text(strip=True)
                    # Remove date prefix if present
                    if ' - ' in book_title:
                        book_title = book_title.split(' - ', 1)[1]
                else:
                    book_title = html_file.stem
                
                if book_title not in book_groups:
                    book_groups[book_title] = []
                book_groups[book_title].append(html_file)
            except Exception as e:
                print(f"Error processing {html_file}: {e}")
                continue
        
        return book_groups
    
    def _parse_highlights(self, filepath: Path) -> Tuple[str, str, List[Dict]]:
        # Try different encodings
        encodings = ['utf-8', 'cp1252', 'iso-8859-1', 'utf-16']
        content = None
        for encoding in encodings:
            try:
                content = filepath.read_text(encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        
        if content is None:
            print(f"Warning: Could not read {filepath} with any encoding")
            return filepath.stem, "Unknown Author", []
        
        soup = BeautifulSoup(content, 'lxml')
        
        # Extract title and timestamp from h1, removing the date prefix
        highlighted_at = None
        title_elem = soup.find('h1')
        if title_elem:
            title_text = title_elem.get_text(strip=True)
            # Extract date and title from format: "2025-06-28 16:57:41 - Title"
            if ' - ' in title_text:
                date_part, title = title_text.split(' - ', 1)
                try:
                    # Parse the date and convert to ISO format
                    dt = datetime.strptime(date_part, "%Y-%m-%d %H:%M:%S")
                    highlighted_at = dt.isoformat() + "+00:00"
                except ValueError:
                    pass
            else:
                title = title_text
        else:
            title = filepath.stem
        
        # Find author in the second bookmark div
        author = "Unknown Author"
        bookmark_divs = soup.find_all('div', class_='bookmark')
        if len(bookmark_divs) >= 2:
            author_text = bookmark_divs[1].find('span')
            if author_text:
                author = author_text.get_text(strip=True)
        
        highlights = []
        
        # Find all bookmark divs that contain highlights (not the title/author ones)
        for div in soup.find_all('div', class_='bookmark'):
            if div.get('id'):  # Only process divs with IDs (actual highlights)
                # Get highlight color
                color_tag = None
                for css_class in div.get('class', []):
                    if css_class.startswith('bm-color-') and css_class != 'bm-color-none':
                        # Extract the color name and format as a tag
                        color_name = css_class.replace('bm-color-', '')
                        color_tag = f".{color_name}"
                        break
                
                # Get page number as integer
                location = None
                page_elem = div.find('p', class_='bm-page')
                if page_elem:
                    page_text = page_elem.get_text(strip=True)
                    try:
                        # Extract just the number from "page # 123" or similar formats
                        page_match = re.search(r'\d+', page_text)
                        if page_match:
                            location = int(page_match.group())
                    except (ValueError, AttributeError):
                        pass
                
                # Get highlight text
                text_elem = div.find('div', class_='bm-text')
                if text_elem:
                    text = text_elem.get_text(strip=True)
                    if text and len(text) > 10:
                        highlight_id = hashlib.md5(f"{title}{text}".encode()).hexdigest()
                        
                        # Check for note
                        note_elem = div.find('div', class_='bm-note')
                        note = note_elem.get_text(strip=True) if note_elem else None
                        
                        # Add color tag to note if present
                        if color_tag:
                            if note:
                                note = f"{note} {color_tag}"
                            else:
                                note = color_tag
                        
                        highlights.append({
                            "id": highlight_id,
                            "text": text,
                            "location": location,
                            "note": note,
                            "highlighted_at": highlighted_at
                        })
        
        return title, author, highlights
    
    def _create_readwise_payload(self, title: str, author: str, highlight: Dict) -> Dict:
        payload = {
            "text": highlight["text"],
            "title": title,
            "author": author,
            "source_type": "book",
            "category": "books"
        }
        
        # Add highlighted_at timestamp if available, otherwise use current time
        if highlight.get("highlighted_at"):
            payload["highlighted_at"] = highlight["highlighted_at"]
        else:
            payload["highlighted_at"] = datetime.now().isoformat() + "+00:00"
        
        # Add location as integer with location_type
        if highlight.get("location") is not None:
            payload["location"] = highlight["location"]
            payload["location_type"] = "page"
        
        if highlight.get("note"):
            payload["note"] = highlight["note"]
        
        return payload
    
    def _send_to_readwise(self, highlights_data: List[Dict]) -> bool:
        headers = {
            "Authorization": f"Token {self.readwise_token}",
            "Content-Type": "application/json"
        }
        
        payload = {"highlights": highlights_data}
        
        try:
            response = requests.post(self.readwise_url, json=payload, headers=headers)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error sending to Readwise: {e}")
            return False
    
    def sync(self):
        try:
            book_groups = self._group_files_by_book()
            print(f"Found {len(book_groups)} unique books")
            
            total_new_highlights = 0
            
            for book_title, files in book_groups.items():
                latest_file = self._get_latest_book_file(files)
                file_hash = self._get_file_hash(latest_file)
                
                cached_hash = self.cache["file_hashes"].get(str(latest_file))
                if cached_hash == file_hash:
                    print(f"Skipping '{book_title}' - no changes")
                    continue
                
                print(f"\nProcessing '{book_title}'...")
                title, author, highlights = self._parse_highlights(latest_file)
                
                new_highlights = []
                for highlight in highlights:
                    if highlight["id"] not in self.cache["synced_highlights"]:
                        payload = self._create_readwise_payload(title, author, highlight)
                        new_highlights.append(payload)
                
                if new_highlights:
                    print(f"  Found {len(new_highlights)} new highlights")
                    
                    batch_size = 100
                    for i in range(0, len(new_highlights), batch_size):
                        batch = new_highlights[i:i + batch_size]
                        if self._send_to_readwise(batch):
                            for j, h in enumerate(highlights[i:i + len(batch)]):
                                self.cache["synced_highlights"][h["id"]] = {
                                    "synced_at": datetime.now().isoformat(),
                                    "book": title
                                }
                            print(f"  Synced batch of {len(batch)} highlights")
                        else:
                            print(f"  Failed to sync batch starting at highlight {i}")
                    
                    total_new_highlights += len(new_highlights)
                else:
                    print(f"  No new highlights to sync")
                
                self.cache["file_hashes"][str(latest_file)] = file_hash
                self._save_cache()
            
            print(f"\nSync complete! Uploaded {total_new_highlights} new highlights.")
            
        except FileNotFoundError as e:
            print(f"Error: {e}")
            print("Please ensure your PocketBook is connected and mounted at /Volumes/PB700K3/")
        except Exception as e:
            print(f"Unexpected error: {e}")


def main():
    # Try to get token from environment variable first
    readwise_token = os.environ.get("READWISE_TOKEN")
    
    # If not in env, try to read from .credentials file
    if not readwise_token:
        credentials_path = Path(__file__).parent / ".credentials"
        if credentials_path.exists():
            with open(credentials_path, 'r') as f:
                for line in f:
                    if line.startswith("READWISE_ACCESS_TOKEN="):
                        readwise_token = line.split("=", 1)[1].strip()
                        break
    
    if not readwise_token:
        print("Error: READWISE_TOKEN not found")
        print("Please either:")
        print("1. Set environment variable: export READWISE_TOKEN='your-token-here'")
        print("2. Add to .credentials file: READWISE_ACCESS_TOKEN=your-token-here")
        print("Get your token from: https://readwise.io/access_token")
        return
    
    syncer = PocketBookReadwiseSync(readwise_token)
    syncer.sync()


if __name__ == "__main__":
    main()