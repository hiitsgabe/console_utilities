import re

# Sample JSON response
json_response = '''
{
    "files": [
    {
        "url": "https://cdn.submundo-wow.com.br/base/%231%20Anagrams%20Sudokus%20Bundle%20%5B01007360179AE000%5D%5Bv0%5D.nsz",
        "size": 93617879
    },
    {
        "url": "https://cdn.submundo-wow.com.br/base/%231%20Anagrams%20%5B0100F1D014F08000%5D%5Bv0%5D.nsz",
        "size": 91318306
    }
]
}
'''

# Test different regex patterns
patterns = [
    # Current pattern from config
    r'"url":\s*"(?P<id>[^"]+/(?P<title>[^"/]+\.nsz))",\s*"size":\s*(?P<size>\d+)',
    
    # Alternative patterns
    r'"url":\s*"(?P<id>[^"]+)",\s*"size":\s*(?P<size>\d+)',
    r'"url":\s*"(?P<url>[^"]+)",\s*"size":\s*(?P<size>\d+)',
]

for i, pattern in enumerate(patterns):
    print(f"\n--- Testing Pattern {i+1}: {pattern} ---")
    matches = re.finditer(pattern, json_response)
    for match in matches:
        print(f"Match: {match.groupdict()}")
        if 'title' in match.groupdict():
            # Extract filename from URL
            url = match.group('id') if 'id' in match.groupdict() else match.group('url')
            filename = url.split('/')[-1]
            print(f"  Extracted filename: {filename}")