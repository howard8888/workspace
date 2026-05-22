@echo off
setlocal

echo ============================================
echo CCA8 quick check
echo ============================================
echo.

cd /d "%~dp0"

echo Current folder:
cd
echo.

echo Python version:
python --version
echo.

echo Python location:
where python
echo.

echo Git status:
git status --short
echo.

echo ============================================
echo Running CCA8 preflight
echo ============================================
echo.

python cca8_run.py --preflight

echo.
echo ============================================
echo Done
echo ============================================
echo.

pause