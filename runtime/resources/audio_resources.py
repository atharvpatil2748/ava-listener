"""
Audio Resources (Phase S)
"""
import sounddevice as sd

class AudioResources:
    @staticmethod
    def create_input_stream(channels, samplerate, dtype, blocksize, callback):
        return sd.InputStream(
            channels=channels,
            samplerate=samplerate,
            dtype=dtype,
            blocksize=blocksize,
            callback=callback,
        )
