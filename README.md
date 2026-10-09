# あとでやる箱

「あとでやろう」を保存し、実際に終わらせるiPhoneアプリです。開発途中です。

iOS 17以降。SwiftUI、SwiftData、Vision、UserNotifications、EventKit、CoreLocation、WidgetKit、AppIntentsなどApple純正Frameworkを使用しています。

## 現在の機能と検証

箱・今日・全文検索・設定、手入力、写真・ファイル入力、端末内OCRと分類、延期・完了・履歴、Share Extension、有限の通知、カレンダー・地図、Widget、Shortcuts、場所通知のソースを実装しています。

2026年10月9日のSimulator検証（commit 0e9fdd4）は全5構成のBuild成功・コンパイラ警告0・Unit 69/69・UI 9/9、全78件が各1回成功し、厳密受入はPASSです。基本操作4件、Light/Darkと最大文字サイズの表示監査、実際の写真選択→Vision OCR→返品分類→保存→全文検索、Safariから実共有→保存→本体検索→確認待ちと元URL表示が成功しました。[実行記録](https://github.com/yosiken-0421/AtodeYaruBox-iOS/actions/runs/37896573653)

今回のソースでは、通知の実配送と取消、実ファイルの読み込み上限、App Intentの保存・完了・画面遷移、最大文字サイズでの初回3ページを追加し、全86件へ検証を拡張しています。通知・Intentの変更操作には端末認証を要求します。「編集」「今日」からの追加は日本語付きの通常ボタンです。追加分とReleaseビルドは再検証待ちです。クラウドAIとCloudKit同期は未実装・OFFです。実機への署名・配布も未完了です。

## 自動Build/Test

GitHubの公開リポジトリで、標準のmacOS runnerを使います。全5ターゲットのBuildと全86件のUnit/UI Testを実行し、失敗・Skip・Swiftコンパイラ警告なしを必須にします。テストには生成した架空画像とlocalhostの一時ページを使用します。ログとスクリーンショットはその検証の記録です。ReleaseのSimulatorビルドは独立した証跡で検証します。合格後にiPhone用のRelease Archiveを署名なしでコンパイルし、本体・Share・Widgetの実製品を検証します。アプリのバイナリは公開しません。

Simulator用アプリは実機へのインストール用ではありません。

## プライバシー

保存した画像・メモを端末内に保持し、OCRも端末内で行います。写真は選択したものだけを取り込み、権限は各機能を使う時に要求します。
