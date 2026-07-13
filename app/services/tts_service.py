import os
import uuid

TTS_VOICES: dict[str, str] = {
    "en-US-JennyNeural": "American (Jenny)",
    "en-GB-SoniaNeural": "British (Sonia)",
    "en-AU-NatashaNeural": "Australian (Natasha)",
}


def _sanitize_ssml(text: str) -> str:
    """Escape XML special characters for SSML."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")


async def generate_audio(script: str, voice: str, output_dir: str = "static/audio") -> str:
    """Generate an MP3 audio file from text using edge-tts.

    Returns the relative path to the generated audio file (e.g. static/audio/uuid.mp3).
    """
    try:
        import edge_tts
    except ImportError:
        raise RuntimeError("edge-tts is not installed. Run: pip install edge-tts")

    if voice not in TTS_VOICES:
        voice = "en-US-JennyNeural"

    os.makedirs(output_dir, exist_ok=True)

    filename = f"{uuid.uuid4().hex}.mp3"
    filepath = os.path.join(output_dir, filename)

    # Replace ___ gaps with "blank" for natural TTS reading
    clean_script = script.replace("___", " [gap] ")

    try:
        communicate = edge_tts.Communicate(clean_script, voice)
        await communicate.save(filepath)
    except Exception:
        communicate = edge_tts.Communicate(script, voice)
        await communicate.save(filepath)

    return os.path.join("static", "audio", filename)
