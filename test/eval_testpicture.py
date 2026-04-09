import argparse
import importlib.util
import time
from pathlib import Path
import sys

import numpy as np
from PIL import Image


def iou_xyxy(box1, box2):
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    inter_w = max(0.0, x2 - x1)
    inter_h = max(0.0, y2 - y1)
    inter = inter_w * inter_h
    if inter <= 0:
        return 0.0
    area1 = max(0.0, box1[2] - box1[0]) * max(0.0, box1[3] - box1[1])
    area2 = max(0.0, box2[2] - box2[0]) * max(0.0, box2[3] - box2[1])
    union = area1 + area2 - inter
    return inter / union if union > 0 else 0.0


def yolo_label_to_xyxy(line, w, h):
    parts = line.strip().split()
    if len(parts) < 5:
        return None
    cls = int(float(parts[0]))
    cx = float(parts[1]) * w
    cy = float(parts[2]) * h
    bw = float(parts[3]) * w
    bh = float(parts[4]) * h
    x1 = cx - bw / 2.0
    y1 = cy - bh / 2.0
    x2 = cx + bw / 2.0
    y2 = cy + bh / 2.0
    return cls, [x1, y1, x2, y2]


def compute_ap(recalls, precisions):
    mrec = np.concatenate(([0.0], recalls, [1.0]))
    mpre = np.concatenate(([0.0], precisions, [0.0]))
    for i in range(mpre.size - 1, 0, -1):
        mpre[i - 1] = max(mpre[i - 1], mpre[i])
    xs = np.linspace(0.0, 1.0, 101)
    ap = 0.0
    for x in xs:
        p = mpre[mrec >= x].max() if np.any(mrec >= x) else 0.0
        ap += p / 101.0
    return float(ap)


def evaluate_map(preds_by_class, gts_by_class, iou_thresholds):
    classes = sorted(set(gts_by_class.keys()) | set(preds_by_class.keys()))
    ap_per_class_per_iou = {}

    for cls in classes:
        gt_map = gts_by_class.get(cls, {})
        n_gt = sum(len(v) for v in gt_map.values())
        if n_gt == 0:
            continue

        cls_preds = preds_by_class.get(cls, [])
        cls_preds = sorted(cls_preds, key=lambda x: x["conf"], reverse=True)
        ap_list = []

        for iou_thr in iou_thresholds:
            matched = {img_id: np.zeros(len(gt_boxes), dtype=bool) for img_id, gt_boxes in gt_map.items()}
            tp = np.zeros(len(cls_preds), dtype=np.float32)
            fp = np.zeros(len(cls_preds), dtype=np.float32)

            for i, pred in enumerate(cls_preds):
                img_id = pred["image_id"]
                pbox = pred["box"]
                gt_boxes = gt_map.get(img_id, [])
                if len(gt_boxes) == 0:
                    fp[i] = 1.0
                    continue

                ious = np.array([iou_xyxy(pbox, g) for g in gt_boxes], dtype=np.float32)
                best_idx = int(np.argmax(ious))
                best_iou = float(ious[best_idx])

                if best_iou >= iou_thr and not matched[img_id][best_idx]:
                    tp[i] = 1.0
                    matched[img_id][best_idx] = True
                else:
                    fp[i] = 1.0

            tp_cum = np.cumsum(tp)
            fp_cum = np.cumsum(fp)
            recalls = tp_cum / max(float(n_gt), 1e-12)
            precisions = tp_cum / np.maximum(tp_cum + fp_cum, 1e-12)
            ap = compute_ap(recalls, precisions) if len(cls_preds) else 0.0
            ap_list.append(ap)

        ap_per_class_per_iou[cls] = ap_list

    if not ap_per_class_per_iou:
        return 0.0, 0.0

    ap50 = [v[0] for v in ap_per_class_per_iou.values()]
    ap5095 = [float(np.mean(v)) for v in ap_per_class_per_iou.values()]
    map50 = float(np.mean(ap50)) if ap50 else 0.0
    map50_95 = float(np.mean(ap5095)) if ap5095 else 0.0
    return map50, map50_95


def collect_images(images_dir):
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
    files = [p for p in images_dir.iterdir() if p.is_file() and p.suffix.lower() in exts]
    return sorted(files)


