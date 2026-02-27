import cv2
from .yolo_tracker import YoloTracker

def detect_performances(video_path, config):
    """
    YOLOとByteTrackを使用して演奏区間を検出します。
    """
    print("YOLOによる演奏区間の検出を開始します...")
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"エラー: 動画ファイル '{video_path}' を開けませんでした。")
        return []

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    max_frames = int(config.get('max_seconds_to_process', 0) * fps) if config.get('max_seconds_to_process') else float('inf')

    # YOLOトラッカーを初期化
    try:
        model_name = config.get('yolo_model', 'yolov8n.pt')
        tracker = YoloTracker(model_name=model_name)
    except Exception as e:
        print(f"YOLOトラッカーの初期化に失敗しました: {e}")
        return []

    # --- ゾーンと状態の管理 ---
    left_percent = config.get('left_zone_end_percent', 0.15)
    center_percent = config.get('center_zone_width_percent', 0.70)
    
    LEFT_ZONE_END = width * left_percent
    CENTER_ZONE_END = width * (left_percent + center_percent)

    stage_status = 'EMPTY'  # 'EMPTY', 'PERFORMING'
    performance_start_time = 0
    performance_segments = []
    
    frame_number = 0
    while cap.isOpened() and frame_number < max_frames:
        ret, frame = cap.read()
        if not ret:
            break

        tracked_objects = tracker.track_frame(frame)
        current_center_ids = set()
        
        for (box, track_id, class_id) in tracked_objects:
            x1, y1, x2, y2 = box
            center_x = (x1 + x2) / 2
            
            if LEFT_ZONE_END < center_x < CENTER_ZONE_END:
                current_center_ids.add(track_id)

        if stage_status == 'EMPTY' and len(current_center_ids) > 0:
            stage_status = 'PERFORMING'
            performance_start_time = frame_number / fps
            print(f"[{performance_start_time:.2f}s] 人物が中央ゾーンに進入。演奏開始と判断。 IDs: {current_center_ids}")

        elif stage_status == 'PERFORMING' and len(current_center_ids) == 0:
            stage_status = 'EMPTY'
            end_time = frame_number / fps
            
            if (end_time - performance_start_time) >= config.get('min_duration_seconds', 10):
                print(f"[{end_time:.2f}s] 中央ゾーンから全員退場。演奏終了と判断。")
                performance_segments.append((performance_start_time, end_time))
            else:
                print(f"[{end_time:.2f}s] 演奏区間が短すぎるため無視されました。 ({(end_time - performance_start_time):.2f}s)")
            
            performance_start_time = 0

        if config.get('show_video', False):
            cv2.line(frame, (int(LEFT_ZONE_END), 0), (int(LEFT_ZONE_END), height), (255, 0, 0), 2)
            cv2.line(frame, (int(CENTER_ZONE_END), 0), (int(CENTER_ZONE_END), height), (255, 0, 0), 2)
            for (box, track_id, class_id) in tracked_objects:
                x1, y1, x2, y2 = map(int, box)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, f"ID:{track_id}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            cv2.putText(frame, f"Status: {stage_status}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            cv2.putText(frame, f"Center IDs: {len(current_center_ids)}", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

            new_width = 960
            ratio = new_width / width
            resized_frame = cv2.resize(frame, (new_width, int(height * ratio)))
            cv2.imshow("YOLO Detection", resized_frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        frame_number += 1
        if not config.get('show_video', False) and frame_number > 0 and frame_number % 100 == 0:
            print(f"  ... [YOLO] フレーム {frame_number} を処理中 ({frame_number / fps:.2f}秒地点)")

    if stage_status == 'PERFORMING':
        end_time = frame_number / fps
        if (end_time - performance_start_time) >= config.get('min_duration_seconds', 10):
            print(f"[{end_time:.2f}s] 動画の終端に達したため、演奏終了と判断。")
            performance_segments.append((performance_start_time, end_time))

    cap.release()
    if config.get('show_video', False):
        cv2.destroyAllWindows()
    
    print(f"YOLOによる区間検出が完了。{len(performance_segments)}件の演奏区間が見つかりました。")
    return sorted(performance_segments, key=lambda x: x[0])

if __name__ == '__main__':
    detection_config = {
        'max_seconds_to_process': 480,
        'min_duration_seconds': 10,
        'show_video': True,
        'left_zone_end_percent': 0.2,
        'yolo_model': 'yolov8n.pt'
    }
    
    video_file = 'input/00002.MTS' # テスト用のビデオファイルパス
    segments = detect_performances(video_file, detection_config)
    
    if segments:
        print("\n--- 検出結果 ---")
        for i, (start, end) in enumerate(segments):
            print(f"演奏 {i+1}: 開始 {start:.2f}秒 - 終了 {end:.2f}秒 (長さ: {end-start:.2f}秒)")
    else:
        print("\n--- 検出結果 ---")
        print("指定された条件に合う演奏区間は見つかりませんでした。")
