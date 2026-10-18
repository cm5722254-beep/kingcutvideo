@echo off
setlocal
cd /d "%~dp0"
set "PATH=C:\Users\soche\MinGit\cmd;C:\Users\soche\MinGit\ucrt64\bin;%PATH%"

echo ======================================================
echo    Pushing 50 Commits to GitHub
echo    Repository: https://github.com/cm5722254-beep/kingcutvideo.git
echo ======================================================
echo.

git push -u origin main

if %errorlevel% neq 0 (
    echo.
    echo [NOTE] If GitHub browser authentication opened, please authorize.
    echo If you have a GitHub Personal Access Token (PAT), you can push with:
    echo   git push https://YOUR_TOKEN@github.com/cm5722254-beep/kingcutvideo.git main
    echo.
    pause
) else (
    echo.
    echo [SUCCESS] Successfully pushed all 50 commits to GitHub!
    pause
)
