import sys
import os
import time
import queue
import numpy as np
import sounddevice as sd

# Ensure we can import from wakeword package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from audio.vad import HybridVAD
from config.settings import SAMPLE_RATE, BLOCK_SIZE

def main():
    print("=== Initializing Silero VAD Standalone Test ===")
    
    # 1. Print Exact ONNX Interface
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    model_path = os.path.join(BASE_DIR, "models", "silero_vad.onnx")
    import onnxruntime as ort
    session = ort.InferenceSession(model_path)
    print("\n[ONNX] INPUTS:")
    for i in session.get_inputs():
        print(f"  {i.name}: {i.shape} ({i.type})")
    print("\n[ONNX] OUTPUTS:")
    for o in session.get_outputs():
        print(f"  {o.name}: {o.shape} ({o.type})\n")
    
    vad = HybridVAD()
    audio_queue = queue.Queue()

    def audio_callback(indata, frames, time_info, status):
        if status:
            print(f"Status: {status}", file=sys.stderr)
        audio_queue.put_nowait(indata[:, 0].copy())

    print(f"Opening microphone... (Rate: {SAMPLE_RATE}, Block: {BLOCK_SIZE})")
    print("Speak into the microphone to see real-time Silero probabilities.")
    print("Press Ctrl+C to stop.\n")

    try:
        with sd.InputStream(
            channels=1,
            samplerate=SAMPLE_RATE,
            dtype="float32",
            blocksize=BLOCK_SIZE,
            callback=audio_callback
        ):
            while True:
                chunk = audio_queue.get()
                # 2. Force explicit shape (though process_chunk handles chunking)
                # We will also dump raw outputs inside vad.py if we modify it, 
                # but let's test the result first.
                res = vad.process_chunk(chunk)
                
                prob = res["silero_prob"]
                webrtc = res["webrtc"]
                rms = res["rms"]
                
                # Visual bar based on probability
                bar_len = int(prob * 50)
                bar = "#" * bar_len + "-" * (50 - bar_len)
                
                # Highlight if speech is detected
                status = "SPEECH " if res["pass"] else "SILENCE"
                
                print(f"[{status}] Prob: {prob:5.3f} |{bar}| (webrtc={webrtc}, rms={rms:.4f})")
                
    except KeyboardInterrupt:
        print("\nTest stopped by user.")
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    main()
