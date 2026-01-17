"""
Direct test for ZhipuAI API
"""
import requests
import json
import sys
import io

# Set UTF-8 encoding for Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# API config
api_key = "1a9b343b6bb947bf939814b919a3c9fb.Nv1tf3ds7jltzywn"
base_url = "https://open.bigmodel.cn/api/paas/v4"
model = "glm-4-flash"

print("=" * 60)
print("Testing ZhipuAI API")
print("=" * 60)

# Test 1: Standard OpenAI format
print("\n[Test 1] Standard OpenAI format")
print(f"URL: {base_url}/chat/completions")

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
}

payload = {
    "model": model,
    "messages": [
        {"role": "user", "content": "Hello"}
    ],
    "temperature": 0.7,
}

try:
    response = requests.post(f"{base_url}/chat/completions", json=payload, headers=headers, timeout=30)
    print(f"Status code: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"Success!")
        print(f"Response: {data['choices'][0]['message']['content']}")
    else:
        print(f"Failed")
        print(f"Response: {response.text}")

except Exception as e:
    print(f"Error: {e}")

# Test 2: Check API key format
print("\n[Test 2] Check API key format")
print(f"API key: {api_key}")
print(f"Key format: {'id.secret format' if '.' in api_key else 'Other format'}")

# Test 3: Try SDK
print("\n[Test 3] Use zhipuai SDK")
try:
    from zhipuai import ZhipuAI

    client = ZhipuAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Hello"}]
    )

    print(f"SDK call successful!")
    print(f"Response: {response.choices[0].message.content}")

except ImportError:
    print("zhipuai SDK not installed")
except Exception as e:
    print(f"SDK call failed: {e}")

print("\n" + "=" * 60)
