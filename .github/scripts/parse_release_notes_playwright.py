#!/usr/bin/env python3
"""
Netskope Release Notes Parser with Playwright
Python 3.12+ compatible script for parsing release notes with JavaScript rendering
"""

import json
import logging
import sys
from dataclasses import dataclass, field
from typing import List, Optional
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class Feature:
    """Represents a single feature in the release notes"""
    title: str
    description: str
    category: str
    
    def to_markdown(self) -> str:
        """Convert feature to markdown format"""
        return f"### {self.title}\n\n{self.description}"


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
        return json.dumps(data, indent=2, ensure_ascii=False)


class ReleaseNotesParser:
    """Parser for Netskope release notes using Playwright"""
    
    def __init__(self, url: str):
        self.url = url
    
    def fetch_and_parse(self) -> ReleaseNotes:
        """Fetch page with Playwright and parse content"""
        with sync_playwright() as p:
            # Launch browser in headless mode
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            logger.info(f"Fetching page with Playwright: {self.url}")
            page.goto(self.url, wait_until='networkidle')
            
            # Wait for content to load
            page.wait_for_timeout(3000)
            
            # Click on all expandable elements (accordions, etc.)
            self.expand_all_content(page)
            
            # Get the rendered HTML
            html_content = page.content()
            browser.close()
            
            # Parse the HTML
            return self.parse_html(html_content)
    
    def expand_all_content(self, page):
        """Expand all collapsible/accordion elements"""
        try:
            # Try different selectors for expandable content
            selectors = [
                'button[aria-expanded="false"]',
                '.accordion-button:not(.collapsed)',
                '.collapsible-header',
                '[data-toggle="collapse"]',
                '.expand-button',
                '.toggle-button',
                'summary',
                '.accordion-toggle'
            ]
            
            for selector in selectors:
                elements = page.query_selector_all(selector)
                for element in elements:
                    try:
                        element.click()
                        page.wait_for_timeout(100)  # Small delay between clicks
                    except:
                        pass
            
            # Wait for expansions to complete
            page.wait_for_timeout(1000)
            
        except Exception as e:
            logger.debug(f"Error expanding content: {e}")
    
    def parse_html(self, html_content: str) -> ReleaseNotes:
        """Parse HTML content and extract release notes"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract version
        version = self.extract_version(soup)
        release_notes = ReleaseNotes(version=version)
        
        # Try multiple strategies to find features
        features = []
        
        # Strategy 1: Look for h3/h4 combinations
        features.extend(self.parse_by_headings(soup))
        
        # Strategy 2: Look for specific class patterns
        features.extend(self.parse_by_classes(soup))
        
        # Strategy 3: Look for list items with strong tags
        features.extend(self.parse_by_lists(soup))
        
        # Remove duplicates based on title
        seen_titles = set()
        for feature in features:
            if feature.title not in seen_titles:
                release_notes.features.append(feature)
                seen_titles.add(feature.title)
        
        logger.info(f"Parsed {len(release_notes.features)} features")
        return release_notes
    
    def extract_version(self, soup: BeautifulSoup) -> str:
        """Extract version number from page"""
        if '129-0-0' in self.url:
            return '129.0.0'
        
        # Try to find version in title or headings
        title = soup.find('title')
        if title:
            import re
            match = re.search(r'(\d+[\.\-]\d+[\.\-]\d+)', title.get_text())
            if match:
                return match.group(1).replace('-', '.')
        
        return 'Unknown'
    
    def parse_by_headings(self, soup: BeautifulSoup) -> List[Feature]:
        """Parse features by h3 (category) and h4 (title) structure"""
        features = []
        current_category = "General"
        last_h3 = None
        
        # Look for all h3 and h4 elements
        for element in soup.find_all(['h3', 'h4', 'h5', 'h6']):
            text = element.get_text(strip=True)
            
            # Skip empty or navigation headers
            if not text or len(text) < 3:
                continue
            
            # H3 elements can be either categories or titles
            if element.name == 'h3':
                # Check if next sibling is also h3 - if so, first h3 is category, second is title
                next_elem = element.find_next_sibling(['h3', 'h4', 'h5', 'h6'])
                
                if next_elem and next_elem.name == 'h3':
                    # This h3 is a category
                    current_category = text
                    last_h3 = element
                    logger.debug(f"Found category: {current_category}")
                else:
                    # This h3 is a title (either standalone or follows another h3)
                    description = self.get_following_description(element)
                    if description or (last_h3 and element != last_h3):
                        # If this h3 immediately follows another h3, it's a title
                        if last_h3 and element.find_previous_sibling(['h3', 'h4', 'h5', 'h6']) == last_h3:
                            feature = Feature(
                                title=text,
                                description=description if description else "",
                                category=current_category
                            )
                            features.append(feature)
                            logger.debug(f"Found feature (h3 as title): {text}")
                        elif description:
                            # Standalone h3 with description
                            feature = Feature(
                                title=text,
                                description=description,
                                category=current_category
                            )
                            features.append(feature)
                            logger.debug(f"Found feature (h3): {text}")
            
            # H4 and below are feature titles
            elif element.name in ['h4', 'h5', 'h6']:
                # Get description from following elements
                description = self.get_following_description(element)
                if description:
                    feature = Feature(
                        title=text,
                        description=description,
                        category=current_category
                    )
                    features.append(feature)
                    logger.debug(f"Found feature: {text}")
        
        return features
    
    def parse_by_classes(self, soup: BeautifulSoup) -> List[Feature]:
        """Parse features by common class patterns"""
        features = []
        
        # Common patterns for feature sections
        patterns = [
            ('feature-item', 'feature-title', 'feature-description'),
            ('release-item', 'release-title', 'release-content'),
            ('enhancement', 'title', 'content'),
            ('card', 'card-title', 'card-body')
        ]
        
        for container_class, title_class, desc_class in patterns:
            containers = soup.find_all(class_=container_class)
            for container in containers:
                title_elem = container.find(class_=title_class)
                desc_elem = container.find(class_=desc_class)
                
                if title_elem and desc_elem:
                    feature = Feature(
                        title=title_elem.get_text(strip=True),
                        description=desc_elem.get_text(strip=True),
                        category=self.guess_category(container)
                    )
                    features.append(feature)
        
        return features
    
    def parse_by_lists(self, soup: BeautifulSoup) -> List[Feature]:
        """Parse features from list structures"""
        features = []
        current_category = "General"
        
        # Look for ul/ol elements that might contain features
        for list_elem in soup.find_all(['ul', 'ol']):
            # Check if this list is under a heading
            prev = list_elem.find_previous_sibling(['h3', 'h4', 'h5'])
            if prev:
                current_category = prev.get_text(strip=True)
            
            for li in list_elem.find_all('li'):
                # Look for strong/b tags that might be titles
                title_elem = li.find(['strong', 'b'])
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    # Remove the title element to get description
                    title_elem.extract()
                    # Get description with images
                    description = self.process_element_with_images(li)
                    
                    if title and len(title) > 3:
                        feature = Feature(
                            title=title,
                            description=description if description else "No description available",
                            category=current_category
                        )
                        features.append(feature)
        
        return features
    
    def get_following_description(self, element) -> str:
        """Get description text from elements following a heading"""
        description_parts = []
        sibling = element.find_next_sibling()
        
        while sibling and sibling.name not in ['h3', 'h4', 'h5', 'h6']:
            # Handle all elements, including divs, p, lists, etc.
            if sibling.name:
                # Look for images within any element
                images = sibling.find_all('img')
                for img in images:
                    src = img.get('src', '')
                    # Only include actual content images
                    if src and ('wp-content/uploads' in src or src.startswith('http')):
                        img_markdown = self.image_to_markdown(img)
                        if img_markdown and img_markdown not in '\n'.join(description_parts):
                            description_parts.append(img_markdown)
                
                # Extract text content
                text = self.extract_text_content(sibling)
                if text and len(text) > 10:  # Skip very short text
                    # Remove leading colon if present
                    text = text.lstrip(': ')
                    description_parts.append(text)
            
            sibling = sibling.find_next_sibling()
            
            # Stop if we've collected enough description
            if len('\n'.join(description_parts)) > 1000:
                break
        
        return '\n\n'.join(description_parts) if description_parts else ""
    
    def extract_text_content(self, element) -> str:
        """Extract and format text content from an element"""
        if element.name == 'ul':
            items = []
            for li in element.find_all('li'):
                li_text = self.convert_element_to_markdown(li)
                items.append(f"- {li_text}")
            return '\n'.join(items)
        elif element.name == 'ol':
            items = []
            for i, li in enumerate(element.find_all('li')):
                li_text = self.convert_element_to_markdown(li)
                items.append(f"{i+1}. {li_text}")
            return '\n'.join(items)
        else:
            return self.convert_element_to_markdown(element)
    
    def extract_content_with_images(self, element) -> str:
        """Extract text content with embedded images as markdown"""
        # Clone the element to avoid modifying the original
        import copy
        element_copy = copy.copy(element)
        
        # Find all images in the element
        images = element.find_all('img')
        
        # If there are images, convert them to markdown
        if images:
            for img in images:
                img_markdown = self.image_to_markdown(img)
                if img_markdown:
                    # Create a new string element with the markdown
                    img.replace_with(f" {img_markdown} ")
        
        # Now extract the text content
        if element.name == 'ul':
            items = []
            for li in element.find_all('li'):
                li_content = self.process_element_with_images(li)
                items.append(f"- {li_content}")
            return '\n'.join(items)
        elif element.name == 'ol':
            items = []
            for i, li in enumerate(element.find_all('li')):
                li_content = self.process_element_with_images(li)
                items.append(f"{i+1}. {li_content}")
            return '\n'.join(items)
        else:
            return self.process_element_with_images(element)
    
    def process_element_with_images(self, element) -> str:
        """Process an element converting images to markdown"""
        return self.convert_element_to_markdown(element)
    
    def convert_element_to_markdown(self, element) -> str:
        """Convert HTML element to markdown, preserving links and images"""
        if isinstance(element, str):
            return element.strip()
        
        result = []
        
        # Process all children
        for child in element.children:
            if isinstance(child, str):
                text = child.strip()
                if text:
                    result.append(text)
            elif child.name == 'a':
                # Convert links to markdown
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
                img_markdown = self.image_to_markdown(child)
                if img_markdown:
                    result.append(img_markdown)
            elif child.name in ['strong', 'b']:
                # Convert bold to markdown
                text = self.convert_element_to_markdown(child)
                if text:
                    result.append(f"**{text}**")
            elif child.name in ['em', 'i']:
                # Convert italic to markdown
                text = self.convert_element_to_markdown(child)
                if text:
                    result.append(f"*{text}*")
            elif child.name == 'code':
                # Convert code to markdown
                text = child.get_text(strip=True)
                if text:
                    result.append(f"`{text}`")
            elif child.name == 'br':
                result.append('\n')
            else:
                # Recursively process other elements
                text = self.convert_element_to_markdown(child)
                if text:
                    result.append(text)
        
        return ' '.join(filter(None, result))
    
    def image_to_markdown(self, img_element) -> str:
        """Convert an img element to markdown format"""
        src = img_element.get('src', '')
        alt = img_element.get('alt', '')
        
        if not src:
            return ''
        
        # Skip icons and logos
        if 'logo' in src.lower() or 'icon' in src.lower() or src.startswith('data:'):
            return ''
        
        # Use a default alt text if none provided
        if not alt:
            alt = 'Image'
        
        # Handle relative URLs
        if src.startswith('/'):
            # Assume it's from the Netskope docs site
            src = f"https://docs.netskope.com{src}"
        elif not src.startswith(('http://', 'https://')):
            # Relative URL without leading slash
            src = f"https://docs.netskope.com/{src}"
        
        return f"![{alt}]({src})"
    
    def guess_category(self, element) -> str:
        """Guess category from element context"""
        # Look for parent heading
        parent = element.find_parent(['section', 'div', 'article'])
        if parent:
            heading = parent.find(['h3', 'h2'])
            if heading:
                return heading.get_text(strip=True)
        return "General"


def main():
    """Main entry point for the script"""
    if len(sys.argv) < 2:
        # Default URL
        url = "https://docs.netskope.com/en/new-features-and-enhancements-in-release-129-0-0"
    else:
        url = sys.argv[1]
    
    try:
        parser = ReleaseNotesParser(url)
        release_notes = parser.fetch_and_parse()
        
        # Output as JSON for GitHub Actions
        print(release_notes.to_json())
        
    except Exception as e:
        logger.error(f"Failed to parse release notes: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()