import os
import numpy as np
import onnxruntime as ort
import sounddevice as sd

def record_audio(duration=3.0, sr=16000):
    print(f"\nRecording {duration} seconds of audio. Please speak...")
    audio = sd.rec(int(duration * sr), samplerate=sr, channels=1, dtype='float32')
    sd.wait()
    print("Recording finished.")
    return audio[:, 0]

def test_streaming(model_path, audio, sr=16000):
    print(f"\n--- Testing Streaming Context Model: {model_path} ---")
    session = ort.InferenceSession(model_path)
    
    # Official Context Sizes
    window_size = 512
    context_size = 64
    
    # Initialize States
    state = np.zeros((2, 1, 128), dtype=np.float32)
    context = np.zeros((1, context_size), dtype=np.float32)
    sr_tensor = np.array(sr, dtype=np.int64)

    probs = []
    state_means = []
    
    for i in range(0, len(audio), window_size):
        chunk = audio[i:i+window_size]
        if len(chunk) < window_size:
            break
            
        chunk = chunk.reshape(1, window_size)
        
        # KEY REVELATION: Concatenate the last 64 samples of the PREVIOUS chunk
        # to the beginning of the CURRENT 512 samples. 
        # The ONNX model receives exactly 576 samples per inference!
        x = np.concatenate([context, chunk], axis=1)
        
        ort_inputs = {
            'input': x,
            'state': state,
            'sr': sr_tensor
        }
        
        outs = session.run(['output', 'stateN'], ort_inputs)
        prob = float(outs[0][0][0])
        state = outs[1]
        
        # Update context cache with the last 64 samples of THIS concatenated chunk
        context = x[:, -context_size:]
        
        probs.append(prob)
        state_means.append(float(np.mean(state)))

    print("Max Probability:", max(probs))
    print("Frames > 0.5:", sum(1 for p in probs if p > 0.5))
    
    print("\nDetailed Frame Log (every 5th frame):")
    for i in range(0, len(probs), 5):
        print(f"Frame {i:03d} | Prob: {probs[i]:.4f} | State Mean: {state_means[i]:.4f}")

def main():
    # Use the user's local model directly to prove it works
    local_path = os.path.abspath(os.path.join("wakeword", "models", "silero_vad.onnx"))
    if not os.path.exists(local_path):
        local_path = os.path.abspath(os.path.join("..", "models", "silero_vad.onnx"))
        if not os.path.exists(local_path):
            print("Model not found!")
            return
            
    print("=== SPEECH TEST WITH PROPER CONTEXT ===")
    speech = record_audio(duration=3.0)
    test_streaming(local_path, speech)

if __name__ == "__main__":
    main()
