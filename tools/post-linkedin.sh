#!/bin/zsh
# post-linkedin.sh P-n [--dry-run] — posts one APPROVED LinkedIn post from Kamel's own account through Claude in Chrome
# (Claude headless with --chrome). Started by report-server.py when Kamel presses Approve (decision 2026-10-16).
# Prints the bot's last line: "POSTED <url>", "DRY OK" or "FAILED <reason>". Exit 0 only on POSTED / DRY OK.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
MB="/Users/kamel/elysian/marketing-brain"; PID="$1"; DRY=""; [ "$2" = "--dry-run" ] && DRY="DRY RUN: "
[[ "$PID" =~ ^P-[0-9]+$ ]] || { echo "FAILED bad post id"; exit 2; }
[ -f "$MB/live/posts/$PID.md" ] || { echo "FAILED $PID.md missing"; exit 2; }
if [ -z "$DRY" ] && ! grep -q "^- status: APPROVED" "$MB/live/posts/$PID.md"; then echo "FAILED $PID is not APPROVED"; exit 2; fi
cd "$MB" || exit 2
NOW=$(date +"%Y-%m-%d %H:%M")
PROMPT="${DRY}You are the Elysian marketing publisher's posting hand. Today is $NOW Dubai. Kamel pressed Approve on the Moon Shelter board for $PID, which is his explicit yes for this one post. Read do/post-linkedin.md and follow it exactly for live/posts/$PID.md. Use only the Claude in Chrome tools and Read. Your final output must be exactly one line: POSTED <url>, DRY OK, or FAILED <reason>."
TOOLS="Read,mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__tabs_close_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__find,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__read_page,mcp__claude-in-chrome__get_page_text,mcp__claude-in-chrome__javascript_tool,mcp__claude-in-chrome__file_upload,mcp__claude-in-chrome__browser_batch"
OUT=$(claude -p --chrome "$PROMPT" --output-format text --allowedTools "$TOOLS" < /dev/null 2>&1)
RC=$?
LAST=$(printf '%s\n' "$OUT" | grep -E '^(POSTED |DRY OK|FAILED )' | tail -1)
[ -z "$LAST" ] && LAST="FAILED no result line (exit $RC): $(printf '%s' "$OUT" | tail -c 300 | tr '\n' ' ')"
echo "$LAST"
case "$LAST" in POSTED*|"DRY OK"*) exit 0;; *) exit 1;; esac
