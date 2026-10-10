# CodemagicとAppleへの接続確認

2026-10-10：検索条件まで一致するJWTに修正後、実Macで補助18件とApple APIのGET認証が成功しました。[実際の確認結果](https://github.com/yosiken-0421/AtodeYaruBox-iOS/actions/runs/38032865143)。このアプリの3つのBundle IDは未登録、配布用証明書は0件でした。署名済みIPA・実機インストール・TestFlight送信はまだ完了していません。以下の失敗記録は解消までの経過です。

署名準備の専用モード `configure_signing_key` は、本人のアプリ所有先と無料枠30分以上、有料CI/CD契約なしを再確認した場合だけ、アプリ専用の暗号化変数グループ `atodeyarubox-signing-key-d43f7c2` にRSA 2048-bitの `CERTIFICATE_PRIVATE_KEY` を生成・保存します。秘密値はCI処理のメモリと本人のCodemagic暗号化保存先だけで扱い、Gitや診断へ出しません。既存値を上書きせず、POST結果が不明でも自動再試行しません。このモードではAppleの証明書作成・アプリ配布・課金変更は行いません。

[暗号化保存の実行結果](https://github.com/yosiken-0421/AtodeYaruBox-iOS/actions/runs/38033364264)で、この専用RSA鍵の生成とsecure=trueの保存を確認しました。値の取得・ローカル保存・公開出力はありません。次の非公開CIでは、本アプリの3つのBundle IDだけを登録し、この鍵と公開鍵が一致する配布証明書を再利用するか、なければ上限内で1件だけ作成します。既存証明書の取消は行いません。Xcodeの自動署名による本体・共有拡張・WidgetのApp GroupsとProfile設定を試し、署名付きArchiveと内部TestFlight用IPAを検証します。これは未実行の準備であり、Appleへのバイナリ送信は含みません。追加の検証を含む補助79件が成功しました。

GitHub Actions secret `CODEMAGIC_API_TOKEN` は保存済みで、対象アプリへのAPI認証は成功しています。同名secretの追加エラーは重複登録によるものです。削除や再入力は不要です。

対象は本人のPersonalアカウントにあるアプリ `6ac5b7b31811e71b67b38c2a` です。Apple接続名には先頭のASCII空白4文字がありました。このアプリだけの暗号化変数グループ `atodeyarubox-apple-alias-d43f7c2` に公開の参照名を `ASC_KEY_ALIAS` として保存し、既存のAppleキーを変更せず参照できました。[暗号化変数の確認](https://github.com/yosiken-0421/AtodeYaruBox-iOS/actions/runs/38022644416)。

2026-10-10の実Mac確認では、参照の解決、ソース取得、補助テスト13件が成功しました。その後、Appleへ通信する前のJWT署名で `JWT_SIGNING_FAILED` が発生しました。[秘密値を出さずに取得した診断](https://github.com/yosiken-0421/AtodeYaruBox-iOS/actions/runs/38031399436)。Apple API認証やアプリ署名はまだ成功していません。

この失敗への修正として、PEM、改行をエスケープしたPEM、Base64で包んだPEM、CI内のファイル参照の読み込みを追加しました。実Macで `PRIVATE_KEY_REFERENCE_REFUSED` を検出した後、Codemagicが生成する拡張子のないキーとCIユーザーのホーム・システム一時ディレクトリ内の参照に対応しました。内容や例外の文章は出力せず、形式とエラー種別の固定コードだけを診断します。使い捨ての実P256キーによるJWTの署名・検証も含め、補助テスト62件が成功しました。これはAppleの実キーによる認証成功を意味しません。

Macでの再確認は最大5分の読み取り専用処理です。開始前に現在の無料M2残量、有料CI/CD契約が無効であること、本人の所有先を再取得します。無料枠が確認できない場合や20分未満の場合は開始しません。古い画像や過去の残量を現在の値として扱いません。

ファイル参照の修正後は実Macで補助18件が成功し、Appleから `APPLE_HTTP_403` の応答を受信しました。Apple公式のJWT仕様では検索条件とfieldsもscopeの照合対象です。確認用トークンがエンドポイントだけを指定していたため、実際に使う4件のGETと検索条件を含めて一致するよう修正しました。実Apple接続の結果は別途確認し、403だけからキーの再作成や権限不足を決めつけません。

Appleへの要求は、このアプリの3つのBundle IDと配布用証明書のGETだけです。Appleリソースの作成・取消、課金設定、バイナリの配布は含みません。秘密鍵はCodemagic上の署名処理内で使用し、チャット、Git、公開ログ、保存する診断へ出しません。

手動の公開Ubuntuワークフローは `app`、`integration`、`verify_alias`、`apple_evidence` ではGETのみを使います。`configure_alias` は本人所有と無料枠を検証した場合だけ、当該アプリの新しい暗号化変数に公開の参照名を保存します。既存値の上書きや不明なPOST結果の自動再試行は行いません。APIトークン自体は個人アカウントに対応するため、コードの要求制限によってトークンの権限そのものが狭まるわけではありません。

実iOS検証済みソースは `300dc7f`、Unit 76件・UI 10件が成功しています。今回の接続修正はSwift・Xcode構成・iOSテストを変更しません。実機へのインストール、署名済みIPA、TestFlight送信は未完了です。

公式仕様：[Codemagic API認証](https://docs.codemagic.io/rest-api/codemagic-rest-api/)、[アプリAPI](https://docs.codemagic.io/rest-api/applications/)、[App Store Connect連携](https://docs.codemagic.io/yaml-publishing/app-store-connect/)、[Codemagic CLIのキー参照](https://github.com/codemagic-ci-cd/cli-tools/blob/master/docs/app-store-connect/README.md)、[GitHub Actions secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets)。
