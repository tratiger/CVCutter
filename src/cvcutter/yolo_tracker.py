from ultralytics import YOLO
import torch

class YoloTracker:
    def __init__(self, model_name='yolov8n.pt'):
        """
        YOLOv8トラッカーを初期化します。

        Args:
            model_name (str): 使用するYOLOモデルの名前。
        """
        # GPUが利用可能か確認
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"YOLO Tracker: Using device '{self.device}'")
        
        # モデルをロード
        try:
            self.model = YOLO(model_name)
            self.model.to(self.device)
        except Exception as e:
            print(f"Error loading YOLO model: {e}")
            print("Please ensure you have a working internet connection to download the model or the model file is correctly placed.")
            raise

    def track_frame(self, frame):
        """
        単一フレーム内のオブジェクトを追跡します。

        Args:
            frame: 入力フレーム (numpy array)。

        Returns:
            タプルのリスト。各タプルは (bbox, track_id, class_id) を含みます。
            bboxは (x1, y1, x2, y2) 形式です。
        """
        # 'person' クラス (クラスID 0) のみを対象とします
        results = self.model.track(frame, persist=True, classes=[0], verbose=False)
        
        if results[0].boxes.id is None:
            return [] # このフレームには追跡対象がいません

        tracked_objects = []
        # .cpu() を呼び出して、結果をCPUメモリに移動させてからnumpyに変換します
        boxes = results[0].boxes.xyxy.cpu().numpy()
        track_ids = results[0].boxes.id.cpu().numpy()
        class_ids = results[0].boxes.cls.cpu().numpy()

        for box, track_id, class_id in zip(boxes, track_ids, class_ids):
            tracked_objects.append((box, int(track_id), int(class_id)))
            
        return tracked_objects
