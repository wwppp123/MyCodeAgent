"""Test WeatherTool functionality"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from tools.builtin.weather import WeatherTool

# Create tool instance
tool = WeatherTool('.')

# Test 1: Get parameters
print("=== Tool Parameters ===")
params = tool.get_parameters()
for p in params:
    print(f"  - {p.name}: {p.description} (required={p.required})")

# Test multiple cities
test_cities = ['北京', '吉林', '长春', 'Shanghai', '深圳']
all_results = []

for city in test_cities:
    print(f"\n=== Querying {city} Weather ===")
    try:
        result = tool.run({'city': city, 'format': 'simple'})
        data = json.loads(result)
        print(f"Status: {data.get('status')}")
        text = data.get('text', '')
        print(f"Result: {text}")
        all_results.append({'city': city, 'result': data})
    except Exception as e:
        print(f"Error: {e}")
        all_results.append({'city': city, 'error': str(e)})

# Save full results to file
with open('weather_test_result.json', 'w', encoding='utf-8') as f:
    json.dump(all_results, f, ensure_ascii=False, indent=2)
print("\nFull results saved to: weather_test_result.json")

print("\n=== Summary ===")
success_count = sum(1 for r in all_results if 'result' in r and r['result'].get('status') == 'success')
print(f"Successfully tested {success_count}/{len(test_cities)} cities")
