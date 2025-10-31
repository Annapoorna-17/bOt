#!/usr/bin/env python3
"""
Test script to demonstrate the list formatting fix.
This shows how the _fix_list_formatting function works.
"""
import re

def _fix_list_formatting(text: str) -> str:
    """
    Fix list formatting by ensuring each bullet point or numbered item is on its own line.
    This handles cases where the LLM generates bullets on the same line.
    Uses multiple strategies to ensure proper formatting.
    """
    original_text = text

    # Strategy 1: Fix bullets that appear mid-line (not after a newline)
    # Replace any occurrence of " • " (space-bullet-space) that's not at line start with newline-bullet-space
    text = re.sub(r'(?<!\n) ([•●○◦]) ', r'\n\1 ', text)

    # Strategy 2: Also catch bullets with minimal spacing
    text = re.sub(r'(?<!\n)([•●○◦]) ', r'\n\1 ', text)

    # Strategy 3: Fix numbered lists - look for patterns like "text 1. " where not at line start
    text = re.sub(r'(?<!\n) (\d+\.) ', r'\n\1 ', text)

    # Strategy 4: Catch edge case where bullet is directly after text without much space
    # Match: letter/number followed by space(s) and bullet
    text = re.sub(r'([a-zA-Z0-9]) +([•●○◦]) ', r'\1\n\2 ', text)

    # Clean up: Remove excessive spaces after bullets
    text = re.sub(r'^([•●○◦])  +', r'\1 ', text, flags=re.MULTILINE)
    text = re.sub(r'^(\d+\.)  +', r'\1 ', text, flags=re.MULTILINE)

    # Debug logging
    if text != original_text:
        print(f"DEBUG: List formatting applied. Before length: {len(original_text)}, After length: {len(text)}")
        # Count newlines added
        newlines_before = original_text.count('\n')
        newlines_after = text.count('\n')
        print(f"DEBUG: Newlines before: {newlines_before}, after: {newlines_after}")

    return text


# Test with the actual problematic response from user
bad_response = "Here is the list of management members at Stixis: • Rayudu Dhananjaya - President & CEO • Surajit Bhuyan - Chief Sales Officer • Mahesh P - Chief Technology Officer • Agni Pravo Ghosh - VP - Strategic Business & Development"

print("=" * 80)
print("BEFORE FIX:")
print("=" * 80)
print(bad_response)
print()

fixed_response = _fix_list_formatting(bad_response)

print("=" * 80)
print("AFTER FIX:")
print("=" * 80)
print(fixed_response)
print()

# Test with numbered list
bad_numbered = "Here are the steps: 1. First step 2. Second step 3. Third step"
print("=" * 80)
print("NUMBERED LIST BEFORE FIX:")
print("=" * 80)
print(bad_numbered)
print()

fixed_numbered = _fix_list_formatting(bad_numbered)
print("=" * 80)
print("NUMBERED LIST AFTER FIX:")
print("=" * 80)
print(fixed_numbered)
