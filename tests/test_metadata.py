"""Small synthetic headers test renamed models and malformed input."""
import importlib.util
import pathlib
import struct
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    'info', pathlib.Path(__file__).parents[1] / 'bin/prism-gguf-info.py')
info = importlib.util.module_from_spec(spec)
spec.loader.exec_module(info)


class MetadataTests(unittest.TestCase):
    def test_types(self):
        for ftype in (27, 28, 128, 129):
            with tempfile.NamedTemporaryFile() as file:
                key = b'general.file_type'
                file.write(b'GGUF' + struct.pack('<IQQ', 3, 0, 1))
                file.write(struct.pack('<Q', len(key)) + key)
                file.write(struct.pack('<II', 4, ftype))
                file.flush()
                self.assertEqual(info.inspect(file.name)['general.file_type'], ftype)

    def test_truncation(self):
        with tempfile.NamedTemporaryFile() as file:
            file.write(b'GGUF')
            file.flush()
            with self.assertRaises(ValueError):
                info.inspect(file.name)


if __name__ == '__main__':
    unittest.main()
