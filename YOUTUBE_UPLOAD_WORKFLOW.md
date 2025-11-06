# YouTube動画アップロードワークフロー

このドキュメントでは、コンサート動画を処理してYouTubeにアップロードするまでの全体のワークフローを説明します。

## 概要

```
1. 動画録画・音声録音
   ↓
2. 動画分割・音声合成（main.py）
   ↓
3. PDFパンフレット解析（pdf_parser.py）
   ↓
4. Googleフォーム回答収集（google_form_connector.py）
   ↓
5. データマッピング（video_mapper.py）
   ↓
6. YouTubeアップロード（youtube_uploader.py）
```

---

## 事前準備

### 1. Gemini CLIのインストール

PDF解析と類似度判定にGemini CLIを使用します。

```bash
# Node.jsがインストールされている場合
npm install -g @google/generative-ai-cli

# または、Python版
pip install google-generativeai
```

Gemini CLIの設定（APIキーの登録）も必要です。詳細は公式ドキュメントを参照してください。

### 2. YouTube Data API v3の設定

1. [Google Cloud Console](https://console.cloud.google.com/)でプロジェクトを作成
2. YouTube Data API v3を有効化
3. OAuth 2.0クライアントID（デスクトップアプリ）を作成
4. `client_secrets.json`をダウンロードし、このディレクトリに配置

### 3. 必要なPythonライブラリのインストール

```bash
pip install -r requirements.txt
```

### 4. Googleフォームの作成

演奏者に回答してもらうGoogleフォームを作成します。

**推奨される質問項目:**

1. **お名前**（必須、記述式）
2. **動画に氏名を表示しますか**（必須、選択式）
   - 表示する
   - 表示しない（匿名）
3. **演奏された曲名を入力してください**（必須、記述式）
   - 例：ショパン ノクターン第2番
4. **公開設定**（必須、選択式）
   - 公開（誰でも検索・閲覧可能）
   - 限定公開（URLを知っている人のみ閲覧可能）
   - 非公開（本人のみ閲覧可能）
5. **動画の説明文に追加したい内容**（任意、記述式）

フォーム作成後、演奏者に回答を依頼します。

---

## ワークフロー

### ステップ1: 動画の分割と音声合成

既存の`main.py`を使用して、録画した動画を演奏ごとに分割し、外部マイク音声と合成します。

```bash
python main.py
```

処理後、`output/`ディレクトリに分割された動画ファイルが作成されます。

### ステップ2: PDFパンフレットの解析

コンサートのプログラムが記載されたPDFパンフレットを解析し、演奏順序・演奏者名・曲名を抽出します。

```bash
python pdf_parser.py path/to/concert_program.pdf --output program_data.json
```

**出力例: `program_data.json`**

```json
{
  "concert_info": {
    "title": "2025年春季ピアノコンサート",
    "date": "2025年3月15日",
    "venue": "〇〇ホール"
  },
  "performances": [
    {
      "program_order": 1,
      "performer_name": "山田太郎",
      "piece_title": "フレデリック・ショパン ノクターン第2番 変ホ長調 Op.9-2",
      "piece_composer": "フレデリック・ショパン"
    },
    {
      "program_order": 2,
      "performer_name": "佐藤花子",
      "piece_title": "ルートヴィヒ・ヴァン・ベートーヴェン ピアノソナタ第14番「月光」第1楽章",
      "piece_composer": "ルートヴィヒ・ヴァン・ベートーヴェン"
    }
  ]
}
```

### ステップ3: Googleフォーム回答の取得

演奏者からの回答を収集します。

#### 方法A: CSVエクスポート（推奨）

1. Googleフォームの回答ページを開く
2. 「回答」タブ → 右上の「...」メニュー → 「回答をダウンロード（.csv）」
3. ダウンロードしたCSVファイルを保存

```bash
python google_form_connector.py form_responses.csv --output form_data.json
```

**出力例: `form_data.json`**

```json
{
  "export_time": "2025-03-15T15:00:00",
  "response_count": 3,
  "responses": [
    {
      "response_id": 1,
      "timestamp": "2025/03/15 14:25:30",
      "name": "山田太郎",
      "display_name": true,
      "piece_title": "ショパン ノクターン2番",
      "privacy": "unlisted",
      "description_extra": ""
    },
    {
      "response_id": 2,
      "timestamp": "2025/03/15 14:28:15",
      "name": "佐藤花子",
      "display_name": true,
      "piece_title": "ベートーヴェン 月光ソナタ 第1楽章",
      "privacy": "public",
      "description_extra": "初めての発表会で緊張しましたが、楽しく演奏できました。"
    }
  ]
}
```

### ステップ4: データマッピング

PDF情報、動画ファイル、アンケート回答を統合し、YouTubeアップロード用のメタデータを生成します。

```bash
python video_mapper.py \
  --program-json program_data.json \
  --form-json form_data.json \
  --video-dir output \
  --output upload_metadata.json
```

**処理内容:**

1. **動画ファイルのソート**: `output/`ディレクトリ内の動画を作成時刻順にソート
2. **プログラム→動画の紐付け**: PDFのprogram_orderと動画の時系列順で対応付け
3. **アンケートとの照合**: 曲名+演奏者名でGemini CLIを使って類似度判定
4. **メタデータ生成**: アンケート回答があるもののみ、YouTube用のメタデータを生成

**出力例: `upload_metadata.json`**

```json
{
  "videos": [
    {
      "title": "ショパン ノクターン第2番 変ホ長調 Op.9-2 - 山田太郎",
      "description": "2025年春季ピアノコンサートでの演奏\n演奏者: 山田太郎\n曲名: ショパン ノクターン第2番...",
      "tags": ["ピアノ", "クラシック", "コンサート", "ショパン"],
      "privacy_status": "unlisted",
      "playlist_id": ""
    },
    {
      "title": "ベートーヴェン ピアノソナタ第14番「月光」第1楽章 - 佐藤花子",
      "description": "2025年春季ピアノコンサートでの演奏\n演奏者: 佐藤花子\n...",
      "tags": ["ピアノ", "クラシック", "コンサート", "ベートーヴェン"],
      "privacy_status": "public",
      "playlist_id": ""
    }
  ]
}
```

**注意:**
- アンケート回答がない演奏は除外されます
- 曲名や演奏者名の表記揺れは、Gemini CLIが自動判定します
- マッピングの詳細は`video_mapping_result.json`に保存されます

### ステップ5: YouTubeへのアップロード

生成されたメタデータを使用して、動画をYouTubeにアップロードします。

```bash
python youtube_uploader.py --video-dir output --metadata upload_metadata.json
```

**処理内容:**

1. 初回実行時、ブラウザが開いてOAuth認証が行われます
2. 動画を順次アップロード（進捗表示あり）
3. 6本アップロード後、自動的に24時間待機
4. エラーが発生した動画はスキップして続行
5. アップロード履歴を`upload_state.json`に保存

**ログファイル**: `logs/youtube_upload.log`

---

## トラブルシューティング

### 動画数とプログラム数が一致しない

- **原因**: プログラムの順番が変更された、または一部の演奏が録画されていない
- **対応**: `video_mapper.py`実行時に警告が表示されます。`video_mapping_result.json`を確認し、手動で調整が必要な場合は`upload_metadata.json`を編集してください

### アンケート回答がマッチしない

- **原因**: 曲名や演奏者名の表記が大きく異なる
- **対応**:
  1. `video_mapping_result.json`でマッチング結果を確認
  2. Gemini CLIの判定が不正確な場合、アンケート回答者に表記を確認
  3. または、`upload_metadata.json`を手動編集

### Gemini CLIがエラーを返す

- **原因**: APIキーの設定不備、または利用制限
- **対応**:
  1. `gemini --version`でCLIが正しくインストールされているか確認
  2. APIキーが正しく設定されているか確認
  3. 簡易マッチングを使用: `python video_mapper.py --no-gemini ...`

### YouTubeアップロードが失敗する

- **原因**:
  - ネットワークエラー
  - 動画ファイルの破損
  - YouTube APIのクォータ超過
- **対応**:
  1. ログファイル（`logs/youtube_upload.log`）を確認
  2. 失敗した動画はスキップされ、次の動画に進みます
  3. `upload_state.json`でアップロード履歴を確認

---

## ファイル構成

```
movieCutter/
├── main.py                          # 動画分割・音声合成（既存）
├── pdf_parser.py                    # PDFパンフレット解析
├── google_form_connector.py         # Googleフォーム回答取得
├── video_mapper.py                  # データマッピング
├── youtube_uploader.py              # YouTubeアップロード
│
├── client_secrets.json              # OAuth認証情報（要取得）
├── token.pickle                     # 認証トークンキャッシュ（自動生成）
├── upload_state.json                # アップロード状態（自動生成）
│
├── program_data.json                # PDF解析結果
├── form_data.json                   # アンケート回答
├── upload_metadata.json             # YouTube用メタデータ
├── video_mapping_result.json        # マッピング詳細
│
├── sample_form_responses.csv        # サンプルCSV
├── YOUTUBE_UPLOAD_WORKFLOW.md       # このファイル
│
├── input/                           # 入力動画・音声
├── output/                          # 処理済み動画（分割後）
├── temp/                            # 一時ファイル
└── logs/                            # ログファイル
    └── youtube_upload.log
```

---

## 補足: Gemini CLIを使わない場合

簡易的な文字列マッチングを使用する場合:

```bash
python video_mapper.py \
  --program-json program_data.json \
  --form-json form_data.json \
  --video-dir output \
  --output upload_metadata.json \
  --no-gemini
```

この場合、曲名と演奏者名の部分一致でマッチングを行います。表記揺れが大きい場合は正確性が低下する可能性があります。

---

## 今後の改善案

1. **GUI統合**: main.pyに各処理を統合し、GUIから一括実行
2. **リアルタイムプレビュー**: マッピング結果を動画と共にプレビュー
3. **バッチ処理の自動化**: 全ステップを一度に実行するスクリプト
4. **Google Sheets API連携**: フォーム回答を自動取得
5. **サムネイル自動生成**: 動画から自動的にサムネイルを抽出

---

## サポート

質問や問題が発生した場合は、ログファイルを確認してください：
- `logs/youtube_upload.log` - YouTubeアップロードのログ
- 各スクリプト実行時の標準出力

詳細なデバッグ情報が必要な場合は、環境変数を設定してログレベルを変更できます：

```bash
# デバッグログを有効化
export PYTHONUNBUFFERED=1
python video_mapper.py ... 2>&1 | tee mapping_debug.log
```
