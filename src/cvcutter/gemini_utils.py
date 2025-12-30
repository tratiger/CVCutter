import os
import sys
import subprocess
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def get_node_bundle_paths():
    """
    同梱された Node.js フォルダのパスを特定し、必要なバイナリのパスを返す
    """
    if getattr(sys, 'frozen', False):
        base_path = Path(sys._MEIPASS)
    else:
        # プロジェクトルート (c:/Users/trati/development/CVCutter)
        base_path = Path(__file__).parent.parent.parent
    
    # 同梱フォルダ名
    node_dir = base_path / "node-v24.12.0-win-x64"
    
    # 開発環境やEXE実行時のパス解決（実行ファイルと同じ階層にある場合も考慮）
    if not node_dir.exists():
        exe_dir = Path(sys.executable).parent
        node_dir = exe_dir / "node-v24.12.0-win-x64"

    if not node_dir.exists():
        raise FileNotFoundError(f"Node.js bundle directory not found at {node_dir}")

    node_exe = node_dir / "node.exe"
    # npx 経由ではなく、直接バイナリまたは JS を叩く
    gemini_cmd = node_dir / "node_modules" / ".bin" / "gemini.cmd"
    gemini_js = node_dir / "node_modules" / "@google" / "gemini-cli" / "dist" / "src" / "gemini.js"
    
    return node_dir, node_exe, gemini_cmd, gemini_js

def run_gemini_cli(args, capture_output=True, interactive=False):
    """
    環境変数を強制的に上書きし、同梱された Node.js を使用して gemini-cli を実行する
    """
    try:
        node_dir, node_exe, gemini_cmd, gemini_js = get_node_bundle_paths()
        
        # 環境変数の構築
        env = os.environ.copy()
        
        # 1. PATHの先頭に同梱Nodeを追加（最優先で使わせる）
        env["PATH"] = str(node_dir) + os.pathsep + env.get("PATH", "")
        
        # 2. ホームディレクトリを同梱フォルダ内に隔離する
        # これにより、ユーザーの ~/.gemini/settings.json のエラーを回避する
        gemini_home = node_dir / "gemini_home"
        os.makedirs(gemini_home, exist_ok=True)
        env["USERPROFILE"] = str(gemini_home) # Windows用
        env["HOME"] = str(gemini_home)        # Linux/macOS用
        
        # 3. npm 関連の環境変数
        npm_cache = node_dir / "npm_cache"
        os.makedirs(npm_cache, exist_ok=True)
        env["npm_config_cache"] = str(npm_cache)
        env["npm_config_prefix"] = str(node_dir)

        # 実行コマンドの決定
        # .cmd ファイルは内部で環境変数を書き換える可能性があるため、
        # node.exe で直接 .js を実行するのが最も環境隔離が確実
        if node_exe.exists() and gemini_js.exists():
            cmd = [str(node_exe), str(gemini_js)] + args
        elif os.name == 'nt' and gemini_cmd.exists():
            cmd = [str(gemini_cmd)] + args
        else:
            raise FileNotFoundError(f"Gemini CLI executable not found. Checked {gemini_js} and {gemini_cmd}")

        logger.info(f"Executing Gemini CLI (Direct Node): {' '.join(cmd)}")
        
        if interactive:
            # 認証時などはブラウザ起動や対話が必要なため、出力をキャプチャせず shell=True で実行
            # Windows では .cmd を叩く際に shell=True が安定する
            return subprocess.run(cmd, env=env, shell=True, check=True)
        else:
            # 解析時は出力を取得
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=capture_output,
                text=True,
                shell=True,
                encoding='utf-8'
            )
            
            if result.returncode != 0:
                logger.error(f"Gemini CLI failed with exit code {result.returncode}")
                if not capture_output:
                    logger.error("Output was not captured.")
                else:
                    logger.error(f"Stderr: {result.stderr}")
                    logger.error(f"Stdout: {result.stdout}")
            
            return result

    except Exception as e:
        logger.error(f"Error running bundled Gemini: {e}")
        raise