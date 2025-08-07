次のAIエージェント用レビュー指摘プロンプトをひとつずつ対応してください。
ただし、指摘が正しいとは限らないので規約や環境、構造などを考慮し指摘されたことをしっかり精査した上で対応可否の判断を下すこと。
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

- In mk/setup.mk at line 548, the symbolic link source path uses $(DOTFILES_DIR)/CLAUDE.md, but the actual file is located at $(DOTFILES_DIR)/claude/CLAUDE.md. Update the source path in the ln -sfn command to reflect the correct directory by changing it to $(DOTFILES_DIR)/claude/CLAUDE.md to fix the path inconsistency.

- In mk/setup.mk at line 555, before creating the symlink for claude-settings.json, add a check to verify if the file $(DOTFILES_DIR)/claude-settings.json exists. If it does not exist, output a warning message to inform the user. Only proceed with the symlink creation if the file is present.

- In mk/setup.mk around lines 558 to 559, the echoed file paths do not match the actual paths used in the link creation commands. Update the echo messages to reflect the correct file paths as per the actual file locations and link commands, ensuring consistency between displayed paths and real paths.
