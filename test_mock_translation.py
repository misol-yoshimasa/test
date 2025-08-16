#!/usr/bin/env python3
"""
Test translation format without actual API call
"""

import json

# Mock translation result
mock_result = {
    "version": "129.0.0",
    "features": [
        {
            "category": "Cloud TAP",
            "title": "クラウドストレージへのインターネット経由アクセスのセキュリティ強化",
            "title_en": "Enhanced Security for Cloud Storage Access over Internet",
            "description": """## クラウドストレージへのインターネット経由アクセスのセキュリティ強化

AWS S3ストレージにタップされたトラフィックを書き込む際の認証方法として、AWS IAM Roles Anywhereのサポートを導入しました。

これは制御された一般提供機能です。この機能をテナントで有効にするには、Netskopeサポートまたは営業担当者にお問い合わせください。

<details>
<summary>🇬🇧 View original English version</summary>

### Enhanced Security for Cloud Storage Access over Internet

Introducing support for AWS IAM Roles Anywhere as an authentication method when writing tapped traffic into AWS S3 storage.

This is a controlled General Availability feature. Contact Netskope Support or your Sales Representative to enable this feature for your tenant.

</details>

---
*Category: Cloud TAP*"""
        }
    ],
    "translated": True
}

# Show the formatted result
print("Mock translation result:")
print("=" * 60)
print(json.dumps(mock_result, ensure_ascii=False, indent=2))
print("=" * 60)
print("\nThis is how the comment will appear in GitHub Discussion:")
print("-" * 60)
print(mock_result['features'][0]['description'])
print("-" * 60)

# Save for testing
with open('test_translated.json', 'w', encoding='utf-8') as f:
    json.dump(mock_result, f, ensure_ascii=False, indent=2)