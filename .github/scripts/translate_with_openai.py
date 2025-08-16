#!/usr/bin/env python3
"""
Translate release notes using OpenAI GPT-4o API
"""

import json
import os
import sys
import time
from typing import Dict, List
import openai
from openai import OpenAI

def translate_text(client: OpenAI, text: str, context: str = "") -> str:
    """
    Translate English text to Japanese using GPT-4o
    """
    try:
        system_prompt = """You are a professional technical translator specializing in IT and cloud security.
Translate the following English text to Japanese, maintaining:
1. Technical accuracy
2. Proper IT terminology in Japanese
3. Markdown formatting (keep links, images, code blocks as-is)
4. Natural Japanese expression

Important:
- Keep URLs, image links, and code blocks unchanged
- Translate alt text in images
- Maintain list formatting
- Keep proper nouns like "Netskope", "AWS", etc. in English"""

        user_prompt = f"Translate to Japanese:\n\n{text}"
        
        if context:
            user_prompt = f"Context: {context}\n\n{user_prompt}"

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,  # Lower temperature for more consistent translations
            max_tokens=2000
        )
        
        return response.choices[0].message.content.strip()
    
    except Exception as e:
        print(f"Translation error: {e}", file=sys.stderr)
        return f"[翻訳エラー: {str(e)}]\n\n{text}"


def create_bilingual_content(title: str, content: str, title_ja: str, content_ja: str, category: str) -> str:
    """
    Create bilingual content with Japanese as main and English in collapsible section
    """
    # Format the bilingual content (no emojis, no category duplication)
    bilingual = f"## {title_ja}\n\n"
    bilingual += f"{content_ja}\n\n"
    bilingual += "<details>\n"
    bilingual += "<summary>View original English version</summary>\n\n"
    bilingual += f"### {title}\n\n"
    bilingual += f"{content}\n\n"
    bilingual += "</details>"
    
    return bilingual


def translate_features(features: List[Dict], api_key: str) -> List[Dict]:
    """
    Translate all features using OpenAI API
    """
    client = OpenAI(api_key=api_key)
    translated_features = []
    
    total = len(features)
    print(f"Translating {total} features using GPT-4o...", file=sys.stderr)
    
    for i, feature in enumerate(features, 1):
        print(f"Translating [{i}/{total}]: {feature['title'][:50]}...", file=sys.stderr)
        
        # Translate title
        title_ja = translate_text(
            client, 
            feature['title'],
            context=f"Category: {feature['category']}"
        )
        
        # Translate description
        description_ja = translate_text(
            client,
            feature['description'],
            context=f"Feature: {feature['title']}, Category: {feature['category']}"
        )
        
        # Create bilingual content
        bilingual_description = create_bilingual_content(
            feature['title'],
            feature['description'],
            title_ja,
            description_ja,
            feature['category']
        )
        
        translated_features.append({
            'category': feature['category'],
            'title': title_ja,  # Use Japanese title as main
            'title_en': feature['title'],  # Keep English title
            'description': bilingual_description  # Bilingual content
        })
        
        # Small delay to avoid rate limiting
        if i < total:
            time.sleep(0.5)
    
    return translated_features


def main():
    """Main entry point"""
    # Check for API key
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)
    
    # Read input from stdin or file
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)
    
    # Check if translation is requested
    if os.environ.get('SKIP_TRANSLATION', '').lower() == 'true':
        print("Skipping translation as requested", file=sys.stderr)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    
    # Translate features
    translated_features = translate_features(data['features'], api_key)
    
    # Update data with translated features
    data['features'] = translated_features
    data['translated'] = True
    
    # Output translated data
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()