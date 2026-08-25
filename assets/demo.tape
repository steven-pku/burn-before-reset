# Regenerate with: vhs assets/demo.tape  (run from the repository root)
# Demo sources live under /Users/Shared/bbr-demo (notes + git repo), see README quick start.
Output assets/demo.gif

Set FontSize 24
Set Width 1200
Set Height 640
Set Padding 24
Set TypingSpeed 25ms

Type "# plan-only quick start: config.local.toml points at a notes folder and a git repo"
Enter
Sleep 800ms
Type "python3 scripts/bbr.py validate-config --config config.local.toml"
Enter
Sleep 2s
Type "python3 scripts/bbr.py plan --config config.local.toml"
Enter
Sleep 2.5s
Type "ls /Users/Shared/bbr-demo/runs/run-*/"
Enter
Sleep 3.5s
