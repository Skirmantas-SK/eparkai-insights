# Rebuild HA PNGs from the simple geometric SVG, using Windows System.Drawing.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$projectRoot = Split-Path -Parent $PSScriptRoot
[xml]$svg = Get-Content -LiteralPath (Join-Path $projectRoot 'assets/eparkai.svg') -Raw
$brandDirectory = Join-Path $projectRoot 'custom_components/eparkai/brand'
New-Item -ItemType Directory -Force -Path $brandDirectory | Out-Null
foreach ($theme in @('light', 'dark')) {
    $bitmap = [System.Drawing.Bitmap]::new(1024, 1024)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.Clear([System.Drawing.Color]::Transparent)
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.ScaleTransform(4, 4)
    foreach ($node in $svg.DocumentElement.ChildNodes) {
        if ($node.LocalName -eq 'title') { continue }
        $color = if ($node.HasAttribute('fill')) { $node.GetAttribute('fill') } else { $node.GetAttribute('stroke') }
        if ($theme -eq 'dark') {
            if ($color -eq '#187F72') { $color = '#48BDA4' }
            elseif ($color -eq '#B9E8D6') { $color = '#123E38' }
        }
        $brush = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml($color))
        switch ($node.LocalName) {
            'circle' {
                $radius = [float]$node.r
                $graphics.FillEllipse($brush, [float]$node.cx - $radius, [float]$node.cy - $radius, 2 * $radius, 2 * $radius)
            }
            'line' {
                $pen = [System.Drawing.Pen]::new($brush, [float]$node.GetAttribute('stroke-width'))
                $graphics.DrawLine($pen, [float]$node.x1, [float]$node.y1, [float]$node.x2, [float]$node.y2)
                $pen.Dispose()
            }
            'polygon' {
                [System.Drawing.PointF[]]$points = @($node.points.Split(' ') | ForEach-Object {
                    $coordinates = $_.Split(',')
                    [System.Drawing.PointF]::new([float]$coordinates[0], [float]$coordinates[1])
                })
                $graphics.FillPolygon($brush, $points)
            }
            default { throw "Unsupported SVG element: $($node.LocalName)" }
        }
        $brush.Dispose()
    }
    foreach ($size in @(256, 512)) {
        $output = [System.Drawing.Bitmap]::new($size, $size)
        $canvas = [System.Drawing.Graphics]::FromImage($output)
        $canvas.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $canvas.DrawImage($bitmap, 0, 0, $size, $size)
        $prefix = if ($theme -eq 'dark') { 'dark_' } else { '' }
        $suffix = if ($size -eq 512) { '@2x' } else { '' }
        $output.Save((Join-Path $brandDirectory "${prefix}icon${suffix}.png"), [System.Drawing.Imaging.ImageFormat]::Png)
        $canvas.Dispose()
        $output.Dispose()
    }
    $graphics.Dispose()
    $bitmap.Dispose()
}
