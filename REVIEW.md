次のAIエージェント用レビュー指摘プロンプトをひとつずつ対応してください。
ただし、指摘が正しいとは限らないので規約や環境、構造などを考慮し指摘されたことをしっかり精査した上で対応可否の判断を下すこと。

**重要**: 現在のPhase/ステップでは対応しないが将来対応予定の指摘については、@coderabbitaiに記憶を依頼してください。

最後に対応不要と判断したプロンプトに関してはその書き出しと、対応不要と判断した理由を下記のように出力してください。
例）
```
1. In backend-auth/server.js around line 44,
    - 開発・ローカル環境ではMemoryStoreで十分。本番環境では別途Redis/MongoDBを使用するべきですが、この段階では不要。

2. In backend-auth/server.js around lines 127 to 163,
    - シンプルな開発用認証サーバーでは、HTMLのインライン埋め込みは許容範囲。テンプレートエンジンの導入は複雑性を増すだけ。

...
```

対応が全て終わったらGitにコミット・プッシュを行ってください。

# Prompt For AI Agents List

- In scripts/install.sh around lines 265 to 273, the interactive read can fail (EOF/Ctrl-D) under set -e and terminate the script; change the read handling to avoid exiting on failure by capturing read's exit and treating empty or failed reads as a negative response. Concretely, run the read in a guarded way (e.g. temporarily disable errexit or append "|| REPLY=''" to the read, or use "if ! read -r ...; then REPLY=''; fi"), then test REPLY against ^[Yy]$ and only remove CONFIG_DIR when it matches, otherwise log that it was kept.

- In scripts/install.sh around lines 279 to 289, the interactive read prompting to remove Lazygit AI Commit Generator settings must be guarded for non-interactive runs; only prompt when stdin is a TTY and otherwise default to "no". Modify the block so you first check if stdin is a terminal (e.g., [ -t 0 ]), perform read -p only when true, and set REPLY="N" (or equivalent default) when not a TTY; keep the backup, sed removal, and log behavior unchanged but only execute them when REPLY matches ^[Yy]$.

- In src/gemini_client.sh around lines 90 to 101 (and also update usages at ~140 and ~252), add a portable timeout command detection at the top of the script that sets a variable (e.g. timeout_cmd) to 'timeout' if available, otherwise to 'gtimeout' if available, and fail with a clear error if neither exists; then replace direct calls to timeout in the noted locations with the detected variable (e.g. "$timeout_cmd" ...) so macOS Homebrew gtimeout is used when present and Linux timeout remains unchanged.

- In src/ui_helper.sh around lines 16 to 23, remove the unnecessary here-string and duplicate load_config call: delete the config=$(load_config) assignment and the <<< "$config" on the get_config_value call so it becomes show_spinner=$(get_config_value ".ui.show_spinner" "true"), and adjust the surrounding logic accordingly; apply the same change in the show_confirmation implementation so you don't call load_config twice and avoid passing a useless heredoc to get_config_value.

- In src/ui_helper.sh around lines 27 to 39, the spinner currently writes to stdout and doesn't hide/restore the cursor; change it to hide the cursor before starting (e.g. tput civis or ESC sequence), run the spinner loop printing to stderr (redirect printf/sleep output to >&2) in the background, capture its PID in SPINNER_PID, and ensure you restore the cursor (tput cnorm or ESC) and kill the spinner on exit (use a trap or ensure callers restore on stop) so spinner output won't mix with command stdout and the terminal cursor is always restored.

- In src/ui_helper.sh around lines 41 to 50, stop_spinner currently kills and waits for the spinner process but does not reliably clear the current line or restore the cursor visibility; update stop_spinner to, after killing/waiting and before logging, clear the line (e.g. overwrite with a carriage return plus ANSI clear-line sequence) and restore cursor visibility (use tput cnorm if available, otherwise emit the ANSI show-cursor sequence), then reset SPINNER_PID and log; ensure these extra steps run unconditionally when a spinner was running so the UI is restored even if cleanup_ui is not called.