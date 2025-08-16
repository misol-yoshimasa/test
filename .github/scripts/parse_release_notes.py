#!/usr/bin/env python3
"""
Netskope Release Notes Parser
Python 3.12+ compatible script for parsing release notes and creating GitHub Discussions
"""

import json
import logging
import sys
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

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
    
    def to_discussion_body(self) -> str:
        """Generate the main discussion body"""
        body = f"# Netskope Release {self.version} - New Features and Enhancements\n\n"
        body += "This discussion contains all the new features and enhancements "
        body += f"from Netskope Release {self.version}.\n\n"
        body += "Each feature is posted as a separate comment below for easy reference and discussion.\n\n"
        body += f"**Total Features:** {len(self.features)}\n\n"
        
        # Create a summary by category
        categories = {}
        for feature in self.features:
            if feature.category not in categories:
                categories[feature.category] = []
            categories[feature.category].append(feature.title)
        
        body += "## Features by Category\n\n"
        for category, titles in sorted(categories.items()):
            body += f"### {category}\n"
            for title in titles:
                body += f"- {title}\n"
            body += "\n"
        
        return body
    
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
    """Parser for Netskope release notes HTML pages"""
    
    def __init__(self, url: str):
        self.url = url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; GitHubActions/1.0)'
        })
    
    def fetch_page(self) -> str:
        """Fetch the HTML content of the release notes page"""
        try:
            logger.info(f"Fetching page: {self.url}")
            response = self.session.get(self.url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Failed to fetch page: {e}")
            raise
    
    def parse_html(self, html_content: str) -> ReleaseNotes:
        """Parse HTML content and extract release notes"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract version from URL or title
        version = self.extract_version(soup)
        release_notes = ReleaseNotes(version=version)
        
        # Look for main content area
        content_area = self.find_content_area(soup)
        if not content_area:
            logger.warning("Could not find main content area")
            return release_notes
        
        current_category = "General"
        
        # Process all elements in the content area
        for element in content_area.find_all(['h3', 'h4', 'div', 'details']):
            # Handle accordion/details elements
            if element.name in ['details', 'div'] and 'accordion' in element.get('class', []):
                features = self.parse_accordion(element, current_category)
                release_notes.features.extend(features)
            
            # H3 elements define categories
            elif element.name == 'h3':
                current_category = element.get_text(strip=True)
                logger.info(f"Found category: {current_category}")
            
            # H4 elements define feature titles
            elif element.name == 'h4':
                feature = self.parse_feature(element, current_category)
                if feature:
                    release_notes.features.append(feature)
        
        logger.info(f"Parsed {len(release_notes.features)} features")
        return release_notes
    
    def extract_version(self, soup: BeautifulSoup) -> str:
        """Extract version number from page"""
        # Try to extract from URL
        if '129-0-0' in self.url:
            return '129.0.0'
        
        # Try to extract from page title
        title = soup.find('title')
        if title:
            title_text = title.get_text()
            if 'Release' in title_text:
                import re
                match = re.search(r'(\d+[\.\-]\d+[\.\-]\d+)', title_text)
                if match:
                    return match.group(1).replace('-', '.')
        
        return 'Unknown'
    
    def find_content_area(self, soup: BeautifulSoup) -> Optional[BeautifulSoup]:
        """Find the main content area of the page"""
        # Common content area selectors
        selectors = [
            'main',
            'article',
            '[role="main"]',
            '.content',
            '.main-content',
            '#content',
            '.documentation-content'
        ]
        
        for selector in selectors:
            content = soup.select_one(selector)
            if content:
                return content
        
        # Fallback to body
        return soup.find('body')
    
    def parse_accordion(self, element: BeautifulSoup, category: str) -> List[Feature]:
        """Parse accordion/collapsible sections"""
        features = []
        
        # Look for summary/header and content pairs
        summaries = element.find_all(['summary', '.accordion-header', '.accordion-title'])
        contents = element.find_all(['div', '.accordion-content', '.accordion-body'])
        
        for summary in summaries:
            title = summary.get_text(strip=True)
            
            # Find associated content
            content = summary.find_next_sibling()
            if content:
                description = self.extract_text_content(content)
                feature = Feature(
                    title=title,
                    description=description,
                    category=category
                )
                features.append(feature)
                logger.debug(f"Found accordion feature: {title}")
        
        return features
    
    def parse_feature(self, element: BeautifulSoup, category: str) -> Optional[Feature]:
        """Parse a single feature from an H4 element"""
        title = element.get_text(strip=True)
        
        # Find the description (usually following paragraphs/lists)
        description_parts = []
        sibling = element.find_next_sibling()
        
        while sibling and sibling.name not in ['h3', 'h4']:
            if sibling.name in ['p', 'ul', 'ol', 'div']:
                text = self.extract_text_content(sibling)
                if text:
                    description_parts.append(text)
            sibling = sibling.find_next_sibling()
        
        if description_parts:
            description = '\n\n'.join(description_parts)
            return Feature(
                title=title,
                description=description,
                category=category
            )
        
        return None
    
    def extract_text_content(self, element: BeautifulSoup) -> str:
        """Extract and format text content from an element"""
        if element.name == 'ul':
            items = [f"- {li.get_text(strip=True)}" for li in element.find_all('li')]
            return '\n'.join(items)
        elif element.name == 'ol':
            items = [f"{i+1}. {li.get_text(strip=True)}" 
                    for i, li in enumerate(element.find_all('li'))]
            return '\n'.join(items)
        else:
            return element.get_text(strip=True)
    
    def parse(self) -> ReleaseNotes:
        """Main parsing method"""
        html_content = self.fetch_page()
        return self.parse_html(html_content)


def main():
    """Main entry point for the script"""
    if len(sys.argv) < 2:
        # Default URL
        url = "https://docs.netskope.com/en/new-features-and-enhancements-in-release-129-0-0"
    else:
        url = sys.argv[1]
    
    try:
        parser = ReleaseNotesParser(url)
        release_notes = parser.parse()
        
        # Output as JSON for GitHub Actions
        print(release_notes.to_json())
        
    except Exception as e:
        logger.error(f"Failed to parse release notes: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()