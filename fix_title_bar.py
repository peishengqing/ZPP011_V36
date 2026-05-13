# -*- coding: utf-8 -*-
"""Add title bar to inventory_view.py using exact byte-level matching"""

inv_path = r'E:\zpp011_dev\模块化脚本\gui\inventory_view.py'
with open(inv_path, 'rb') as f:
    raw = f.read()

# The exact bytes to find (from the file's actual content)
old_bytes = b'''    def _build_ui(self):\r
        """\xb9\xb9\xbd\xa8\xbd\xe7\xc3\xe6\xb2\xbc\xbe\xd6"""\r
        # \xe2\x94\x80\xe2\x94\x80 \xb6\xa5\xb2\xb2\xb2\xbf\xb2\xd4\xd7\xf7\xc0\xb8 \xe2\x94\x80\xe2\x94\x80\xe2\x94\x80\xe2\x94\x80\xe2\x94\x80\xe2\x94\x80\xe2\x94\x80\xe2\x94\x80\xe2\x94\x80\xe2\x94\x80\xe2\x94\x80\xe2\x94\x80\xe2\x94\x80\xe2\x94\x80\r
        top_frame = tk.Frame(self, bg='#f5f5f5', pady=10)\r
        top_frame.pack(fill='x', padx=10)'''

new_bytes = b'''    def _build_ui(self):\r
        """\xb9\xb9\xbd\xa8\xbd\xe7\xc3\xe6\xb2\xbc\xbe\xd6"""\r
        # \xe2\x94\x80\xe2\x94\x80 \xb6\xa5\xb2\xb2\xb2\xbf\xb2\xd4\xd7\xf7\xc0\xb8 (title bar)\r
        header = tk.Frame(self, bg='#1a365d', height=56)\r
        header.pack(fill="x")\r
        header.pack_propagate(False)\r
\r
        tk.Label(header, text="\xf0\x9f\x93\xa6", font=("Segoe UI Emoji", 22),\r
                 bg='#1a365d').pack(side="left", padx=(16, 8))\r
        title_frame = tk.Frame(header, bg='#1a365d')\r
        title_frame.pack(side="left")\r
        tk.Label(title_frame, text="\xd4\xc6\xc4\xcf\xb4\xef\xc0\xfbZPP011 \xbf\xe2\xb4\xe6\xc1\xf7\xcb\xae\xb9\xdc\xc0\xed",\r
                 font=("Microsoft YaHei", 13, "bold"), fg='#ffffff',\r
                 bg='#1a365d').pack(anchor="w")\r
        tk.Label(title_frame, text="\xd6\xc6\xd7\xf7\xc8\xcb\xa3\xba\xc5\xf8\xca\xcc\xc7\xe5  |  v36.1",\r
                 font=("Microsoft YaHei", 8), fg='#cae8ff',\r
                 bg='#1a365d').pack(anchor="w")\r
\r
        # \xe2\x94\x80\xe2\x94\x80 \xb6\xa5\xb2\xb2\xb2\xbf\xb2\xd4\xd7\xf7\xc0\xb8\r
        top_frame = tk.Frame(self, bg='#f5f5f5')\r
        top_frame.pack(fill='x', padx=10, pady=(8, 0))'''

if old_bytes in raw:
    raw = raw.replace(old_bytes, new_bytes)
    with open(inv_path, 'wb') as f:
        f.write(raw)
    print("SUCCESS: Title bar added!")
else:
    print("FAILED: pattern not found")
    # Debug: show what we have around _build_ui
    idx = raw.find(b'def _build_ui')
    if idx >= 0:
        print(f"Found _build_ui at byte {idx}")
        print(repr(raw[idx:idx+200]))
