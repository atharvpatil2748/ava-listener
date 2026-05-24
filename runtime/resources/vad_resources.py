"""
VAD Resources (Phase S)
"""
import os

class SileroResources:
    @staticmethod
    def create_session():
        import onnxruntime
        from config.settings import MODELS_DIR
        model_path = os.path.join(MODELS_DIR, "silero_vad.onnx")
        if not os.path.isfile(model_path):
            raise FileNotFoundError(f"Silero VAD model missing: {model_path}")
            
        opts = onnxruntime.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        return onnxruntime.InferenceSession(model_path, providers=['CPUExecutionProvider'], sess_options=opts)
