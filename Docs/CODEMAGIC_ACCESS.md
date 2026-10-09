# Codemagicへの読み取り接続

現在のiOS検証済みソースは `300dc7f`、Unit 76/UI 10の全86件が成功。API接続の追加はSwift・Xcode構成・iOSテストを変更しません。

AppleのキーをCodemagicへ保存する接続と、AIの実行環境からCodemagicを読む接続は別です。後者のために、本人のCodemagic API tokenをGitHubのこのリポジトリのActions secret `CODEMAGIC_API_TOKEN`へ直接保存します。本人のアカウント全体に対応する認証情報なので、このアプリの確認以外の用途へ転用しません。チャット、ソース、ログ、公開ファイルへ送らず、既存トークンのRevokeはしません。

準備した手動起動の `codemagic-read-access.yml` は、公開リポジトリのmainだけで動くUbuntuの3分上限の処理です。Mac実行やiOSビルドは開始しません。固定されたアプリ `6ac5b7b31811e71b67b38c2a` の `/apps/:id` へGETを1回行い、応答の任意の文章・名前・メール・環境変数・秘密値を保存せず、既知IDの一致と少数のbooleanだけを報告します。リダイレクト、巨大応答、未知のアプリIDでは成功しません。秘密値は当該ステップの環境からだけ取得します。

APIでアプリを読めても、Appleの認証、保存済みintegrationの参照解決、署名の成功は別で、いずれも成功と報告しません。APIのアカウント権限は確認処理そのものより広く、このコードのGET制限はトークン自体の権限を狭めるものではありません。新しいジョブ起動、アプリ変更、他アプリ読取り、Team移動、課金設定、証明書取消、秘密鍵ダウンロード、バイナリ送信はこの確認に含めません。

本人操作は、Codemagicの認証欄を開く工程と、GitHubの暗号化されたActions secretへの直接保存を一件ずつ案内します。一般のAPI説明はAccount settings > API tokenですが、本人のPersonal account settingsの画像には単独のAPI token項目がありませんでした。Codemagic自身の[公式サンプル](https://github.com/codemagic-ci-cd/white-label-demo-project)にあるPersonal Account > Integrations > Codemagic API経路を確認し、画像で見えているIntegrationsを入口に案内します。展開後の実際の項目は本人画面で確認し、表示されるまで存在を断定しません。Show/Revokeや秘密値のチャット送信は、入口の確認では依頼しません。保存後の存在確認と起動・結果確認はAIが行い、本人へテスト実行を依頼しません。保存したことをAPI認証の成功と混同しません。

公式仕様：[Codemagic API認証](https://docs.codemagic.io/rest-api/codemagic-rest-api/)、[アプリ読取りAPI](https://docs.codemagic.io/rest-api/applications/)、[GitHub Actions secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets)。
