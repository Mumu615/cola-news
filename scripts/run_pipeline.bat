@echo off
setlocal

set ROOT=%~dp0..
cd /d "%ROOT%"

echo [1/5] Collect AI RSS...
py scripts\collect_ai_news.py
if errorlevel 1 goto err

echo [2/5] Collect GitHub Trending...
py scripts\collect_github.py
if errorlevel 1 goto err

echo [3/5] Generate CN posts...
py scripts\generate_posts.py
if errorlevel 1 goto err

echo [4/5] Build search index...
py scripts\build_search_index.py
if errorlevel 1 goto err

echo [5/5] Build Hugo site...
cache\tools\hugo.exe --minify
if errorlevel 1 goto err

if exist ".git" (
  git add .
  git diff --cached --quiet
  if errorlevel 1 (
    git commit -m "chore: auto update cola news"
    git push origin HEAD
    if errorlevel 1 (
      echo [WARN] Git push failed. Check remote/auth.
    ) else (
      echo [OK] Pushed to origin. GitHub Actions should deploy.
    )
  ) else (
    echo [OK] No changes.
  )
) else (
  echo [WARN] Not a git repo yet. Local build finished only.
)

echo DONE
exit /b 0

:err
echo [ERROR] Pipeline failed.
exit /b 1
