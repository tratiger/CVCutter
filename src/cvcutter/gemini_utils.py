import logging
import google.generativeai as genai
from typing import Optional, Dict, Any
import json

logger = logging.getLogger(__name__)

# デフォルトモデル
DEFAULT_MODEL = "gemini-2.5-flash"

def configure_gemini(api_key: str):
    """
    Gemini APIを構成する
    """
    if not api_key:
        raise ValueError("Gemini APIキーが設定されていません。設定画面から入力してください。")
    genai.configure(api_key=api_key)

def call_gemini_api(prompt: str, file_path: Optional[str] = None, model_name: str = DEFAULT_MODEL) -> str:
    """
    Gemini APIを呼び出してテキストを生成する
    """
    try:
        model = genai.GenerativeModel(model_name)
        
        contents = [prompt]
        
        if file_path:
            # ファイル（PDF等）をアップロードして内容に含める
            logger.info(f"ファイルをアップロード中: {file_path}")
            uploaded_file = genai.upload_file(file_path)
            contents.append(uploaded_file)
            
        response = model.generate_content(contents)
        return response.text
    except Exception as e:
        logger.error(f"Gemini API呼び出しエラー: {e}")
        raise

def extract_json_from_text(text: str) -> Dict[str, Any]:
    """
    テキストからJSON部分を抽出してパースする
    """
    # JSONコードブロックを探す
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        json_str = text[start:end].strip()
    elif "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        json_str = text[start:end].strip()
    else:
        json_str = text.strip()

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"JSON解析エラー: {e}")
        logger.debug(f"解析対象テキスト: {json_str}")
        raise ValueError(f"Geminiの出力が正しいJSON形式ではありません: {e}")