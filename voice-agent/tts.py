"""
ElevenLabs text-to-speech synthesis.

Generates an MP3 file per utterance and returns its ID so main.py can
build a /audio/<id> URL for Twilio's <Play> verb.
"""

import os
import uuid
from pathlib import Path

from elevenlabs.client import ElevenLabs

_client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
_MODEL = "eleven_turbo_v2_5"  # lowest latency model

AUDIO_DIR = Path("/tmp/pill_buddy_audio")
AUDIO_DIR.mkdir(exist_ok=True)


def synthesize(text: str) -> str:
    """
    Synthesize text to an MP3 file and return its file_id.
    Caller constructs the public URL as {BASE_URL}/audio/{file_id}.
    """
    file_id = str(uuid.uuid4())
    path = AUDIO_DIR / f"{file_id}.mp3"

    audio_stream = _client.text_to_speech.convert(
        voice_id="EXAVITQu4vr4xnSDxMaL",  # Bella
        text=text,
        model_id=_MODEL,
        output_format="mp3_44100_128",
    )
    with open(path, "wb") as f:
        for chunk in audio_stream:
            f.write(chunk)

    return file_id
