"""マイク録音。"""
import io
import threading
import wave

import numpy as np

SAMPLE_RATE = 16000  # 音声認識モデルが前提とする 16kHz


class Recorder:
    def __init__(self):
        self._chunks: list[np.ndarray] = []
        self._stream = None
        self._lock = threading.Lock()

    def start(self):
        import sounddevice as sd  # マイクが無い環境でも他の部分をテストできるよう遅延 import

        with self._lock:
            self._chunks = []
            try:
                self._open(sd)
            except Exception as e:
                # 録音の部品(PortAudio)は、起動した時点のマイク一覧を覚えたままになる。
                # スリープ復帰・イヤホンの抜き差し・Bluetooth の接続切替でマイクが変わると、
                # 古い情報のまま開こうとして失敗するので、マイク一覧を読み直して1回だけやり直す。
                print(f"  マイクを開けなかったため、マイク一覧を読み直します（{e}）", flush=True)
                sd._terminate()
                sd._initialize()
                self._open(sd)

    def _open(self, sd):
        dev = sd.query_devices(kind="input")
        print(f"  使用マイク: {dev.get('name', '?')}", flush=True)
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="int16", callback=self._callback
        )
        self._stream.start()

    def _callback(self, indata, frames, time_info, status):
        self._chunks.append(indata.copy())

    def stop(self) -> np.ndarray:
        with self._lock:
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()
                self._stream = None
            if not self._chunks:
                return np.zeros(0, dtype=np.int16)
            return np.concatenate(self._chunks).reshape(-1)


def duration_sec(audio: np.ndarray) -> float:
    return len(audio) / SAMPLE_RATE


def is_silent(audio: np.ndarray, threshold: float = 150.0) -> bool:
    """音量(RMS = 波の大きさの平均)が小さすぎれば無音とみなす。"""
    if len(audio) == 0:
        return True
    rms = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))
    return rms < threshold


def to_wav_bytes(audio: np.ndarray) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(audio.astype(np.int16).tobytes())
    return buf.getvalue()
