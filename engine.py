import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'runtime'))

from asr.streaming import SherpaStreamer
from matcher.evaluator import best_match

class WakeEngine:
    def __init__(self):
        self.streamer = SherpaStreamer()

    def on_text(self, text):
        print("ASR:", text)
        match_result, score, variant = best_match(text)
        if match_result:
            print(f"🔥 WAKE DETECTED: {match_result} (score: {score})")

    def start(self):
        self.streamer.start(self.on_text)

if __name__ == "__main__":
    engine = WakeEngine()
    engine.start()