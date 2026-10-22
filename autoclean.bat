@echo off
echo Cleaning NUTRINUTS build files...
taskkill /f /im NUTRINUTS.exe 2>nul
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist __pycache__ rmdir /s /q __pycache__
if exist NUTRINUTS.spec del /q NUTRINUTS.spec
for /d /r %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
echo Clean ho gaya!
pause