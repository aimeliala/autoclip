"""Config is plain JSON, credentials never are. OS keyring preferred, memory fallback."""
from dataclasses import dataclass, asdict, fields
from pathlib import Path
import json
import os
import platform

APP_NAME = 'AutoClip Studio'
SECRETS = {'groq': 'GROQ_API_KEY', 'openrouter': 'OPENROUTER_API_KEY', 'kie': 'KIE_API_KEY'}
_SESSION_SECRETS = {}


def config_root():
    if platform.system() == 'Darwin':
        return Path.home() / 'Library' / 'Application Support' / 'AutoClip Studio'
    if platform.system() == 'Windows':
        base = Path(os.getenv('APPDATA', str(Path.home() / 'AppData' / 'Roaming')))
    else:
        base = Path(os.getenv('XDG_CONFIG_HOME', str(Path.home() / '.config')))
    return base / 'autoclip-studio'


@dataclass
class Settings:
    profile: str = 'auto'                   # auto/economy/balanced/quality
    speech: str = 'auto'                    # auto/subtitles/groq/local/none
    language: str = 'id'
    groq_model: str = 'whisper-large-v3-turbo'
    ai_provider: str = 'off'                # off/openrouter/kie/ollama
    ai_model: str = 'qwen/qwen3.5-flash'
    kie_endpoint: str = 'https://api.kie.ai/gemini-3-flash/v1/chat/completions'
    ollama_url: str = 'http://127.0.0.1:11434'
    ollama_model: str = 'qwen3.5:2b'
    clip_length: int = 48
    max_clips: int = 6
    output_resolution: int = 720
    captions: bool = True
    smart_crop: bool = True
    downloads_dir: str = str(Path.home() / ('Movies' if platform.system() == 'Darwin' else 'Videos') / 'AutoClip Studio')
    ffmpeg: str = 'ffmpeg'
    ffprobe: str = 'ffprobe'


def load_settings(path=None):
    path = Path(path) if path else config_root() / 'settings.json'
    if not path.exists():
        return Settings()
    data = json.loads(path.read_text(encoding='utf-8'))
    allowed = {f.name for f in fields(Settings)}
    return Settings(**{k: v for k, v in data.items() if k in allowed})


def save_settings(settings, path=None):
    path = Path(path) if path else config_root() / 'settings.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(settings)
    # Never allow credentials to be introduced into the plain JSON settings.
    for forbidden in ('groq_api_key', 'openrouter_api_key', 'kie_api_key', 'api_key'):
        data.pop(forbidden, None)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)
    if os.name != 'nt':
        path.chmod(0o600)
    return path


def set_secret(provider, key):
    """Save to OS keychain. If unavailable keep in volatile memory only; returns saved flag."""
    if provider not in SECRETS:
        raise ValueError('Unsupported secret provider')
    _SESSION_SECRETS[provider] = key
    try:
        import keyring
        if key:
            keyring.set_password('autoclip-studio', provider, key)
        else:
            try:
                keyring.delete_password('autoclip-studio', provider)
            except Exception:
                pass
        return True
    except Exception:
        return False


def get_secret(provider):
    if provider not in SECRETS:
        return ''
    if provider in _SESSION_SECRETS:
        return _SESSION_SECRETS[provider]
    env = os.getenv(SECRETS[provider], '')
    if env:
        return env
    try:
        import keyring
        return keyring.get_password('autoclip-studio', provider) or ''
    except Exception:
        return ''
