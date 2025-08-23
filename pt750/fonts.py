import os
import requests
import logging
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional, List

logger = logging.getLogger(__name__)

# Google Fonts API - kostenlos und umfangreich
GOOGLE_FONTS_API = "https://fonts.google.com/download"
# Entfernt - nur manueller URL-Download
POPULAR_FONTS = []

class FontManager:
    def __init__(self, font_cache_dir: str = "/app/custom_fonts"):
        self.cache_dir = Path(font_cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    def is_font_cached(self, font_name: str) -> bool:
        """Check if font is already downloaded."""
        font_files = list(self.cache_dir.glob(f"{font_name}*.ttf"))
        font_files.extend(list(self.cache_dir.glob(f"{font_name}*.otf")))
        return len(font_files) > 0
    
    def get_cached_fonts(self) -> List[str]:
        """Get list of all cached font names."""
        fonts = set()
        for ttf_file in self.cache_dir.glob("*.ttf"):
            # Extract base font name (remove variants like -Bold, -Italic)
            font_name = ttf_file.stem.split('-')[0]
            fonts.add(font_name)
        for otf_file in self.cache_dir.glob("*.otf"):
            # Extract base font name (remove variants like -Bold, -Italic)
            font_name = otf_file.stem.split('-')[0]
            fonts.add(font_name)
        return sorted(fonts)
    
    def download_google_font(self, font_name: str) -> bool:
        """Download a font from Google Fonts using multiple fallback methods."""
        try:
            logger.info(f"Downloading font: {font_name}")
            
            # Method 1: Try direct Google Fonts ZIP download
            success = self._try_google_fonts_zip(font_name)
            if success:
                return True
                
            # Method 2: Try alternative Google Fonts API
            success = self._try_google_fonts_api(font_name)
            if success:
                return True
                
            # Method 3: Try GitHub Google Fonts mirror
            success = self._try_github_fonts_mirror(font_name)
            if success:
                return True
                
            logger.error(f"All download methods failed for font: {font_name}")
            return False
            
        except Exception as e:
            logger.error(f"Failed to download font {font_name}: {e}")
            return False
    
    def _try_google_fonts_zip(self, font_name: str) -> bool:
        """Try downloading from Google Fonts direct ZIP."""
        try:
            url = f"https://fonts.google.com/download?family={font_name.replace(' ', '+')}"
            response = requests.get(url, timeout=30, allow_redirects=True)
            
            # Check if we got a ZIP file
            if response.headers.get('content-type', '').startswith('application/zip') or \
               len(response.content) > 1000:  # ZIP files are usually larger
                
                return self._extract_font_zip(response.content, font_name)
            return False
            
        except Exception as e:
            logger.warning(f"Google Fonts ZIP download failed for {font_name}: {e}")
            return False
    
    def _try_google_fonts_api(self, font_name: str) -> bool:
        """Try downloading via Google Fonts CSS API to get direct TTF URLs."""
        try:
            # Use Google Fonts CSS API to get font URLs
            css_url = f"https://fonts.googleapis.com/css2?family={font_name.replace(' ', '+')}:wght@400&display=swap"
            
            # Use a real browser User-Agent to get TTF URLs instead of WOFF2
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(css_url, headers=headers, timeout=15)
            if response.status_code == 200:
                css_content = response.text
                
                # Extract TTF URLs from CSS
                import re
                ttf_urls = re.findall(r'url\((https://fonts\.gstatic\.com/[^)]+\.ttf)\)', css_content)
                
                if ttf_urls:
                    # Download the first TTF found
                    ttf_url = ttf_urls[0]
                    ttf_response = requests.get(ttf_url, timeout=15)
                    
                    if ttf_response.status_code == 200:
                        ttf_path = self.cache_dir / f"{font_name}-Regular.ttf"
                        with open(ttf_path, 'wb') as f:
                            f.write(ttf_response.content)
                        logger.info(f"Downloaded {font_name} from Google Fonts CSS API")
                        return True
                        
            return False
            
        except Exception as e:
            logger.warning(f"Google Fonts CSS API download failed for {font_name}: {e}")
            return False
    
    def _try_github_fonts_mirror(self, font_name: str) -> bool:
        """Try downloading from GitHub Google Fonts mirror."""
        try:
            font_slug = font_name.lower().replace(' ', '')
            base_url = f"https://github.com/google/fonts/raw/main/ofl/{font_slug}"
            
            # Try to download the regular variant
            variants = ['Regular', '400', 'normal']
            for variant in variants:
                url = f"{base_url}/{font_name.replace(' ', '')}-{variant}.ttf"
                try:
                    response = requests.get(url, timeout=15)
                    if response.status_code == 200:
                        ttf_path = self.cache_dir / f"{font_name}-{variant}.ttf"
                        with open(ttf_path, 'wb') as f:
                            f.write(response.content)
                        logger.info(f"Downloaded {font_name} from GitHub mirror")
                        return True
                except:
                    continue
                    
            return False
            
        except Exception as e:
            logger.warning(f"GitHub fonts mirror download failed for {font_name}: {e}")
            return False
    
    def _extract_font_zip(self, zip_content: bytes, font_name: str) -> bool:
        """Extract TTF files from ZIP content."""
        try:
            import zipfile
            import io
            
            with zipfile.ZipFile(io.BytesIO(zip_content)) as zip_ref:
                extracted_files = 0
                for file_info in zip_ref.infolist():
                    if file_info.filename.endswith('.ttf'):
                        # Extract with clean filename
                        clean_name = Path(file_info.filename).name
                        extract_path = self.cache_dir / clean_name
                        
                        with zip_ref.open(file_info) as source:
                            with open(extract_path, 'wb') as target:
                                target.write(source.read())
                        extracted_files += 1
                
                if extracted_files > 0:
                    logger.info(f"Extracted {extracted_files} font files for {font_name}")
                    return True
                    
            return False
            
        except Exception as e:
            logger.error(f"ZIP extraction failed for {font_name}: {e}")
            return False
    
    def download_font_from_url(self, url: str, font_name: Optional[str] = None) -> bool:
        """Download a font from URL (supports TTF and ZIP with better error handling)."""
        try:
            if not font_name:
                # Extract name from URL
                font_name = Path(urlparse(url).path).stem
            
            # Better headers to avoid bot detection
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            }
            
            logger.info(f"Downloading from URL: {url}")
            response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
            response.raise_for_status()
            
            logger.info(f"Response: {response.status_code}, Content-Type: {response.headers.get('content-type')}, Size: {len(response.content)} bytes")
            
            content_type = response.headers.get('content-type', '').lower()
            
            # Enhanced file type detection
            is_zip = (
                'zip' in content_type or 
                'application/x-zip' in content_type or 
                url.lower().endswith('.zip') or
                response.content[:2] == b'PK'  # ZIP magic bytes
            )
            
            is_ttf = (
                'font' in content_type or 
                'truetype' in content_type or 
                url.lower().endswith('.ttf') or
                url.lower().endswith('.otf') or
                response.content[:4] in [b'\x00\x01\x00\x00', b'OTTO']  # TTF/OTF magic bytes
            )
            
            # Handle ZIP files
            if is_zip:
                logger.info(f"Processing ZIP file for {font_name}")
                return self._extract_font_zip(response.content, font_name)
            
            # Handle TTF/OTF files
            elif is_ttf:
                extension = '.ttf' if response.content[:4] == b'\x00\x01\x00\x00' else '.otf'
                ttf_path = self.cache_dir / f"{font_name}{extension}"
                with open(ttf_path, 'wb') as f:
                    f.write(response.content)
                logger.info(f"Downloaded {extension.upper()} font from URL: {font_name}")
                return True
            
            # Unknown format - try to extract useful info
            else:
                logger.error(f"Unknown file format from URL: {url}")
                logger.error(f"Content-Type: {content_type}")
                logger.error(f"First 10 bytes: {response.content[:10]}")
                
                # Last resort: if it looks like font data, save as TTF
                if len(response.content) > 5000:  # Font files are usually large
                    ttf_path = self.cache_dir / f"{font_name}.ttf"
                    with open(ttf_path, 'wb') as f:
                        f.write(response.content)
                    logger.warning(f"Saved unknown format as TTF: {font_name}")
                    return True
                
                return False
            
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP error downloading from {url}: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to download font from URL {url}: {e}")
            return False
    
    def upload_font_file(self, content: bytes, filename: str, font_name: Optional[str] = None) -> bool:
        """Upload a font file directly from bytes content."""
        try:
            if not font_name:
                font_name = Path(filename).stem
            
            filename_lower = filename.lower()
            
            # Handle ZIP files
            if filename_lower.endswith('.zip'):
                logger.info(f"Processing uploaded ZIP file: {filename}")
                return self._extract_font_zip(content, font_name)
            
            # Handle TTF/OTF files
            elif filename_lower.endswith(('.ttf', '.otf')):
                extension = '.ttf' if filename_lower.endswith('.ttf') else '.otf'
                target_path = self.cache_dir / f"{font_name}{extension}"
                
                with open(target_path, 'wb') as f:
                    f.write(content)
                
                logger.info(f"Uploaded {extension.upper()} font: {font_name}")
                return True
            
            else:
                logger.error(f"Unsupported file type: {filename}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to upload font file {filename}: {e}")
            return False
    
    def remove_font(self, font_name: str) -> bool:
        """Remove a cached font."""
        try:
            removed = False
            for ttf_file in self.cache_dir.glob(f"{font_name}*.ttf"):
                ttf_file.unlink()
                removed = True
            for otf_file in self.cache_dir.glob(f"{font_name}*.otf"):
                otf_file.unlink()
                removed = True
            
            if removed:
                logger.info(f"Removed font: {font_name}")
            return removed
            
        except Exception as e:
            logger.error(f"Failed to remove font {font_name}: {e}")
            return False
    
    def get_font_suggestions(self) -> List[str]:
        """Get list of popular fonts for download."""
        return POPULAR_FONTS

# Global instance
font_manager = FontManager()