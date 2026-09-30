#!/bin/bash
# Set the iTerm2 background color of the session THIS agent is running in,
# not whichever tab happens to have focus.
# Usage: set-color.sh R G B   (16-bit channels, 0-65535; 0 0 0 = reset)
#
# Agent shells have no tty of their own, so walk up the process tree to the
# first ancestor attached to one (the claude / cursor-agent / agy process),
# then find the iTerm2 session that owns that tty.
set -euo pipefail

if [ $# -ne 3 ]; then
  echo "Usage: $0 R G B  (0-65535 each)" >&2
  exit 2
fi

pid=$$
tty=""
while [ "$pid" -gt 1 ]; do
  t=$(ps -o tty= -p "$pid" | tr -d ' ')
  if [ -n "$t" ] && [ "$t" != "??" ]; then
    tty="/dev/$t"
    break
  fi
  pid=$(ps -o ppid= -p "$pid" | tr -d ' ')
done

if [ -z "$tty" ]; then
  echo "No terminal found for this session (not running in a terminal window?)." >&2
  exit 1
fi

result=$(osascript - "$tty" "$1" "$2" "$3" <<'APPLESCRIPT'
on run argv
  set target to item 1 of argv
  set rgb to {(item 2 of argv) as integer, (item 3 of argv) as integer, (item 4 of argv) as integer}
  if application "iTerm" is not running then return "no-iterm"
  tell application "iTerm"
    repeat with w in windows
      repeat with t in tabs of w
        repeat with s in sessions of t
          if tty of s is target then
            set background color of s to rgb
            return "ok"
          end if
        end repeat
      end repeat
    end repeat
  end tell
  return "not-found"
end run
APPLESCRIPT
)

case "$result" in
  ok) echo "Set background of the iTerm2 session on $tty to {$1, $2, $3}." ;;
  no-iterm) echo "iTerm2 isn't running; nothing changed." >&2; exit 1 ;;
  *) echo "No iTerm2 session owns $tty (another terminal, e.g. Cursor's?); nothing changed." >&2; exit 1 ;;
esac
