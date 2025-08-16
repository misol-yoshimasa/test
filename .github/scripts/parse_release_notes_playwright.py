#!/usr/bin/env python3
"""
Parse Netskope Release Notes using Playwright
Enhanced version with better accordion handling and structure parsing
"""

import json
import sys
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Optional
from urllib.parse import urlparse
import re

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Feature:
    """Represents a single feature in the release notes"""
    title: str
    description: str
    category: str
    
    def to_markdown(self) -> str:
        """Convert to markdown format"""
        return f"## {self.title}\n\n{self.description}\n\n*Category: {self.category}*"


@dataclass
class ReleaseNotes:
    """Container for all release notes"""
    version: str
    features: List[Feature] = field(default_factory=list)
    
    def to_json(self) -> str:
        """Export release notes as JSON"""
        data = {
            "version": self.version,
            "features": [
                {
                    "category": f.category,
                    "title": f.title,
                    "description": f.description
                }
                for f in self.features
            ]
        }
        return json.dumps(data, ensure_ascii=False, indent=2)


class ReleaseNotesParser:
    """Parser for Netskope release notes using Playwright"""
    
    def __init__(self, url: str):
        self.url = url
    
    def fetch_with_playwright(self) -> str:
        """Fetch the page using Playwright and expand all content"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            logger.info(f"Fetching page with Playwright: {self.url}")
            page.goto(self.url, wait_until='networkidle')
            
            # Wait for content to load
            page.wait_for_timeout(3000)
            
            # Expand all content
            self.expand_all_content(page)
            
            # Get the HTML content
            html_content = page.content()
            browser.close()
            
            return html_content
    
    def expand_all_content(self, page):
        """Expand all collapsible content on the page"""
        try:
            # Click on "What's New" tab if present
            try:
                whats_new_tab = page.query_selector('text="What\'s New"')
                if whats_new_tab:
                    whats_new_tab.click()
                    page.wait_for_timeout(1000)
                    logger.info("Clicked on What's New tab")
            except:
                pass
            
            # Expand all accordion items
            # Look for various types of expandable elements
            expandable_selectors = [
                'button[aria-expanded="false"]',
                '.accordion-toggle[aria-expanded="false"]',
                '.collapsible:not(.active)',
                '[data-toggle="collapse"]:not(.collapsed)',
                '.expandable:not(.expanded)'
            ]
            
            for selector in expandable_selectors:
                elements = page.query_selector_all(selector)
                for element in elements:
                    try:
                        element.click()
                        page.wait_for_timeout(100)
                    except:
                        continue
            
            # Final wait for all content to expand
            page.wait_for_timeout(2000)
            logger.info("Expanded all collapsible content")
            
        except Exception as e:
            logger.debug(f"Error expanding content: {e}")
    
    def parse_html(self, html_content: str) -> ReleaseNotes:
        """Parse HTML content and extract release notes"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract version from URL or page
        version = self.extract_version(soup)
        
        # Initialize release notes
        release_notes = ReleaseNotes(version=version)
        
        # Parse features using improved logic
        features = self.parse_features(soup)
        
        # Deduplicate features
        seen = set()
        for feature in features:
            key = (feature.title, feature.category)
            if key not in seen:
                seen.add(key)
                release_notes.features.append(feature)
        
        return release_notes
    
    def extract_version(self, soup: BeautifulSoup) -> str:
        """Extract version number from page"""
        # Try to extract from URL
        if 'release-' in self.url:
            match = re.search(r'release-(\d+-\d+-\d+)', self.url)
            if match:
                return match.group(1).replace('-', '.')
        
        # Try to extract from page title or heading
        title = soup.find('title')
        if title:
            match = re.search(r'(\d+\.\d+\.\d+)', title.text)
            if match:
                return match.group(1)
        
        h1 = soup.find('h1')
        if h1:
            match = re.search(r'(\d+\.\d+\.\d+)', h1.text)
            if match:
                return match.group(1)
        
        return 'Unknown'
    
    def parse_features(self, soup: BeautifulSoup) -> List[Feature]:
        """Parse features with improved structure recognition"""
        features = []
        current_category = "General"
        
        # Find main content area
        main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content') or soup
        
        # Get all headings
        headings = main_content.find_all(['h2', 'h3', 'h4', 'h5', 'h6'])
        
        for i, heading in enumerate(headings):
            text = heading.get_text(strip=True)
            
            # Skip empty or too short headings
            if not text or len(text) < 3:
                continue
            
            # Skip navigation or meta headings
            if any(skip in text.lower() for skip in ['table of contents', 'navigation', 'menu', 'search']):
                continue
            
            # H2 and H3 at top level are usually categories
            if heading.name in ['h2', 'h3']:
                # Check if this is a category or a feature title
                # Look ahead to see if there's another heading immediately after
                next_heading = None
                if i + 1 < len(headings):
                    next_heading = headings[i + 1]
                
                # If the next heading is the same level or lower, this is likely a category
                if next_heading and next_heading.name in ['h3', 'h4', 'h5', 'h6']:
                    # Check if they are close together (category -> title pattern)
                    elements_between = self.count_elements_between(heading, next_heading)
                    
                    if elements_between < 3:  # Close together, likely category-title pair
                        current_category = text
                        logger.debug(f"Found category: {current_category}")
                        continue
                
                # This heading might be a feature title
                description = self.get_feature_description(heading)
                if description:
                    feature = Feature(
                        title=text,
                        description=description,
                        category=current_category
                    )
                    features.append(feature)
                    logger.debug(f"Found feature: {text}")
                else:
                    # Might be a category if no description
                    current_category = text
                    logger.debug(f"Set as category (no description): {current_category}")
            
            # H4, H5, H6 are usually feature titles
            elif heading.name in ['h4', 'h5', 'h6']:
                description = self.get_feature_description(heading)
                if description:
                    feature = Feature(
                        title=text,
                        description=description,
                        category=current_category
                    )
                    features.append(feature)
                    logger.debug(f"Found feature: {text}")
        
        return features
    
    def count_elements_between(self, elem1, elem2) -> int:
        """Count significant elements between two elements"""
        count = 0
        current = elem1.find_next_sibling()
        
        while current and current != elem2:
            if current.name and current.name not in ['br', 'hr']:
                # Check if element has substantial content
                text = current.get_text(strip=True)
                if text and len(text) > 10:
                    count += 1
            current = current.find_next_sibling()
        
        return count
    
    def get_feature_description(self, heading) -> str:
        """Get the description following a feature heading"""
        description_parts = []
        current = heading.find_next_sibling()
        
        while current:
            # Stop at next heading
            if current.name and current.name in ['h2', 'h3', 'h4', 'h5', 'h6']:
                break
            
            # Process the element
            if current.name:
                content = self.process_element(current)
                if content and len(content) > 5:
                    description_parts.append(content)
            
            current = current.find_next_sibling()
            
            # Stop if we have enough content
            if len('\n'.join(description_parts)) > 1500:
                break
        
        return '\n\n'.join(description_parts).strip()
    
    def process_element(self, element) -> str:
        """Process an element and convert to markdown"""
        if not element.name:
            return ""
        
        # Handle lists
        if element.name == 'ul':
            items = []
            for li in element.find_all('li', recursive=False):
                li_content = self.convert_to_markdown(li)
                if li_content:
                    items.append(f"- {li_content}")
            return '\n'.join(items)
        
        elif element.name == 'ol':
            items = []
            for i, li in enumerate(element.find_all('li', recursive=False), 1):
                li_content = self.convert_to_markdown(li)
                if li_content:
                    items.append(f"{i}. {li_content}")
            return '\n'.join(items)
        
        # Handle paragraphs and divs
        elif element.name in ['p', 'div', 'section', 'article']:
            content = self.convert_to_markdown(element)
            return content if content else ""
        
        # Handle blockquotes
        elif element.name == 'blockquote':
            content = self.convert_to_markdown(element)
            return f"> {content}" if content else ""
        
        # Handle code blocks
        elif element.name in ['pre', 'code']:
            code = element.get_text(strip=True)
            if element.name == 'pre':
                return f"```\n{code}\n```"
            else:
                return f"`{code}`"
        
        # Default: convert to markdown
        else:
            return self.convert_to_markdown(element)
    
    def convert_to_markdown(self, element) -> str:
        """Convert HTML element to markdown format"""
        if isinstance(element, str):
            return element.strip()
        
        result = []
        
        for child in element.children:
            if isinstance(child, str):
                text = child.strip()
                if text:
                    result.append(text)
            
            elif child.name == 'br':
                result.append('\n')
            
            elif child.name in ['strong', 'b']:
                content = self.convert_to_markdown(child)
                if content:
                    result.append(f"**{content}**")
            
            elif child.name in ['em', 'i']:
                content = self.convert_to_markdown(child)
                if content:
                    result.append(f"*{content}*")
            
            elif child.name == 'code':
                result.append(f"`{child.get_text(strip=True)}`")
            
            elif child.name == 'a':
                link_text = child.get_text(strip=True)
                href = child.get('href', '')
                if href:
                    # Handle relative URLs
                    if href.startswith('/'):
                        href = f"https://docs.netskope.com{href}"
                    elif not href.startswith(('http://', 'https://', 'mailto:', '#')):
                        href = f"https://docs.netskope.com/{href}"
                    result.append(f"[{link_text}]({href})")
                else:
                    result.append(link_text)
            
            elif child.name == 'img':
                src = child.get('src', '')
                alt = child.get('alt', 'Image')
                if src:
                    # Handle relative URLs
                    if src.startswith('/'):
                        src = f"https://docs.netskope.com{src}"
                    # Only include content images, not icons
                    if 'wp-content/uploads' in src or (src.startswith('http') and 'icon' not in src.lower()):
                        result.append(f"![{alt}]({src})")
            
            elif child.name == 'ul':
                # Nested list
                ul_content = self.process_element(child)
                if ul_content:
                    result.append('\n' + ul_content)
            
            elif child.name == 'ol':
                # Nested list
                ol_content = self.process_element(child)
                if ol_content:
                    result.append('\n' + ol_content)
            
            elif child.name in ['span', 'div']:
                # Process inline elements
                content = self.convert_to_markdown(child)
                if content:
                    result.append(content)
            
            elif child.name not in ['script', 'style', 'noscript']:
                # Other elements - get text content
                content = self.convert_to_markdown(child)
                if content:
                    result.append(content)
        
        return ' '.join(result).strip()


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: parse_release_notes_playwright.py <url>")
        sys.exit(1)
    
    url = sys.argv[1]
    
    try:
        # Parse release notes
        parser = ReleaseNotesParser(url)
        html_content = parser.fetch_with_playwright()
        release_notes = parser.parse_html(html_content)
        
        # Output as JSON
        print(release_notes.to_json())
        
        # Log summary
        logger.info(f"Successfully parsed {len(release_notes.features)} features")
        
    except Exception as e:
        logger.error(f"Failed to parse release notes: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()