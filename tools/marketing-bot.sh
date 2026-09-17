#!/bin/zsh
# Marketing bot on Grok: Sunday market read + idea bank. Log: ~/Library/Logs/elysian-marketing-bot.log
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
cd /Users/kamel/elysian/marketing-brain || exit 1
python3 /Users/kamel/elysian/hq/tools/heartbeat.py marketing running
python3 /Users/kamel/elysian/hq/tools/grokbot.py /Users/kamel/elysian/marketing-brain do/market-analyst.md
python3 /Users/kamel/elysian/hq/tools/grokbot.py /Users/kamel/elysian/marketing-brain do/creative-director.md
RC=$?
if [ $RC -eq 0 ]; then python3 /Users/kamel/elysian/hq/tools/heartbeat.py marketing ok "analyst + ideas"; else python3 /Users/kamel/elysian/hq/tools/heartbeat.py marketing failed "exit $RC"; fi
