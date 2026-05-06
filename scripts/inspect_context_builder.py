"""Inspect context_builder.py structure"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

with open('core/context_engine/context_builder.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

with open('inspect_output.txt', 'w', encoding='utf-8') as out:
    for i in range(500, min(600, len(lines))):
        out.write(f'{i+1}: {lines[i]}')

print("Output saved to inspect_output.txt")
