"""Streamlit interactions with the real model and mocked speech."""
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest


class UITests(unittest.TestCase):
    def test_command_flow(self):
        app = AppTest.from_file("../ui/app.py", default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.slider(key="threshold").value, 0.7)
        self.assertFalse(app.checkbox(key="debug").value)
        app.button(key="start").click().run()
        self.assertFalse(app.exception)
        self.assertEqual([m.value for m in app.metric], ["RIGHT", "96.04%", "NO"])
        self.assertEqual(len(app.get("vega_lite_chart")), 1)
        self.assertFalse(any("Actual dataset label:" in m.value for m in app.markdown))
        app.checkbox(key="debug").check().run()
        self.assertTrue(any("Actual dataset label: RIGHT" in m.value for m in app.markdown))
        app.checkbox(key="audio").check().run()
        with patch("src.twss.speech.Speaker.speak") as speak:
            app.button(key="speak").click().run()
            speak.assert_called_once_with("No.")
        app.slider(key="threshold").set_value(0.99).run()
        self.assertEqual([m.value for m in app.metric], ["UNKNOWN", "96.04%", "—"])
        self.assertIsNone(app.session_state.controller.latest.sentence)
        self.assertTrue(app.button(key="speak").disabled)
        self.assertEqual(app.session_state.controller.processed, 1)
        app.button(key="start").click().run()
        self.assertEqual(app.session_state.controller.processed, 2)
        self.assertEqual(app.metric[1].value, "72.14%")
        app.button(key="reset").click().run()
        self.assertEqual(app.session_state.controller.processed, 0)
        self.assertIsNone(app.session_state.controller.latest)
        self.assertFalse(app.exception)

    def test_exhaustion_and_failure(self):
        app = AppTest.from_file("../ui/app.py", default_timeout=30).run()
        app.button(key="start").click().run()
        controller = app.session_state.controller
        controller.trials = iter(())
        app.button(key="start").click().run()
        self.assertTrue(controller.exhausted)
        self.assertIsNone(controller.latest)
        self.assertTrue(app.button(key="speak").disabled)
        app.run()
        self.assertTrue(app.button(key="start").disabled)
        app.button(key="reset").click().run()
        def broken_source():
            raise OSError("Simulated source failure")
            yield
        app.session_state.controller.trials = broken_source()
        app.button(key="start").click().run()
        self.assertIn("Simulated source failure", app.session_state.status)
        self.assertIsNone(app.session_state.controller.latest)
        self.assertFalse(app.exception)


