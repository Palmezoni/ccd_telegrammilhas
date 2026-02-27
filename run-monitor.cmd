@echo off
setlocal
cd /d "C:\Users\palme\.openclaw\workspace\telegram-mtproto"

rem Run headless (no console window) via pythonw.
"C:\Users\palme\.openclaw\workspace\telegram-mtproto\.venv\Scripts\pythonw.exe" -u "C:\Users\palme\.openclaw\workspace\telegram-mtproto\monitor.py" --send
