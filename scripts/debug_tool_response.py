"""Debug tool response handling"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Read context_builder.py
with open('core/context_engine/context_builder.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Write the entire content to a file for inspection
with open('debug_context_builder.txt', 'w', encoding='utf-8') as f:
    f.write(content)

print("Full context_builder.py written to debug_context_builder.txt")

# Find build_messages function
lines = content.split('\n')
in_build_messages = False
indent_level = 0
build_messages_lines = []

for i, line in enumerate(lines, 1):
    if 'def build_messages' in line:
        in_build_messages = True
        indent_level = len(line) - len(line.lstrip())
        print(f"Found build_messages at line {i}")
    if in_build_messages:
        build_messages_lines.append(f"{i}: {line}")
        # Check for role handling
        if 'role' in line and ('user' in line or 'assistant' in line or 'tool' in line or 'summary' in line):
            print(f"Line {i} [ROLE]: {line.strip()[:100]}")
        # Stop when we hit the next function at same or lower indent level
        if line.strip() and not line.strip().startswith('#') and not line.strip().startswith('"""') and not line.strip().startswith("'''"):
            current_indent = len(line) - len(line.lstrip())
            if line.strip().startswith('def ') and 'build_messages' not in line and current_indent <= indent_level:
                break

# Save build_messages function
with open('debug_build_messages.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(build_messages_lines))
print(f"Saved {len(build_messages_lines)} lines to debug_build_messages.txt")
