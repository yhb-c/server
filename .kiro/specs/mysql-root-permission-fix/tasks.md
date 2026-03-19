 
 1.video_capture_factory.py代码负责调用海康sdk库（liquid/server/lib）捕获rtsp流解码生成yuv数据，输入到模型进行检测
 2.server/detection/detection.py，输入为video_capture_factory.pyrtsp流解码获得的帧，使用模型推理roi区域得到液位高度数据，roi位置信息读取server/database/config/annotation_result.yaml
 3.server/websocket/detection_service.py负责推送高度数据到客户端