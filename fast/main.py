from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import StreamingResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

import cv2
import tempfile
import threading
import queue
import uuid
import os
import io
import logging
import base64

from roboflow import Roboflow

from inference import InferencePipeline
from inference.core.interfaces.camera.entities import VideoFrame
from supervision import Detections, BoxAnnotator, LabelAnnotator

from PIL import Image
import numpy as np

app = FastAPI()

# CORS (개발 환경에서 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Annotators
box_annotator = BoxAnnotator()
label_annotator = LabelAnnotator()

# 스트림별 리소스 저장
frame_queues = {}
pipelines = {}
temp_files = {}

# 클라이언트가 비디오 업로드 → 스트리밍 ID 반환
@app.post("/upload_stream/")
async def upload_stream(file: UploadFile = File(...)):
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    temp_file.write(await file.read())
    temp_file.flush()
    temp_file.close()

    stream_id = uuid.uuid4().hex
    frame_queue = queue.Queue()

    frame_queues[stream_id] = frame_queue
    temp_files[stream_id] = temp_file.name

    def on_prediction(predictions: dict, video_frame: VideoFrame):
        if not predictions:
            return

        labels = [p["class"] for p in predictions["predictions"]]
        detections = Detections.from_inference(predictions)

        image = label_annotator.annotate(
            scene=video_frame.image.copy(), detections=detections, labels=labels
        )
        image = box_annotator.annotate(image, detections=detections)

        ret, buffer = cv2.imencode(".jpg", image)
        if ret:
            frame_queue.put(buffer.tobytes())

    pipeline = InferencePipeline.init(
        model_id="trash_detection-cxvht/5",  # 여기에 실제 모델 ID 입력
        video_reference=temp_file.name,
        on_prediction=on_prediction
    )

    pipelines[stream_id] = pipeline

    # 백그라운드에서 YOLO 실행
    threading.Thread(target=lambda: [pipeline.start(), pipeline.join()], daemon=True).start()

    return PlainTextResponse(f"/video_feed/{stream_id}")

# 클라이언트가 MJPEG 스트리밍 요청
@app.get("/video_feed/{stream_id}")
def video_feed(stream_id: str):
    frame_queue = frame_queues.get(stream_id)
    pipeline = pipelines.get(stream_id)
    temp_file_path = temp_files.get(stream_id)

    if not frame_queue or not pipeline:
        return PlainTextResponse("Invalid stream ID", status_code=404)

    def generate():
        try:
            while True:
                frame = frame_queue.get(timeout=5)
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                )
        except Exception as e:
            print(f"[{stream_id}] Streaming stopped: {str(e)}")
        finally:
            print(f"[{stream_id}] Cleaning up resources...")

            # YOLO 파이프라인 중지
            try:
                pipeline.stop()
            except Exception as e:
                pass

            # 리소스 제거
            frame_queues.pop(stream_id, None)
            pipelines.pop(stream_id, None)
            temp_path = temp_files.pop(stream_id, None)
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")



rf = Roboflow(api_key=os.environ["ROBOFLOW_API_KEY"])
project = rf.workspace("mbcai25-zyauo").project("trash_detection-cxvht")
model = project.version(4).model

color_map = {}

def get_color(class_name):
    if class_name not in color_map:
        color_map[class_name] = tuple(np.random.randint(0, 256, size=3).tolist())
    return color_map[class_name]


# 객체 탐지용 클래스를 생성한다.
class DetectionResult(BaseModel): # pydantic을 사용하여 데이터 모델을 정의 (응답 데이터를 구조화)
    message : str                 # 클라이언트가 보낸 메세지
    image : str                   # Base64로 인코딩된 탐지 결과 이미지

# 객체 탐지 함수
# 객체 탐지를 위한 함수 정의로 모델에 이미지를 넣어 객체를 탐지하고
# 그 결과에서 바운딩 박스 정보를 추출한 후 이미지에 바인딩 박스와 클래스 이름, 신뢰도를 표시한 후 반환
def detect_objects(image: Image):
    # 임시 파일로 저장
    temp_path = "temp_img/temp.jpg"
    image.save(temp_path)

    # Roboflow 모델 예측 (API 기반, confidence threshold, overlap 설정 가능)
    prediction = model.predict(temp_path, confidence=40, overlap=30).json()

    # OpenCV 이미지로 로드
    img = cv2.imread(temp_path)

    # 바운딩 박스 시각화
    for pred in prediction["predictions"]:
        x, y, w, h = pred["x"], pred["y"], pred["width"], pred["height"]
        class_name = pred["class"]
        conf = pred["confidence"]

        x1 = int(x - w / 2)
        y1 = int(y - h / 2)
        x2 = int(x + w / 2)
        y2 = int(y + h / 2)

        color = get_color(class_name)

        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        cv2.putText(img, f"{class_name} {conf:.2f}", (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

    # PIL 이미지로 변환
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    result_image = Image.fromarray(img_rgb)
    return result_image


class LoggingMiddleware(BaseHTTPMiddleware): # 로그를 콘솔에 출력하는 용도
    logging.basicConfig(level=logging.INFO) # 로그 출력 추가
    async def dispatch(self, request, call_next) :
        logging.info(f"Req: {request.method}{request.url}")
        response = await call_next(request)
        logging.info(f"Status Code : {response.status_code}")
        return response
app.add_middleware(LoggingMiddleware) # 모든 요청에 대해 로그를 남기는 미들웨어 클래스를 사용함

# 객체 탐지 엔드 포인트
@app.post("/detect", response_model=DetectionResult) # http://localhost:8001/detect
async def detect_service(message: str = Form(...), file: UploadFile = File(...)):
    # 이미지를 읽어서 PIL 이미지로 변환
    image = Image.open(io.BytesIO(await file.read()))

    # 알파 채널 제거하고 RGB로 변환
    if image.mode == 'RGBA' :
        image = image.convert('RGB')
    elif image.mode != 'RGB' :
        image = image.convert('RGB')

    # 객체 탐지 수행 -> 이미지가 들어가서 모델에서 처리후 결과를 받음
    result_image = detect_objects(image)

    # 이미지 결과를 base64로 인코딩
    buffered = io.BytesIO()
    result_image.save(buffered, format="JPEG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

    return DetectionResult(message=message, image=img_str)
