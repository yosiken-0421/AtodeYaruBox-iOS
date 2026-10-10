# CodemagicとAppleへの接続確認

最新の実Macでは、IDと配布証明書の再利用、証明書のMac取り込みが成功しました。補助37件成功・Compile Error 0・コンパイラWarning 0で、ArchiveのApp Groups設定が停止箇所です。設定とProfileを読み取り専用で照合する処理を追加し、補助94件が成功しました。この検証ではAppleへの書き込みや追加ビルドを行わず、共有領域の設定が不足する箇所だけを集計します。アプリ本体のネイティブ86件成功は別集計です。

2026-10-10：Apple API認証に続き、このアプリ用の3つのBundle IDと配布用証明書を作成しました。[秘密値を出さずに取得した署名準備の実結果](https://github.com/yosiken-0421/AtodeYaruBox-iOS/actions/runs/38035015291)。公開鍵の一致とTeam IDは検証済みです。Macへの証明書取り込みで停止したため、[cryptography公式のmacOS互換形式](https://cryptography.io/en/50.0.2/hazmat/primitives/asymmetric/serialization/)へ修正しました。再確認で作成済みIDの検索判定が停止し、本体と拡張をまとめた結果から完全一致するIDだけを選ぶよう修正しました。別アプリのIDや完全一致の重複は拒否します。補助88件成功、アプリのネイティブ86件成功は別集計です。署名済みIPA・実機インストール・TestFlight送信は未完了です。

署名準備の専用モード `configure_signing_key` は、本人のアプリ所有先と無料枠30分以上、有料CI/CD契約なしを再確認した場合だけ、アプリ専用の暗号化変数グループ `atodeyarubox-signing-key-d43f7c2` にRSA 2048-bitの `CERTIFICATE_PRIVATE_KEY` を生成・保存します。秘密値はCI処理のメモリと本人のCodemagic暗号化保存先だけで扱い、Gitや診断へ出しません。既存値を上書きせず、POST結果が不明でも自動再試行しません。このモードではAppleの証明書作成・アプリ配布・課金変更は行いません。

[暗号化保存の実行結果](https://github.com/yosiken-0421/AtodeYaruBox-iOS/actions/runs/38033364264)で、専用RSA鍵の生成とsecure=trueの保存を確認しました。次の非公開CIは作成済みのIDと同じ鍵に一致する証明書を再利用し、本体・共有拡張・Widgetの署名を進めます。使い捨てCI内の互換形式P12はランダムなパスフレーズで暗号化し、鍵・P12をArtifactやGitへ出しません。Appleへのバイナリ送信は含みません。

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
