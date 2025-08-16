#!/usr/bin/env python3
"""
Test translation with a single feature
"""

import json
import os
import sys

# Test data with one feature
test_data = {
    "version": "129.0.0",
    "features": [
        {
            "category": "Cloud TAP",
            "title": "Enhanced Security for Cloud Storage Access over Internet",
            "description": "Introducing support for AWS IAM Roles Anywhere as an authentication method when writing tapped traffic into AWS S3 storage.\n\nThis is a controlled General Availability feature. Contact Netskope Support or your Sales Representative to enable this feature for your tenant."
        }
    ]
}

# Save test data
with open('test_release_notes.json', 'w', encoding='utf-8') as f:
    json.dump(test_data, f, ensure_ascii=False, indent=2)

print("Test data created. To test translation, run:")
print("")
print("export OPENAI_API_KEY='your-api-key-here'")
print("python .github/scripts/translate_with_openai.py test_release_notes.json")
print("")
print("Or to test without API key (mock translation):")
print("python test_mock_translation.py")