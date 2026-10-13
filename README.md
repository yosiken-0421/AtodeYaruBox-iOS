# あとでやる箱

「あとでやろう」を保存し、実際に終わらせるiPhoneアプリです。版0.2.0(2)を本人向けTestFlightへ配布済みです。

iOS 17以降。SwiftUI、SwiftData、Vision、UserNotifications、EventKit、CoreLocation、WidgetKit、AppIntentsなどApple純正Frameworkを使用しています。

## 現在の機能と検証

箱・今日・全文検索・設定、手入力、写真・ファイル入力、端末内OCRと分類、延期・完了・履歴、Share Extension、有限の通知、カレンダー・地図、Widget、Shortcuts、場所通知を実装しています。0.2.0では[項目の共有とアプリ内カレンダー](Docs/SHARING_CALENDAR.md)を追加しました。

2026年10月13日、ソース`177fc860eb69369c9a2cc66639a0d7123b4e5cbf`で全5ターゲットのDebug Build、Unit93/93・UI13/13（全106件、失敗・Skip0）、独立したRelease Simulator Build、iPhoneOS/arm64 Release Archiveが成功しました。コンパイルエラー・コンパイラ警告0です。[全件検証](https://github.com/yosiken-0421/AtodeYaruBox-iOS/actions/runs/38363619136)。

Light/Dark・最大文字サイズ・全種類のアクセシビリティ監査、実写真選択→Vision OCR→分類→保存→検索、Safari共有→保存→本体確認、通知の配送と取消、共有のプレビュー・取込、月別カレンダーの操作をSimulatorで検証しました。共有は相手へのコピーで、メモとURLは初期OFF、写真・OCR原文・通知設定は含めません。

本体・Share Extension・Widgetの署名、Appleの処理完了、既存本人用TestFlightへの0.2.0(2)追加を確認済みです。送信中の502は受信確認後の1回の再送で解消しました。署名・配布用の70件、受領・本人グループ用の28件も成功し、追加料金は0円です。旧ビルドは保持しています。秘密キーや平文の個人情報は公開せず、確認結果は明示許可に基づく暗号文で取得しています。

新しい版の実機QA、実機のWidget・Siri・位置通知・カメラの動作確認は残っています。クラウドAIとCloudKit同期は未実装・OFFです。コンパイラ警告とは別に、テスト用ターゲットのIntentメタデータ抽出省略とRelease Simulator拡張のstrip省略を検証記録に残しています。

## 自動Build/Test

GitHubの公開リポジトリで、標準のmacOS runnerを使います。全5ターゲットのBuildと全106件のUnit/UI Testを実行し、失敗・Skip・Swiftコンパイラ警告なしを必須にします。テストには生成した架空画像とlocalhostの一時ページを使用します。ログとスクリーンショットはその検証の記録です。ReleaseのSimulatorビルドは独立した証跡で検証します。合格後にiPhone用のRelease Archiveを署名なしでコンパイルし、本体・Share・Widgetの実製品を検証します。アプリのバイナリは公開しません。

Simulator用アプリは実機へのインストール用ではありません。

## Apple署名と内部配布

公開 `codemagic.yaml` はApple接続確認用で、自動トリガーや配布処理を含みません。署名と内部配布は、無料枠・本人の許可・対象アプリ・成功済みソースを照合した専用の非公開CI設定で実施しました。既存証明書と3製品のProfileを再利用し、ソース・公開ログに秘密値を保存しません。

CI用のPyJWTと暗号化ライブラリは隔離環境で使い、iPhoneアプリの依存関係には追加していません。アカウントに関する確認結果は固定長の暗号文で取得してローカルだけで復号し、平文の公開を拒否します。[接続・検証記録](Docs/CODEMAGIC_ACCESS.md)。iOSの106件とCI用補助検証は別に集計します。

## プライバシー

保存した画像・メモを端末内に保持し、OCRも端末内で行います。写真は選択したものだけを取り込み、権限は各機能を使う時に要求します。
