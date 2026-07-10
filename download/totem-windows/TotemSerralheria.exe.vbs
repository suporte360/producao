' Para ter um icone de executavel, renomeie este arquivo para .exe
' Exemplo: renomeie "TotemSerralheria.exe.vbs" para "TotemSerralheria.exe"
' OBS: Windows permite renomear .vbs para .exe e ele continua funcionando com duplo-clique
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "TotemSerralheria.bat", 0, False