# CodemagicとAppleへの接続確認

共有領域の登録と3つの関連付け保存後、[実Macの照合結果](https://github.com/yosiken-0421/AtodeYaruBox-iOS/actions/runs/38040776022)で配布用Profileを3つ作成し、すべての共有権限・Team・既存証明書・期限・端末登録不要の配布用種別が一致しました。補助58件成功、証明書取り込みも成功。署名対象の識別名が`$(APP_BUNDLE_ID)`形式であることを照合処理が扱えず停止し、許可された変数だけを解決する修正と実プロジェクト生成器での回帰テストを追加しました。補助110件成功。署名済みIPAはまだ未検証です。

[Apple公式手順](https://developer.apple.com/help/account/identifiers/enable-app-capabilities/)ではApp IDを変更した後のProfile更新が必要です。古い専用Profileを残したまま、固定名の`v2`を1件ずつ作成し、既存の`v2`があれば再利用します。自動的な次版作成や削除は行いません。既存の証明書・鍵・Teamと3つのBundle ID、共有領域、期限、端末登録不要のApp Store用Profileであることを厳密に照合します。

補助110件が成功しました。[配布証明書とProfileを指定する署名方式](https://docs.codemagic.io/partials/alternative-code-signing-methods-ios/)を、CI生成の各ターゲットへ適用します。アプリのSwiftコード・既存プロジェクト生成器はネイティブ86件成功時と同一です。無料枠と有料契約なしを直前に再確認してから、修正した専用の非公開CIを最大20分で1回起動します。作成済み3つのProfileを再利用し、署名済みArchiveとIPAに含まれる本体・拡張2つを検証します。バイナリのAppleへの送信は含めません。キー再作成や追加の本人操作は現在不要です。

最新の署名処理では、IDと配布証明書の再利用、証明書のMac取り込みが成功しました。補助37件成功・Compile Error 0・コンパイラWarning 0で、ArchiveのProfile設定が停止箇所です。[実MacでのGET専用照合](https://github.com/yosiken-0421/AtodeYaruBox-iOS/actions/runs/38037634619)は補助46件とAppleへの照合が成功し、3つのIDすべてでAPP_GROUPSが有効、Profileは0件でした。共有領域そのものの登録・関連付けまではこのAPIでは確認できません。

実機登録を必要としない[配布用Profile作成API](https://developer.apple.com/documentation/appstoreconnectapi/post-v1-profiles)の経路を追加し、補助101件成功。既存の3つのIDと同じ鍵の証明書のみを使い、App Store用・正しいTeam・正しい共有領域・証明書一致を検証します。署名リソースが欠けても新しいIDや証明書を作らず、既存の専用Profileを削除・上書きせず、POST結果が不明でも再送しません。バイナリ送信は含みません。アプリ本体のネイティブ86件成功は別集計です。署名済みIPAは未検証です。

問い合わせ失敗の修正では、capabilitiesの`limit`指定がHTTP400の原因でした。[Apple公式仕様](https://developer.apple.com/documentation/appstoreconnectapi/get-v1-bundleids-_id_-bundleidcapabilities)は最大200と記載していますが、実応答を優先して指定を省くことで成功しました。必要時のGET再確認も任意パラメータをすべて省き、上限1回です。

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
