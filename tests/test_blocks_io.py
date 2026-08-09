"""Unit tests for I/O and structural blocks: Scope, InputPort/OutputPort, AudioInput/Output, AudioRead."""
import os
import wave
import struct
import tempfile
import unittest
import numpy as np

from engine.blocks.scope import Scope
from engine.blocks.input_port import InputPort
from engine.blocks.output_port import OutputPort
from engine.blocks.audio_input import AudioInput
from engine.blocks.audio_output import AudioOutput
from engine.blocks.audio_read import AudioRead
from engine.models import RuntimeContext
from conftest import set_params


class TestScope(unittest.TestCase):
    def test_records_time_and_value_data(self):
        s = Scope()
        for i, t in enumerate([0.0, 0.1, 0.2]):
            s.inputs["in1"].value = float(i)
            s.compute(t, 0.1)

        self.assertEqual(s.time_data, [0.0, 0.1, 0.2])
        self.assertEqual(s.value_data, [0.0, 1.0, 2.0])

    def test_multiple_inputs_recorded_independently(self):
        s = Scope()
        s.add_input("in2")
        s.num_inputs = 2

        s.inputs["in1"].value = 1.0
        s.inputs["in2"].value = 2.0
        s.compute(0.0, 0.1)

        self.assertEqual(s.input_data["in1"], [1.0])
        self.assertEqual(s.input_data["in2"], [2.0])

    def test_reset_clears_stored_data(self):
        s = Scope()
        s.inputs["in1"].value = 1.0
        s.compute(0.0, 0.1)
        self.assertTrue(s.time_data)

        s.reset()
        self.assertEqual(s.time_data, [])
        self.assertEqual(s.value_data, [])
        self.assertEqual(s.input_data, {})

    def test_get_data_arrays_returns_numpy_arrays(self):
        s = Scope()
        s.inputs["in1"].value = 3.0
        s.compute(0.0, 0.1)
        time_arr, data_dict = s.get_data_arrays()
        self.assertIsInstance(time_arr, np.ndarray)
        self.assertIsInstance(data_dict["in1"], np.ndarray)
        self.assertEqual(data_dict["in1"][0], 3.0)


class TestInputOutputPort(unittest.TestCase):
    def test_input_port_compute_is_noop_value_injected_externally(self):
        p = InputPort()
        p.outputs["out"].value = 5.0
        p.compute(0.0, 0.01)  # should not touch outputs itself
        self.assertEqual(p.outputs["out"].value, 5.0)

    def test_output_port_compute_is_noop(self):
        p = OutputPort()
        p.inputs["in"].value = 9.0
        p.compute(0.0, 0.01)
        # OutputPort doesn't write an output port itself; value stays on 'in'.
        self.assertEqual(p.inputs["in"].value, 9.0)

    def test_port_name_param_updates_label(self):
        p = InputPort()
        p.params["PortName"] = "Speed"
        p._update_label()
        self.assertIn("Speed", p.name)


class TestAudioInputOutput(unittest.TestCase):
    def test_audio_input_reads_channel_from_context(self):
        block = AudioInput()
        set_params(block, Channel=1)
        indata = np.array([[0.1, 0.9], [0.2, 0.8], [0.3, 0.7]])
        ctx = RuntimeContext(indata=indata, outdata=None, frame_idx=1)
        block.compute(0.0, 0.01, context=ctx)
        self.assertAlmostEqual(block.outputs["out"].value, 0.8)

    def test_audio_input_compute_chunk_copies_channel(self):
        block = AudioInput()
        set_params(block, Channel=0)
        indata = np.array([[0.1, 0.0], [0.2, 0.0], [0.3, 0.0]])
        ctx = RuntimeContext(indata=indata, outdata=None)
        block.compute_chunk(np.arange(3) * 0.01, 0.01, context=ctx)
        np.testing.assert_allclose(block.outputs["out"].vector_value, [0.1, 0.2, 0.3])

    def test_audio_input_without_context_does_not_crash(self):
        block = AudioInput()
        block.compute(0.0, 0.01, context=None)  # should be a no-op

    def test_audio_output_writes_channel_into_context(self):
        block = AudioOutput()
        set_params(block, Channel=0)
        block.inputs["in"].value = 0.42
        outdata = np.zeros((3, 2))
        ctx = RuntimeContext(indata=None, outdata=outdata, frame_idx=2)
        block.compute(0.0, 0.01, context=ctx)
        self.assertAlmostEqual(outdata[2, 0], 0.42)

    def test_audio_output_compute_chunk_writes_full_channel(self):
        block = AudioOutput()
        set_params(block, Channel=1)
        block.inputs["in"].vector_value = np.array([0.1, 0.2, 0.3])
        outdata = np.zeros((3, 2))
        ctx = RuntimeContext(indata=None, outdata=outdata)
        block.compute_chunk(np.arange(3) * 0.01, 0.01, context=ctx)
        np.testing.assert_allclose(outdata[:, 1], [0.1, 0.2, 0.3])

    def test_audio_output_channel_out_of_range_does_not_crash(self):
        block = AudioOutput()
        set_params(block, Channel=5)  # only 2 channels available
        block.inputs["in"].value = 1.0
        outdata = np.zeros((3, 2))
        ctx = RuntimeContext(indata=None, outdata=outdata, frame_idx=0)
        block.compute(0.0, 0.01, context=ctx)  # should not raise
        np.testing.assert_allclose(outdata, np.zeros((3, 2)))


class TestAudioRead(unittest.TestCase):
    def _write_test_wav(self, path, freq=1.0, sr=100, seconds=1.0, amplitude=0.5):
        n = int(sr * seconds)
        t = np.arange(n) / sr
        samples = (amplitude * np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)
        with wave.open(path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(struct.pack(f"<{n}h", *samples))

    def test_reads_and_plays_back_wav_samples(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.wav")
            self._write_test_wav(path, freq=1.0, sr=100, seconds=1.0)

            block = AudioRead()
            block.params["Filename"] = path
            block.params["Loop"] = "No"
            block.reset()

            self.assertIsNotNone(block.samples)
            block.compute(0.0, 0.01)
            self.assertAlmostEqual(block.outputs["out"].value, 0.0, places=2)

    def test_missing_file_outputs_zero_without_crashing(self):
        block = AudioRead()
        block.params["Filename"] = "does_not_exist.wav"
        block.reset()
        block.compute(0.0, 0.01)
        self.assertEqual(block.outputs["out"].value, 0.0)

    def test_loop_wraps_past_end_of_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.wav")
            self._write_test_wav(path, freq=1.0, sr=100, seconds=1.0)

            block = AudioRead()
            block.params["Filename"] = path
            block.params["Loop"] = "Yes"
            block.reset()

            # Well past file duration; should not raise and should wrap around.
            block.compute(10.0, 0.01)
            self.assertIsInstance(block.outputs["out"].value, float)

    def test_no_loop_outputs_zero_past_end_of_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.wav")
            self._write_test_wav(path, freq=1.0, sr=100, seconds=1.0)

            block = AudioRead()
            block.params["Filename"] = path
            block.params["Loop"] = "No"
            block.reset()

            block.compute(5.0, 0.01)  # past 1.0s duration
            self.assertEqual(block.outputs["out"].value, 0.0)


if __name__ == "__main__":
    unittest.main()
