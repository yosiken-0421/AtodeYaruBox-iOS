# CodemagicとAppleへの接続確認

GitHub Actions secret `CODEMAGIC_API_TOKEN` は保存済みで、対象アプリへのAPI認証は成功しています。同名secretの追加エラーは重複登録によるものです。削除や再入力は不要です。

対象は本人のPersonalアカウントにあるアプリ `6ac5b7b31811e71b67b38c2a` です。Apple接続名には先頭のASCII空白4文字がありました。このアプリだけの暗号化変数グループ `atodeyarubox-apple-alias-d43f7c2` に公開の参照名を `ASC_KEY_ALIAS` として保存し、既存のAppleキーを変更せず参照できました。[暗号化変数の確認](https://github.com/yosiken-0421/AtodeYaruBox-iOS/actions/runs/38022644416)。

2026-10-10の実Mac確認では、参照の解決、ソース取得、補助テスト13件が成功しました。その後、Appleへ通信する前のJWT署名で `JWT_SIGNING_FAILED` が発生しました。[秘密値を出さずに取得した診断](https://github.com/yosiken-0421/AtodeYaruBox-iOS/actions/runs/38031399436)。Apple API認証やアプリ署名はまだ成功していません。

この失敗への修正として、PEM、改行をエスケープしたPEM、Base64で包んだPEM、許可された `.p8` ファイル参照の読み込みを追加しました。内容や例外の文章は出力せず、形式とエラー種別の固定コードだけを診断します。使い捨ての実P256キーによるJWTの署名・検証も含め、補助テスト61件が成功しました。これはAppleの実キーによる認証成功を意味しません。

Macでの再確認は最大5分の読み取り専用処理です。開始前に現在の無料M2残量、有料CI/CD契約が無効であること、本人の所有先を再取得します。無料枠が確認できない場合や20分未満の場合は開始しません。古い画像や過去の残量を現在の値として扱いません。

Appleへの要求は、このアプリの3つのBundle IDと配布用証明書のGETだけです。Appleリソースの作成・取消、課金設定、バイナリの配布は含みません。秘密鍵はCodemagic上の署名処理内で使用し、チャット、Git、公開ログ、保存する診断へ出しません。

手動の公開Ubuntuワークフローは `app`、`integration`、`verify_alias`、`apple_evidence` ではGETのみを使います。`configure_alias` は本人所有と無料枠を検証した場合だけ、当該アプリの新しい暗号化変数に公開の参照名を保存します。既存値の上書きや不明なPOST結果の自動再試行は行いません。APIトークン自体は個人アカウントに対応するため、コードの要求制限によってトークンの権限そのものが狭まるわけではありません。

実iOS検証済みソースは `300dc7f`、Unit 76件・UI 10件が成功しています。今回の接続修正はSwift・Xcode構成・iOSテストを変更しません。実機へのインストール、署名済みIPA、TestFlight送信は未完了です。

公式仕様：[Codemagic API認証](https://docs.codemagic.io/rest-api/codemagic-rest-api/)、[アプリAPI](https://docs.codemagic.io/rest-api/applications/)、[App Store Connect連携](https://docs.codemagic.io/yaml-publishing/app-store-connect/)、[Codemagic CLIのキー参照](https://github.com/codemagic-ci-cd/cli-tools/blob/master/docs/app-store-connect/README.md)、[GitHub Actions secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets)。
