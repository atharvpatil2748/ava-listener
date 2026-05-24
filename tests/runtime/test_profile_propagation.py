import os
import tempfile
import json
import unittest
from runtime.kernel.orchestrator import WakeEngine
from runtime.config.profile_loader import load_profile

class TestProfilePropagation(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        
        # Create base.json
        self.base_path = os.path.join(self.temp_dir.name, "base.json")
        with open(self.base_path, 'w') as f:
            json.dump({
                "vad": {"sileroThreshold": 0.15},
                "confidence": {"defaultThreshold": 0.78},
                "transcription": {"enableDebug": False}
            }, f)
            
        # Create debug.json
        self.debug_path = os.path.join(self.temp_dir.name, "debug.json")
        with open(self.debug_path, 'w') as f:
            json.dump({
                "extends": "base.json",
                "transcription": {"enableDebug": True},
                "wakePhrases": [
                    {
                        "phraseId": "test_phrase",
                        "text": "test phrase",
                        "threshold": 0.9
                    }
                ]
            }, f)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_profile_loader_merges_correctly(self):
        data = load_profile(self.debug_path)
        self.assertEqual(data["vad"]["sileroThreshold"], 0.15)
        self.assertTrue(data["transcription"]["enableDebug"])
        self.assertEqual(data["wakePhrases"][0]["text"], "test phrase")

    def test_orchestrator_preserves_merged_object(self):
        engine = WakeEngine()
        engine.load_profile(self.debug_path)
        
        # Check active profile
        self.assertEqual(engine._active_profile["vad"]["sileroThreshold"], 0.15)
        self.assertTrue(engine._active_profile["transcription"]["enableDebug"])
        
        # Check effective config mapping
        effective = engine.get_effective_config()
        self.assertEqual(effective["values"]["vad.sileroThreshold"], 0.15)
        self.assertTrue(effective["values"]["transcription.enableDebug"])
        
        # Verify mutability behavior
        from runtime.config.mutability import RestartRequiredError
        
        # Hot reloadable
        engine.update_config({"vad.sileroThreshold": 0.3})
        self.assertEqual(engine._runtime_params["vad_threshold"], 0.3)
        
        # Restart required (should raise if engine active)
        engine._state_machine.transition("running")
        with self.assertRaises(RestartRequiredError):
            engine.update_config({"asr.provider": "whisper"})

if __name__ == '__main__':
    unittest.main()
