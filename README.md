# あとでやる箱

「あとでやろう」を保存し、実際に終わらせるiPhoneアプリです。開発途中です。

iOS 17以降。SwiftUI、SwiftData、Vision、UserNotifications、EventKit、CoreLocation、WidgetKit、AppIntentsなどApple純正Frameworkを使用しています。

## 現在の機能と検証

箱・今日・全文検索・設定、手入力、写真・ファイル入力、端末内OCRと分類、延期・完了・履歴、Share Extension、有限の通知、カレンダー・地図、Widget、Shortcuts、場所通知のソースを実装しています。

2026年10月9日のSimulator検証（commit ce71a7c）は全5構成のBuild成功・コンパイラ警告0・Unit 69/69・UI 8/9、計77/78。基本操作4件、Light/Darkの表示監査、実際の写真選択→Vision OCR→返品分類→保存→全文検索、Safariから実共有→保存→本体検索→確認待ちと元URL表示が成功しました。最大文字サイズの「あとで」画面だけ文字サイズ対応の監査が未合格で、全件受入はFAILです。日時指定の独立画面は同じ実行で監査指摘なしでした。延期のボタンを修正した今回のソースは再検証待ちです。クラウドAIとCloudKit同期は未実装・OFFです。実機への署名・配布も未完了です。

## 自動Build/Test

GitHubの公開リポジトリで、標準のmacOS runnerを使います。全5ターゲットのBuildと全78件のUnit/UI Testを実行し、失敗・Skip・Swiftコンパイラ警告なしを必須にします。テストには生成した架空画像とlocalhostの一時ページを使用します。ログとスクリーンショットはその検証の記録です。

Simulator用アプリは実機へのインストール用ではありません。

## プライバシー

保存した画像・メモを端末内に保持し、OCRも端末内で行います。写真は選択したものだけを取り込み、権限は各機能を使う時に要求します。
