#!/usr/bin/env bash
# UmbraCrawl autopush: commit only on change, push only if remote exists.
# Runs every 5 min via systemd user timer. Small precise messages only.
set -u
cd "/home/voidblade/SIDE PROJECT" || exit 0
LOG=".autopush.log"

files=$(git status --porcelain | awk '{print $2}' | head -8)
[ -z "$files" ] && exit 0  # nothing changed

# message is the matter only, no area prefix
n=$(echo "$files" | wc -l)
base=$(basename "$first")
if [ "$n" -eq 1 ]; then
  msg="update $base"
else
  msg="update $base +$((n - 1))"
fi
msg=$(echo "$msg" | cut -c1-72)

git add -A -q
git commit -q -m "$msg" >>"$LOG" 2>&1 || exit 0
echo "$(date -Is) committed: $msg" >>"$LOG"

# push only when a remote + upstream exist
if git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
  git push -q >>"$LOG" 2>&1 && echo "$(date -Is) pushed: $msg" >>"$LOG"
else
  echo "$(date -Is) no upstream, push skipped" >>"$LOG"
fi
