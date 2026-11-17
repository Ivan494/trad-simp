import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from trad2simp import config
from trad2simp.convert import convert_text, flip_script


class ConversionTests(unittest.TestCase):
    def test_modes(self):
        trad, simp = '今天是臺灣，我們喝咖啡。', '今天是台湾，我们喝咖啡。'
        self.assertEqual(flip_script(trad), simp)
        self.assertEqual(flip_script(simp), trad)
        for text in (trad, simp):
            self.assertEqual(convert_text(text, 't2s'), simp)
            self.assertEqual(convert_text(text, 's2t'), trad)
        self.assertEqual(convert_text('繁體与简体', 't2s'), '繁体与简体')
        self.assertEqual(convert_text('繁體与简体', 's2t'), '繁體與簡體')

    def test_boundaries(self):
        for text in ('', 'hello 123', '😀\n\t !'):
            for mode in ('auto', 't2s', 's2t'):
                self.assertEqual(convert_text(text, mode), text)
        self.assertEqual(convert_text('😀繁體\n文字', 't2s'), '😀繁体\n文字')
        with self.assertRaises(ValueError):
            convert_text('', 'bad')


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'config.json'
        for name, value in [('CONFIG_DIR', self.tmp.name), ('CONFIG_PATH', str(self.path))]:
            p = patch.object(config, name, value)
            p.start()
            self.addCleanup(p.stop)

    def test_bad_settings(self):
        for raw in ('null', '[]', '1', '"text"', '{bad', '\ufffd'):
            self.path.write_text(raw, encoding='utf-8')
            self.assertEqual(config.load_config(), {})
        self.path.write_bytes(b'\xff')
        self.assertEqual(config.load_config(), {})

    def test_types_and_roundtrip(self):
        value = {'mode': 't2s', 'hotkey': 'ctrl+alt+k', 'tray_hint': True}
        self.assertTrue(config.save_config(value))
        self.assertEqual(config.load_config(), value)
        self.path.write_text(json.dumps({'mode': [], 'hotkey': 3, 'tray_hint': 'yes'}))
        self.assertEqual(config.load_config(), {})

    def test_atomic_failure_preserves_old(self):
        config.save_config({'mode': 't2s'})
        with patch.object(config.os, 'replace', side_effect=PermissionError):
            self.assertFalse(config.save_config({'mode': 's2t'}))
        self.assertEqual(config.load_config()['mode'], 't2s')
        self.assertFalse(list(Path(self.tmp.name).glob('.config-*')))

    def test_no_sensitive_exception_log(self):
        config.log('clipboard failed: private-text C:\\Users\\Private\\secret')
        output = (Path(self.tmp.name) / 'log.txt').read_text()
        self.assertNotIn('private', output)
        self.assertNotIn('Users', output)
