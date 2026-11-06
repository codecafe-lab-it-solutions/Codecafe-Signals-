"""Create Windows Desktop Shortcut for CodeCafe Signals."""
import os
import win32com.client

shell = win32com.client.Dispatch("WScript.Shell")
desktop = shell.SpecialFolders("Desktop")
shortcut_path = os.path.join(desktop, "CodeCafe Signals Platform.lnk")

shortcut = shell.CreateShortCut(shortcut_path)
shortcut.Targetpath = os.path.abspath("Run_CodeCafe_Signals.bat")
shortcut.WorkingDirectory = os.path.abspath(".")
shortcut.Description = "CodeCafe Signals Autonomous AI Trading Platform"
shortcut.save()

print("=" * 60)
print(f"  [SUCCESS] Desktop shortcut created:")
print(f"  {shortcut_path}")
print("  You can now double-click 'CodeCafe Signals Platform' on your Desktop!")
print("=" * 60)

