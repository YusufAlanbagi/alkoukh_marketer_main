import requests
from config.settings import settings

def test_kb():
    url = settings.nano_banana_base_url + "/v1/nanobanana/generate-pro"
    headers = {
        "x-api-key": settings.nano_banana_api_key,
        "Authorization": f"Bearer {settings.nano_banana_api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "prompt": "Test image of a cute cat",
        "aspectRatio": "1:1"
    }
    print(f"Testing URL: {url}")
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        print(f"Status: {r.status_code}")
        print(f"Response: {r.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_kb()
