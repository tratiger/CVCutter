# Google Forms API 使用ガイド

このガイドでは、Google Forms APIを使用してフォームの作成と回答取得を行う方法を説明します。

## 概要

このプロジェクトでは、以下の2つのスクリプトでForms APIを使用します：

1. **create_google_form.py** - Googleフォームの自動作成
2. **google_form_connector.py** - フォーム回答の自動取得

Forms APIを使用することで、CSVファイルの手動エクスポートが不要になり、完全自動化されたワークフローを実現できます。

---

## 事前準備

### 1. Google Cloud Consoleでの設定

#### A. プロジェクトの作成
1. [Google Cloud Console](https://console.cloud.google.com/)にアクセス
2. 新しいプロジェクトを作成（または既存のプロジェクトを選択）

#### B. APIの有効化
以下のAPIを有効化してください：

1. **Google Forms API**
   - 左メニュー → 「APIとサービス」 → 「ライブラリ」
   - "Google Forms API"を検索して有効化

2. **YouTube Data API v3**（動画アップロード用）
   - 同様に検索して有効化

#### C. OAuth 2.0クライアントIDの作成

1. 左メニュー → 「APIとサービス」 → 「認証情報」
2. 「認証情報を作成」 → 「OAuth クライアント ID」
3. アプリケーションタイプ: **「デスクトップアプリ」**
4. 名前: 任意（例: "Concert Video Uploader"）
5. 「作成」をクリック
6. **client_secrets.json**をダウンロード
7. ダウンロードしたファイルを`movieCutter/`ディレクトリに配置

### 2. スコープの設定

このプロジェクトで使用するスコープ：

```
Forms API用:
- https://www.googleapis.com/auth/forms.body
- https://www.googleapis.com/auth/forms.responses.readonly

YouTube API用:
- https://www.googleapis.com/auth/youtube.upload
```

OAuth同意画面で、これらのスコープが含まれていることを確認してください。

---

## 使用方法

### ステップ1: Googleフォームの作成

```bash
python create_google_form.py
```

**実行内容:**
1. 初回実行時、ブラウザが開いてOAuth認証を求められます
2. Googleアカウントでログイン
3. アプリケーションの権限を承認
4. フォームが自動作成されます

**出力:**
```
【演奏者に送るURL】
https://docs.google.com/forms/d/FORM_ID/viewform

【フォーム編集URL】
https://docs.google.com/forms/d/FORM_ID/edit
```

**自動作成される質問項目:**
1. お名前（必須、記述式）
2. 動画に氏名を表示しますか（必須、選択式）
3. 演奏された曲名（必須、記述式）
4. 公開設定（必須、選択式）
5. 追加の説明文（任意、段落テキスト）

**保存されるファイル:**
- `form_config.json` - フォームIDとURLを保存
- `forms_token.pickle` - 認証トークンをキャッシュ

**回答URLの配布:**
出力された回答URLを演奏者に送信してください。

### ステップ2: フォーム回答の取得

#### A. デフォルト実行（form_config.jsonから自動取得）

```bash
python google_form_connector.py --use-api
```

または引数なしで実行（form_config.jsonが存在する場合）:

```bash
python google_form_connector.py
```

#### B. 特定のフォームIDを指定

```bash
python google_form_connector.py --form-id YOUR_FORM_ID --use-api
```

#### C. CSVファイルから取得（従来の方法）

```bash
python google_form_connector.py form_responses.csv
```

**出力:**
- `form_responses.json` - 回答データ（JSON形式）

---

## 統合ワークフローでの使用

### デフォルト実行（Forms API使用）

```bash
python run_youtube_workflow.py --pdf concert_program.pdf
```

`form_config.json`が存在する場合、自動的にForms APIから回答を取得します。

### 特定のフォームIDを指定

```bash
python run_youtube_workflow.py \
  --pdf concert_program.pdf \
  --form-id YOUR_FORM_ID
```

### CSVファイルから取得

```bash
python run_youtube_workflow.py \
  --pdf concert_program.pdf \
  --form-csv responses.csv \
  --use-csv
```

---

## 認証フロー

### 初回認証

1. スクリプト実行時に自動的にブラウザが開きます
2. Googleアカウントでログイン
3. 以下の権限を承認:
   - フォームの作成と編集
   - フォーム回答の読み取り
4. 認証トークンが`forms_token.pickle`に保存されます

### 2回目以降

保存された認証トークンが自動的に使用されるため、ブラウザ認証は不要です。

### トークンの有効期限

トークンの有効期限が切れた場合、自動的にリフレッシュトークンを使用して更新されます。

### トークンのリセット

認証をやり直したい場合は、以下のファイルを削除してください：

```bash
rm forms_token.pickle
```

---

## トラブルシューティング

### エラー: "client_secrets.jsonが見つかりません"

**原因:** OAuth 2.0クライアントIDがダウンロードされていません

**対処:**
1. Google Cloud Consoleから`client_secrets.json`をダウンロード
2. `movieCutter/`ディレクトリに配置

### エラー: "Forms APIエラー: 403"

**原因:** Google Forms APIが有効化されていません

**対処:**
1. Google Cloud Consoleで「APIとサービス」→「ライブラリ」
2. "Google Forms API"を検索して有効化

### エラー: "form_config.jsonが見つかりません"

**原因:** フォームがまだ作成されていません

**対処:**
```bash
python create_google_form.py
```

### 回答が取得できない

**原因1:** フォームに回答がまだ送信されていません

**対処:** 演奏者にフォームURLを送信し、回答を依頼してください

**原因2:** フォームIDが間違っています

**対処:** `form_config.json`に記載されているフォームIDを確認してください

### 既存のフォームを使用したい

**手動でform_config.jsonを作成:**

```json
{
  "form_id": "YOUR_EXISTING_FORM_ID",
  "form_title": "Your Form Title",
  "response_url": "https://docs.google.com/forms/d/YOUR_FORM_ID/viewform"
}
```

フォームIDは、フォームURLの`/d/`と`/edit`の間の文字列です：
```
https://docs.google.com/forms/d/【ここがフォームID】/edit
```

---

## Forms APIの利点

### CSVエクスポートと比較

| 項目 | Forms API | CSVエクスポート |
|------|-----------|----------------|
| 自動化 | ✅ 完全自動 | ❌ 手動操作が必要 |
| リアルタイム性 | ✅ 最新の回答を即座に取得 | ❌ 手動でエクスポートが必要 |
| 統合性 | ✅ ワークフローに統合可能 | ❌ 別途ダウンロードが必要 |
| エラー削減 | ✅ ファイル操作ミスなし | ❌ ファイル名や配置ミスの可能性 |
| スケジューリング | ✅ cron等で自動実行可能 | ❌ 人間の操作が必要 |

### 推奨される使用方法

**本番環境:** Forms APIを使用（完全自動化）

**開発/テスト:** CSVファイルも使用可能（動作確認やデバッグ用）

---

## セキュリティに関する注意

### 認証情報の保護

以下のファイルは秘密情報を含むため、Gitにコミットしないでください：

```
client_secrets.json
forms_token.pickle
token.pickle
form_config.json（フォームIDが外部に漏れないようにする場合）
```

`.gitignore`に追加してください：

```
# 認証情報
client_secrets.json
*_token.pickle
token.pickle

# APIキー・ID
form_config.json
upload_state.json
```

### フォームの公開範囲

作成されたフォームは、デフォルトで「リンクを知っている人のみ回答可能」に設定されています。演奏者にのみURLを共有し、一般公開しないでください。

---

## API利用制限

### Forms APIのクォータ

Google Forms APIには以下の制限があります：

- **読み取り:** 1分あたり300リクエスト
- **書き込み:** 1分あたり100リクエスト

通常の使用では、これらの制限に達することはほぼありません。

### エラー429への対応

万が一"Too Many Requests"エラーが発生した場合、スクリプトは自動的にリトライします。

---

## よくある質問

### Q1. 既存のフォームに質問を追加できますか？

A1. `create_google_form.py`は新規フォームのみ作成します。既存フォームへの質問追加は、Googleフォームのウェブインターフェースから手動で行ってください。

### Q2. フォームのデザインをカスタマイズできますか？

A2. Forms APIではデザインのカスタマイズに制限があります。フォーム作成後、Googleフォームのウェブインターフェースからテーマや色を変更してください。

### Q3. 複数のフォームを管理できますか？

A3. はい。`--form-id`オプションで異なるフォームIDを指定することで、複数のフォームを管理できます。

### Q4. フォームの回答を削除できますか？

A4. Forms APIの読み取り専用スコープでは回答の削除はできません。Googleフォームのウェブインターフェースから手動で削除してください。

---

## さらなる情報

- [Google Forms API公式ドキュメント](https://developers.google.com/forms/api)
- [OAuth 2.0認証ガイド](https://developers.google.com/identity/protocols/oauth2)
- [YouTube Data API v3ガイド](https://developers.google.com/youtube/v3)
