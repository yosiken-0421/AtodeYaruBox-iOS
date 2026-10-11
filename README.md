# あとでやる箱

「あとでやろう」を保存し、実際に終わらせるiPhoneアプリです。開発途中です。

iOS 17以降。SwiftUI、SwiftData、Vision、UserNotifications、EventKit、CoreLocation、WidgetKit、AppIntentsなどApple純正Frameworkを使用しています。

## 現在の機能と検証

箱・今日・全文検索・設定、手入力、写真・ファイル入力、端末内OCRと分類、延期・完了・履歴、Share Extension、有限の通知、カレンダー・地図、Widget、Shortcuts、場所通知のソースを実装しています。

2026年10月9日の検証（ソースcommit `300dc7f7143c3c9e6fc0615effe70bd10efb6950`）は、全5構成のDebug Build成功・Unit 76/76・UI 10/10、全86件が各1回成功し、厳密受入はPASSです。失敗・Skip・コンパイルエラー・コンパイラ警告は0です。別のRelease Simulator Buildと、署名なしのiPhoneOS/arm64 Release Archiveも成功しました。[実行記録](https://github.com/yosiken-0421/AtodeYaruBox-iOS/actions/runs/37913596688)

基本操作、Light/Darkと最大文字サイズの全種類の表示監査、実際の写真選択→Vision OCR→返品分類→保存→全文検索、Safariから実共有→保存→本体検索、通知の実配送と完了前後の取消、実ファイルの読み込み上限、App Intentの直接実行による保存・完了・画面遷移、最大文字での初回3ページをSimulatorで検証しました。通知・Intentの変更操作には端末認証を要求する設定を実装しています。「編集」「今日」からの追加は日本語付きの通常ボタンです。

2026年10月11日：版0.1.0(1)の本体・Share Extension・Widgetを署名し、TestFlightへ送信しました。Appleの受領・処理完了と内部テスト用ビルドを確認済みです。署名処理の補助70件は成功、Compile Error・コンパイラWarningは0、追加費用は0です。公開CIにはバイナリや秘密鍵を保存していません。iPhoneへのインストールと実機のWidget・Siri・位置通知・権限拒否の確認は残っています。クラウドAIとCloudKit同期は未実装・OFFです。

コンパイラ警告とは別に、Debugのテスト用ターゲットのIntentメタデータ抽出省略1件と、Release Simulatorの署名済み拡張バイナリのstrip省略2件を記録しています。署名なしiPhone用Archiveの警告は0です。検証後の変更は説明、Git除外設定、CI用のApple接続確認だけで、Swiftソース・Xcode構成・iOSテストは検証済み版と同一です。

## 自動Build/Test

GitHubの公開リポジトリで、標準のmacOS runnerを使います。全5ターゲットのBuildと全86件のUnit/UI Testを実行し、失敗・Skip・Swiftコンパイラ警告なしを必須にします。テストには生成した架空画像とlocalhostの一時ページを使用します。ログとスクリーンショットはその検証の記録です。ReleaseのSimulatorビルドは独立した証跡で検証します。合格後にiPhone用のRelease Archiveを署名なしでコンパイルし、本体・Share・Widgetの実製品を検証します。アプリのバイナリは公開しません。

Simulator用アプリは実機へのインストール用ではありません。

## Apple署名と内部配布

公開 `codemagic.yaml` はApple接続確認用で、自動トリガーや配布処理を含みません。署名と内部配布は、無料枠・本人の許可・対象アプリ・成功済みソースを照合した専用の非公開CI設定で実施しました。既存証明書と3製品のProfileを再利用し、ソース・公開ログに秘密値を保存しません。

CI用のPyJWTと暗号化ライブラリは隔離環境で使い、iPhoneアプリの依存関係には追加していません。アカウントに関する確認結果は固定長の暗号文で取得してローカルだけで復号し、平文の公開を拒否します。[接続・検証記録](Docs/CODEMAGIC_ACCESS.md)。iOSの86件とCI用補助検証は別に集計します。

## プライバシー

保存した画像・メモを端末内に保持し、OCRも端末内で行います。写真は選択したものだけを取り込み、権限は各機能を使う時に要求します。