def main():
    parser = argparse.ArgumentParser(description="Evaluate model with project detection loading path.")
    parser.add_argument(
        "--model",
        default=r"C:\Users\admin\Desktop\server\server\database\model\temp_models\tensor.pt",
        help="Model path",
    )
    parser.add_argument(
        "--dataset",
        default=r"C:\Users\admin\Desktop\server\testpicture",
        help="Dataset root, must include images/ labels/",
    )
    parser.add_argument("--imgsz", type=int, default=640, help="Inference image size")
    parser.add_argument("--conf", type=float, default=0.001, help="Inference conf threshold")
    parser.add_argument("--iou", type=float, default=0.6, help="NMS IoU threshold")
    parser.add_argument("--device", default="cuda", help="cuda/cpu/cuda:0")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    server_root = root / "server"
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    if str(server_root) not in sys.path:
        sys.path.insert(0, str(server_root))

    model_detect_path = server_root / "detection" / "model_detect.py"
    spec = importlib.util.spec_from_file_location("project_model_detect", model_detect_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module spec: {model_detect_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    load_model = mod.load_model

    model_path = Path(args.model)
    dataset_dir = Path(args.dataset)
    images_dir = dataset_dir / "images"
    labels_dir = dataset_dir / "labels"

    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")
    if not images_dir.exists() or not labels_dir.exists():
        raise FileNotFoundError(f"Dataset must include images/ and labels/: {dataset_dir}")

    model, actual_model_path = load_model(str(model_path), device=args.device)
    if model is None:
        raise RuntimeError("load_model failed in server/detection/model_detect.py")

    image_files = collect_images(images_dir)
    if not image_files:
        raise RuntimeError(f"No images found in: {images_dir}")

    preds_by_class = {}
    gts_by_class = {}

    infer_ms_list = []
    preprocess_ms_list = []
    postprocess_ms_list = []
    wall_times = []
    total_instances = 0

    for img_idx, img_path in enumerate(image_files):
        image_id = img_path.stem
        with Image.open(img_path) as im:
            w, h = im.size

        # Load GT label
        label_path = labels_dir / f"{image_id}.txt"
        if label_path.exists():
            lines = label_path.read_text(encoding="utf-8", errors="ignore").splitlines()
            for ln in lines:
                parsed = yolo_label_to_xyxy(ln, w, h)
                if parsed is None:
                    continue
                cls, box = parsed
                gts_by_class.setdefault(cls, {}).setdefault(image_id, []).append(box)
                total_instances += 1

        # Predict with project-style call chain
        predict_kwargs = {
            "source": str(img_path),
            "imgsz": args.imgsz,
            "conf": args.conf,
            "iou": args.iou,
            "save": False,
            "verbose": False,
            "stream": False,
        }
        if not str(actual_model_path).endswith(".engine"):
            predict_kwargs["device"] = args.device
            predict_kwargs["half"] = args.device != "cpu"

        t0 = time.perf_counter()
        results = model.predict(**predict_kwargs)
        wall_times.append((time.perf_counter() - t0) * 1000.0)

        if not results:
            continue
        result = results[0]
        speed = getattr(result, "speed", {}) or {}
        preprocess_ms_list.append(float(speed.get("preprocess", 0.0)))
        infer_ms_list.append(float(speed.get("inference", 0.0)))
        postprocess_ms_list.append(float(speed.get("postprocess", 0.0)))

        boxes = getattr(result, "boxes", None)
        if boxes is None or boxes.xyxy is None:
            continue

        xyxy = boxes.xyxy.detach().cpu().numpy()
        confs = boxes.conf.detach().cpu().numpy()
        clss = boxes.cls.detach().cpu().numpy().astype(int)
        for b, c, cls in zip(xyxy, confs, clss):
            preds_by_class.setdefault(int(cls), []).append(
                {"image_id": image_id, "conf": float(c), "box": [float(v) for v in b]}
            )

        if (img_idx + 1) % 20 == 0:
            print(f"[Progress] {img_idx + 1}/{len(image_files)} images processed")

    iou_thresholds = np.arange(0.5, 0.96, 0.05)
    map50, map50_95 = evaluate_map(preds_by_class, gts_by_class, iou_thresholds)

    avg_pre = float(np.mean(preprocess_ms_list)) if preprocess_ms_list else 0.0
    avg_inf = float(np.mean(infer_ms_list)) if infer_ms_list else 0.0
    avg_post = float(np.mean(postprocess_ms_list)) if postprocess_ms_list else 0.0
    avg_wall = float(np.mean(wall_times)) if wall_times else 0.0
    fps = 1000.0 / avg_inf if avg_inf > 0 else 0.0
    fps_e2e = 1000.0 / avg_wall if avg_wall > 0 else 0.0

    print("\n=== Evaluation Summary (Project Detection Path) ===")
    print(f"Model: {actual_model_path}")
    print(f"Dataset: {dataset_dir}")
    print(f"Images: {len(image_files)}")
    print(f"GT instances: {total_instances}")
    print(f"mAP@0.5: {map50:.6f}")
    print(f"mAP@0.5:0.95: {map50_95:.6f}")
    print(
        "Speed (ms/image): "
        f"preprocess={avg_pre:.3f}, inference={avg_inf:.3f}, postprocess={avg_post:.3f}, wall={avg_wall:.3f}"
    )
    print(f"Approx model FPS (inference only): {fps:.2f}")
    print(f"Approx end-to-end FPS (wall): {fps_e2e:.2f}")


if __name__ == "__main__":
    main()
