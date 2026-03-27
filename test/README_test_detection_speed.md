# 检测速度测试脚本说明

## 文件用途
测试液位检测引擎在多视频场景下的推理速度性能，一个模型负责四个视频的检测任务，所有视频同时并行测试。

## 功能特性
- 自动加载testmodel目录下的模型1、2、3、4
- 自动加载testvideo目录下的所有测试视频
- 按照一个模型对应四个视频的方式进行测试
- 多线程并行测试所有视频，模拟真实多通道场景
- 实时显示检测进度和性能指标
- 输出详细的性能统计报告

## 测试配置
- 模型路径: /home/lqj/liquid/server/database/model/detection_model/testmodel
- 使用模型: 1.engine, 2.engine, 3.engine, 4.engine
- 视频路径: /home/lqj/liquid/testvideo
- ROI配置: /home/lqj/liquid/server/database/config/annotation_result.yaml

## 运行方式
```bash
cd /home/lqj/liquid
source ~/anaconda3/bin/activate liquid
python test_detection_speed.py
```

## 输出指标
- 每帧模型计算耗时(ms): 每个ROI的平均单帧检测耗时，单位毫秒
- ROI序号规则: 1.mp4对应ROI1和ROI2，2.mp4对应ROI3和ROI4，以此类推

## 测试流程
1. 扫描模型和视频文件
2. 按顺序分配: 模型1处理视频1-4，模型2处理视频5-8，模型3处理视频9-12，模型4处理视频13-16
3. 创建多线程，所有视频同时开始检测
4. 对每个视频逐帧进行液位检测（最多500帧）
5. 记录每帧的检测时间
6. 输出详细的性能统计报告
