param($docx, $pdf)
$w = New-Object -ComObject Word.Application
$w.Visible = $false; $w.DisplayAlerts = 0
$d = $w.Documents.Open($docx)
foreach ($t in $d.TablesOfContents) { $t.Update() }
$d.Fields.Update() | Out-Null
foreach ($t in $d.TablesOfContents) { $t.Update() }
$d.Save()
$d.ExportAsFixedFormat($pdf, 17)
"pages: " + $d.ComputeStatistics(2)
$d.Close(); $w.Quit()
