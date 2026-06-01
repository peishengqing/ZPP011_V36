@echo off


chcp     
    
    

rem Run fixed Python script (no Chinese in __file__, pure ASCII)


python.exe "%~dp0fix_pos_clean.py"


pause