#!/bin/bash
# Usage: render.sh deck.pptx outdir [width_px]
# Renders every slide to PNG via Windows PowerPoint COM (accurate fonts). WSL only.
set -e
IN=$(realpath "$1"); OUT=$(realpath -m "$2"); W=${3:-1600}
WT=/mnt/c/Users/DELL/AppData/Local/Temp/sby_render_$$
mkdir -p "$WT/out" "$OUT"; cp "$IN" "$WT/in.pptx"
WIN=$(wslpath -w "$WT")
cat > "$WT/r.ps1" <<PS
\$ErrorActionPreference = 'Stop'
\$app = New-Object -ComObject PowerPoint.Application
\$p = \$app.Presentations.Open('$WIN\\in.pptx', \$true, \$false, \$false)
\$ratio = \$p.PageSetup.SlideHeight / \$p.PageSetup.SlideWidth
\$h = [int]($W * \$ratio)
foreach (\$s in \$p.Slides) { \$s.Export(('$WIN\\out\\slide-{0:D2}.png' -f \$s.SlideIndex), 'PNG', $W, \$h) }
\$p.Close()
if (\$app.Presentations.Count -eq 0) { \$app.Quit() }
PS
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w "$WT/r.ps1")"
rm -f "$OUT"/slide-*.png; cp "$WT"/out/*.png "$OUT"/; rm -rf "$WT"
ls "$OUT"
