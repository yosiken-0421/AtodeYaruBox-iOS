# Codemagicへの読み取り接続

2026-10-10：暗号化されたActions secretの保存と、既存アプリのGETによる認証成功を確認しました。[実行記録](https://github.com/yosiken-0421/AtodeYaruBox-iOS/actions/runs/37976837550)。Appleの認証や署名の成功とは区別します。秘密値・任意の応答テキストは保存しません。

追加の[所属先・登録名の確認](https://github.com/yosiken-0421/AtodeYaruBox-iOS/actions/runs/37978005029)は成功。アプリは本人のPersonalアカウントに所属し、Apple接続は有効でした。保存名は `AtodeYaruBox-CI` と完全一致せず、Unicode表記の正規化と外側の空白除去を行うと一致します。所属の取り違えとは扱いません。既知のこの名前へ正規化できる唯一の保存名だけ、64文字以下・制御文字なしを条件に文字番号として取得し、ビルド側の参照を正確な保存名へ合わせます。任意の登録名、メール、所属ID、Key IDや秘密値は取得結果へ出しません。Appleキーの取消・再作成は不要です。

手動確認に `integration` モードを追加しました。既知のアプリ（必要な場合のみ既知の失敗ビルド）から所有アカウントを検証してから、本人の接続設定と当該アプリの所属先の接続設定を読みます。保存された `AtodeYaruBox-CI` の完全一致・空白等を除いた一致だけをbooleanで比較し、名前・メール・所属ID・Apple Key ID・秘密値は結果に残しません。どの処理もGETのみです。アプリの所属が不明なまま別のTeamへ問い合わせず、他アプリの取得や設定変更、Mac実行、署名、配布は行いません。現在のCodemagic公開Webアプリにある `/user`、`/team/:id`、`/builds/:id` のGETと所有先による参照切替を根拠とし、実APIの応答が検証できない場合は成功にしません。補助22件が成功しました。

現在のiOS検証済みソースは `300dc7f`、Unit 76/UI 10の全86件が成功。API接続の追加はSwift・Xcode構成・iOSテストを変更しません。

AppleのキーをCodemagicへ保存する接続と、AIの実行環境からCodemagicを読む接続は別です。後者のために、本人のCodemagic API tokenをGitHubのこのリポジトリのActions secret `CODEMAGIC_API_TOKEN`へ直接保存します。本人のアカウント全体に対応する認証情報なので、このアプリの確認以外の用途へ転用しません。チャット、ソース、ログ、公開ファイルへ送らず、既存トークンのRevokeはしません。

準備した手動起動の `codemagic-read-access.yml` は、公開リポジトリのmainだけで動くUbuntuの3分上限の処理です。Mac実行やiOSビルドは開始しません。固定されたアプリ `6ac5b7b31811e71b67b38c2a` の `/apps/:id` へGETを1回行い、応答の任意の文章・名前・メール・環境変数・秘密値を保存せず、既知IDの一致と少数のbooleanだけを報告します。リダイレクト、巨大応答、未知のアプリIDでは成功しません。秘密値は当該ステップの環境からだけ取得します。

APIでアプリを読めても、Appleの認証、保存済みintegrationの参照解決、署名の成功は別で、いずれも成功と報告しません。APIのアカウント権限は確認処理そのものより広く、このコードのGET制限はトークン自体の権限を狭めるものではありません。新しいジョブ起動、アプリ変更、他アプリ読取り、Team移動、課金設定、証明書取消、秘密鍵ダウンロード、バイナリ送信はこの確認に含めません。

本人操作は、Codemagicの認証欄を開く工程と、GitHubの暗号化されたActions secretへの直接保存を一件ずつ案内します。現在の入口は[Account settings](https://codemagic.io/settings)のAPI token欄です。2026-10-10、一般公開されている現在のWebアプリのナビゲーション、/settingsへのルート、該当画面のAPI token表示を照合しました。メニューのSettingsはPersonal/Teamの設定へ移動するため、認証欄には直接URLを使います。本人画像ではPersonal account settingsにも、そのIntegrations内にもAPI tokenがなく、旧サンプルのIntegrations経路は現在の入口として使いません。本人のログイン済み端末での表示はまだ未確認です。Show/Revokeや秘密値のチャット送信は、入口の確認では依頼しません。保存後の存在確認と起動・結果確認はAIが行い、本人へテスト実行を依頼しません。保存したことをAPI認証の成功と混同しません。

公式仕様：[Codemagic API認証](https://docs.codemagic.io/rest-api/codemagic-rest-api/)、[アプリ読取りAPI](https://docs.codemagic.io/rest-api/applications/)、[GitHub Actions secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets)。
