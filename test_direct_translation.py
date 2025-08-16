#!/usr/bin/env python3
"""
Direct test of translation with OpenAI API
"""

import os
import sys

# APIキーを直接環境変数に設定してテスト
# ターミナルで設定されているOPENAI_API_KEYを使用
api_key = input("Please enter your OpenAI API key (or press Enter to skip): ").strip()

if api_key:
    os.environ['OPENAI_API_KEY'] = api_key
    
    # Import and run translation
    import json
    from openai import OpenAI
    
    # Test with a simple text
    client = OpenAI(api_key=api_key)
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Translate the following to Japanese:"},
                {"role": "user", "content": "Enhanced Security for Cloud Storage Access over Internet"}
            ],
            temperature=0.3,
            max_tokens=100
        )
        
        print("\n✅ API connection successful!")
        print(f"Translation: {response.choices[0].message.content}")
        
        # Now run the full translation script
        print("\n" + "="*60)
        print("Running full translation script...")
        print("="*60)
        
        os.system(f'OPENAI_API_KEY="{api_key}" python .github/scripts/translate_with_openai.py test_release_notes.json')
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nPlease check:")
        print("1. Your API key is valid")
        print("2. You have GPT-4o access")
        print("3. Your account has credits")
else:
    print("\nRunning without API key - showing mock translation")
    os.system('python test_mock_translation.py')