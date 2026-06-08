import matplotlib.font_manager as fm
# Find Chinese fonts
chinese_fonts = [f.name for f in fm.fontManager.ttflist 
                 if any(kw in f.name.lower() for kw in ['yahei', 'simhei', 'song', 'heiti', 'microsoft', 'fang'])]
print("Found Chinese fonts:")
for f in sorted(set(chinese_fonts)):
    print(f"  {f}")
