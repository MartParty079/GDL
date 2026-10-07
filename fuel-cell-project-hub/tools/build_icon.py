"""Export the PNG master as a Windows ICO with seven PNG-encoded frames."""
import struct
from pathlib import Path
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage

SIZES = (16, 24, 32, 48, 64, 128, 256)


def build_icon(master, destination):
    image = QImage(str(master))
    if image.isNull() or image.width() != image.height():
        raise ValueError('The icon master must be a readable square PNG.')
    frames = []
    for size in SIZES:
        encoded = QByteArray()
        buffer = QBuffer(encoded)
        buffer.open(QIODevice.WriteOnly)
        if not image.scaled(size, size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).save(buffer, 'PNG'):
            raise ValueError('Could not export the icon frame.')
        buffer.close()
        frames.append(bytes(encoded))
    offset = 6 + 16 * len(SIZES)
    directory = []
    for size, frame in zip(SIZES, frames):
        directory.append(struct.pack('<BBBBHHII', size if size < 256 else 0, size if size < 256 else 0,
                                     0, 0, 1, 32, len(frame), offset))
        offset += len(frame)
    Path(destination).write_bytes(struct.pack('<HHH', 0, 1, len(frames)) + b''.join(directory) + b''.join(frames))


if __name__ == '__main__':
    assets = Path(__file__).resolve().parents[1] / 'assets'
    build_icon(assets / 'app_icon.png', assets / 'app_icon.ico')
    print('Exported Windows ICO:', ', '.join(str(size) for size in SIZES))
