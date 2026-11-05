# The after clip, the counterpart of the before clip: Claude Code with Haiku 4.5 on the three domain servers.
# It replaces the live demo: the talk shows only this recording. Real Claude Code, real tool calls,
# nothing scripted but the prompts and the approvals of the host's confirmation dialog.
# Render with media/render-after-clip.sh (Haiku 4.5, 3 takes, clean environment, per-take checks).
# Haiku 4.5 buys without asking "Rex or Bello?", so there is no "Rex" prompt.
# Same settings as media/before-clip.tape (PlaybackSpeed 2, Framerate 20, fullscreen TUI; see there).
# A write tool (buy_pet, schedule_pickup) makes the host ask: "Do you want to proceed?". After each
# prompt the tape twice waits for that dialog or the end of the turn, holds and presses Enter (approves
# a dialog; on the idle prompt it sends nothing, because prompt suggestions are off:
# CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION=false), then waits for the end of the turn ("? for shortcuts").
# The tape can't branch, so this works for zero, one or two writes per turn.

Output media/after-clip.mp4
Require claude

Set Shell bash
Set Width 1920
Set Height 1080
Set FontSize 24
Set FontFamily "JetBrains Mono, Symbola"
Set Theme "Catppuccin Mocha"
Set Padding 40
Set PlaybackSpeed 2
Set Framerate 20
Set TypingSpeed 110ms
Set WaitTimeout 120s

Hide
Type "scripts/reset-after.sh && clear && CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION=false scripts/after-claude.sh"
Enter
Wait+Screen@90s /for shortcuts/
Sleep 1s
Show
Sleep 1s

# (1) find_available_pets: Rex and Bello; the agent asks which one.
# (1) Haiku 4.5 picks Rex itself and buys him: the host asks.
Type "Buy me a friendly dog"
Sleep 400ms
Enter
Sleep 2s
Wait+Screen /proceed\?|for shortcuts/
Sleep 2s
Enter
Sleep 2s
Wait+Screen /proceed\?|for shortcuts/
Sleep 2s
Enter
Sleep 2s
Wait+Screen /for shortcuts/
Sleep 2s

# (2) The pickup: the host asks.
Type "Tuesday 10 AM"
Sleep 400ms
Enter
Sleep 2s
Wait+Screen /proceed\?|for shortcuts/
Sleep 2s
Enter
Sleep 2s
Wait+Screen /proceed\?|for shortcuts/
Sleep 2s
Enter
Sleep 2s
Wait+Screen /for shortcuts/
Sleep 2s

# (3) Rex is gone: Bello offered, no second purchase.
Type "Buy Rex for my sister too"
Sleep 400ms
Enter
Sleep 2s
Wait+Screen /proceed\?|for shortcuts/
Sleep 2s
Enter
Sleep 2s
Wait+Screen /proceed\?|for shortcuts/
Sleep 2s
Enter
Sleep 2s
Wait+Screen /for shortcuts/
Sleep 6s
Screenshot media/after-clip-done.png
Sleep 1s
