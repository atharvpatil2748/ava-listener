"""
ASR Resources (Phase S)
"""
import sherpa_onnx
import os

class SherpaResources:
    @staticmethod
    def create_recognizer(models_dir, num_threads, sample_rate, rule1, rule2, rule3):
        enc = os.path.join(models_dir, "encoder.onnx")
        dec = os.path.join(models_dir, "decoder.onnx")
        joi = os.path.join(models_dir, "joiner.onnx")
        tok = os.path.join(models_dir, "tokens.txt")

        for path, label in [
            (enc, "encoder"), (dec, "decoder"),
            (joi, "joiner"),  (tok, "tokens"),
        ]:
            if not os.path.isfile(path):
                raise FileNotFoundError(
                    f"Model file missing: {path}\n"
                    f"Download sherpa-onnx-streaming-zipformer-en-2023-06-26 "
                    f"and place files in wakeword/models/"
                )

        return sherpa_onnx.OnlineRecognizer.from_transducer(
            encoder=enc,
            decoder=dec,
            joiner=joi,
            tokens=tok,
            num_threads=num_threads,
            sample_rate=sample_rate,
            feature_dim=80,
            enable_endpoint_detection=True,
            rule1_min_trailing_silence=rule1,
            rule2_min_trailing_silence=rule2,
            rule3_min_utterance_length=rule3,
        )

    @staticmethod
    def create_stream(recognizer):
        return recognizer.create_stream()
