$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '[1/5] 采集 AI RSS...'
py scripts/collect_ai_news.py

Write-Host '[2/5] 采集 GitHub Trending...'
py scripts/collect_github.py

Write-Host '[3/5] 生成中文文章...'
py scripts/generate_posts.py

Write-Host '[4/5] 构建搜索索引...'
py scripts/build_search_index.py

Write-Host '[5/5] Hugo 构建...'
.\cache\tools\hugo.exe --minify

if (Test-Path (Join-Path $root '.git')) {
  git add .
  $changes = git status --porcelain
  if ($changes) {
    $msg = "chore: 自动更新资讯 $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    git commit -m $msg | Out-Host
    git push origin HEAD 2>$null | Out-Host
    if ($LASTEXITCODE -eq 0) {
      Write-Host '已推送到 origin，GitHub Actions 将自动发布。'
    } else {
      Write-Warning '检测到 Git 仓库，但推送失败。请检查远程仓库、权限或登录状态。'
    }
  } else {
    Write-Host '无内容变更，跳过提交与推送。'
  }
} else {
  Write-Warning '当前目录还不是 Git 仓库，已完成本地更新与构建。若需自动发布，请先初始化并绑定 GitHub 远程仓库。'
}
