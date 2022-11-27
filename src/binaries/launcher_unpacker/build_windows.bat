@echo off
tcl\windows\tclsh.exe tcl\sdx.kit wrap unpacker -runtime tcl\windows\base-tcl8.5-thread-win32-x86_64.exe

del unpacker.exe 2>nul
rename unpacker unpacker_win.exe
pause
