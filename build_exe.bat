@echo off
echo Building SPRV_MergeTool.exe ...
python -m PyInstaller --onefile --windowed --name "SPRV_MergeTool" merge_sprv.py
if %ERRORLEVEL% neq 0 (
    echo Build FAILED.
    pause
    exit /b 1
)
echo Cleaning up build artifacts ...
rmdir /s /q build 2>nul
del /f SPRV_MergeTool.spec 2>nul
echo.
echo Done! EXE is at: dist\SPRV_MergeTool.exe
pause
