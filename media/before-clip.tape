# The before clip for the talk hook: Claude Code with Haiku 4.5 on the wrapped Petstore "succeeds wrongly".
# Real Claude Code, real tool calls, the evaluation's data; nothing scripted but the three prompts.
# The customer answers (CUSTOMER=answers: no appended system prompt), like in the after clip.
# (2) shows that Rex and Bello were in the shop all along; the answer to (3) shows nothing was bought.
# Render with media/render-before-clip.sh (Haiku 4.5, 3 takes, clean environment, per-take checks).
# The model's answers vary per take; the evaluation (eval.py, 5 runs) holds the numbers.
# Run from the repo root. PlaybackSpeed 2: every Sleep shows for half its time. Framerate 20:
# capture keeps up at 1080p (at the default 50 fps frames are dropped and the clip runs too fast).
# Claude Code runs fullscreen (stage-before settings): the alternate screen has no scrollback, so
# VHS's screen text is what is visible. A turn is over when the footer says "? for shortcuts"
# again ("esc to interrupt" while working).

Output media/before-clip.mp4
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
Type "scripts/reset-before.sh && clear && CUSTOMER=answers scripts/before-claude.sh"
Enter
Wait+Screen@90s /for shortcuts/
Sleep 1s
Show
Sleep 1s

# (1) The purchase: findPets... -> placeOrder -> "done".
Type "Buy me a friendly dog"
Sleep 400ms
Enter
Sleep 2s
Wait+Screen /for shortcuts/
Sleep 4s
# After the hold: a screenshot right after the wait can show a frame from just before it.
Screenshot media/before-clip-done.png

# (2) Is Rex still for sale?
Type "Which friendly dogs are available?"
Sleep 400ms
Enter
Sleep 2s
Wait+Screen /for shortcuts/
Sleep 4s

# (3) Only a human asking makes the agent check. The clip ends here: the answer shows what went wrong.
Type "Did the order go through? Was the dog actually bought?"
Sleep 400ms
Enter
Sleep 2s
Wait+Screen /for shortcuts/
Sleep 6s
