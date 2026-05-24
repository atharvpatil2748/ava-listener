from asr.sherpa_stream import SherpaStreamer
from detection.matcher import is_wake_word


class WakeEngine:
    def __init__(self):
        self.streamer = SherpaStreamer()

    def on_text(self, text):
        print("ASR:", text)

        if is_wake_word(text):
            print("🔥 WAKE DETECTED")

    def start(self):
        self.streamer.start(self.on_text)