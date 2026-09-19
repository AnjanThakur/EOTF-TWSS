import time
import unittest
from threading import Thread
import numpy as np

from src.acquisition.beast_stream import BeastStreamer, discover_streams
from tests.mock_lsl_stream import MockLSLPublisher


class LSLTests(unittest.TestCase):
    def test_discovery_connection_samples_window_and_wrong_count(self):
        publisher = MockLSLPublisher(name="TWSS Test Unique", channels=6, rate=50)
        source = BeastStreamer(stream_name="TWSS Test Unique", expected_channels=6, resolve_timeout=3)
        try:
            self.assertTrue(discover_streams(name="TWSS Test Unique", timeout=3))
            source.start()
            time.sleep(0.5)
            thread = Thread(target=publisher.publish, kwargs={"seconds": 8}, daemon=True); thread.start()
            window = source.get_window(3)
            self.assertEqual(window.shape, (6, 150)); self.assertTrue(np.isfinite(window).all())
        finally: source.stop()

    def test_wrong_count_and_timeout(self):
        publisher = MockLSLPublisher(name="TWSS Wrong Count", channels=4, rate=20)
        source = BeastStreamer(stream_name="TWSS Wrong Count", expected_channels=6, resolve_timeout=3)
        with self.assertRaises(ValueError): source.start()
        source = BeastStreamer(stream_name="TWSS Missing", resolve_timeout=0.2)
        with self.assertRaises(RuntimeError): source.start()
