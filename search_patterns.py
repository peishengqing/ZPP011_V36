#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Search for patterns in table_events.py and ui_builder.py"""

import re

def search_file(filepath, patterns):
    """Search for patterns in a file and print matching lines with line numbers"""
    print(f"\n{'='*60}")
    print(f"Searching in: {filepath}")
    print('='*60)
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines, 1):
            for pattern in patterns:
                if pattern in line:
                    print(f"{i}: {line.rstrip()}")
                    break
    except Exception as e:
        print(f"Error reading {filepath}: {e}")

# Search patterns
patterns = [
    '_on_filter_changed',
    'def sort',
    'audit_tree',
    '__init__',
    '_get_row_tags',
    'yscroll',
    'vscroll',
    'scrollbar',
    '_refresh_audit_tree'
]

# Search in table_events.py
search_file(r'gui\event_handlers\table_events.py', patterns)

# Search in ui_builder.py for audit_tree creation
patterns2 = ['audit_tree', 'scrollbar', 'vscroll', 'yscroll']
search_file(r'gui\ui_builder.py', patterns2)
