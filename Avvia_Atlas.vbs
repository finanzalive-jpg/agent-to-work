' ============================================
' Avvia Atlas - Launcher silenzioso
' Avvia atlas_unificato.py senza finestra console
' ============================================
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Cartella dello script
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' Cerca Python 3.12 (py launcher o python diretto)
pythonCmd = ""

' Prova py -3.12
On Error Resume Next
Set exec = WshShell.Exec("py -3.12 --version")
If Err.Number = 0 Then
    pythonCmd = "py -3.12"
End If
On Error GoTo 0

' Fallback: python diretto
If pythonCmd = "" Then
    pythonCmd = "python"
End If

' Avvia atlas_unificato.py nella cartella del progetto
WshShell.CurrentDirectory = scriptDir
WshShell.Run pythonCmd & " """ & scriptDir & "\atlas_unificato.py""", 0, False
