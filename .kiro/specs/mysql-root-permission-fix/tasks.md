 
 1.video_capture_factory.py代码负责调用海康sdk库（liquid/server/lib）捕获rtsp流解码生成yuv数据，输入到模型进行检测
 2.server/detection/detection.py，输入为video_capture_factory.pyrtsp流解码获得的帧，加载并使用模型推理roi区域得到液位高度数据，roi位置信息读取server/database/config/annotation_result.yaml
 3.server/websocket/detection_service.py负责推送高度数据到客户端
 模型加载成功 (tensor.pt, CPU模式)
 configure_channel尝试创建任务，但任务已在load_model时创建。让我修复configure_channel，跳过任务创建步骤。
 直接测试服务器对客户端start_detection指令的响应
 检测线程只负责：获取帧 → 调用detection.py计算高度 → 输出结果
不需要存储 detection_engines 和 video_captures
模型和ROI配置应该在detection.py中管理
LiquidDetectionEngine.detect() 方法：

输入：帧 + ROI配置
输出：液位高度数据