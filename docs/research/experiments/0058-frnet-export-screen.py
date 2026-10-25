"""Isolated ONNX/TensorRT compatibility screen, using synthetic geometry only.

Run from Drishti-2.5 with artifacts/frnet-engine-env-20261023/Scripts/python.exe.
No exported model is selected by the production runtime. A static tracing
success does not establish variable-point-count or prediction compatibility.
"""

import argparse
import json
import traceback
import warnings
from pathlib import Path

import onnx
import torch

from drishti.frnet_model import TorchFRNetPredictor

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
report = {
    "torch": torch.__version__,
    "onnx": onnx.__version__,
    "status": "research only; no production model change",
    "exports": {},
}
torch.set_num_threads(2)
predictor = TorchFRNetPredictor(
    checkpoint=Path("../data/frnet-semantickitti_seg.pth"),
    checkpoint_sha256="09adea9005215641aea915cc3aa2bebf74582ce240cca91dedd07940ad94285e",
)
torch.manual_seed(58)
points = torch.rand(256, 4)
points[:, :3] = points[:, :3] * torch.tensor([50.0, 50.0, 3.0]) + torch.tensor([1.0, -25.0, -1.7])
stem_input = torch.rand(1, 16, 64, 512)
for name, model, example in (
    ("full", predictor._model, points),
    ("stem", predictor._model.backbone.stem, stem_input),
):
    path = args.output / f"{name}.onnx"
    item = {}
    try:
        with warnings.catch_warnings(record=True) as recorded, torch.inference_mode():
            warnings.simplefilter("always")
            torch.onnx.export(
                model,
                (example,),
                str(path),
                dynamo=False,
                opset_version=17,
                input_names=["input"],
                output_names=["output"],
            )
        item["warnings"] = [str(w.message) for w in recorded]
        graph = onnx.load(path)
        onnx.checker.check_model(graph)
        item["onnx_check"] = "passed; static synthetic shape only"
        item["operators"] = sorted({node.op_type for node in graph.graph.node})
        try:
            import tensorrt as trt

            report["tensorrt"] = trt.__version__
            logger = trt.Logger(trt.Logger.WARNING)
            builder = trt.Builder(logger)
            network = builder.create_network(
                1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH)
            )
            importer = trt.OnnxParser(network, logger)
            item["tensorrt_parse"] = importer.parse(path.read_bytes())
            item["parser_errors"] = [str(importer.get_error(i)) for i in range(importer.num_errors)]
        except Exception:
            item["tensorrt_error"] = traceback.format_exc()
    except Exception:
        item["export_error"] = traceback.format_exc()
    report["exports"][name] = item
    (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(name, json.dumps(item), flush=True)
predictor.close()
