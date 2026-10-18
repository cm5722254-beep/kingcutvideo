"""
Internationalization (i18n) Engine for King Video Cutter.
Supports instant runtime switching between Khmer and English without restarting the app.
"""

import json
import os
import sys
from typing import Dict, Any, Callable, List

def get_base_dir() -> str:
    """Returns base directory whether running from source or PyInstaller bundle."""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

class I18NManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(I18NManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.current_lang = "km"  # Khmer default
        self.translations: Dict[str, Dict[str, str]] = {}
        self._subscribers: List[Callable[[], None]] = []
        self.load_all_locales()

    def load_all_locales(self):
        """Loads all available json translation files from locales/ directory."""
        locales_dir = os.path.join(get_base_dir(), "locales")
        if not os.path.exists(locales_dir):
            return

        for filename in os.listdir(locales_dir):
            if filename.endswith(".json"):
                lang_code = os.path.splitext(filename)[0]
                filepath = os.path.join(locales_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        self.translations[lang_code] = json.load(f)
                except Exception as e:
                    print(f"Error loading locale {filename}: {e}", file=sys.stderr)

    def set_language(self, lang_code: str):
        """Switches current language and notifies all registered UI components immediately."""
        if lang_code in self.translations or lang_code in ["km", "en"]:
            self.current_lang = lang_code
            self.notify_subscribers()

    def subscribe(self, callback: Callable[[], None]):
        """Register a callback that gets called whenever language changes."""
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[], None]):
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def notify_subscribers(self):
        """Triggers all callbacks to re-translate UI strings dynamically."""
        for callback in self._subscribers:
            try:
                callback()
            except Exception as e:
                print(f"Error executing i18n callback: {e}", file=sys.stderr)

    def translate(self, key: str, **kwargs) -> str:
        """Fetch string by key in current language, falling back to English, then key itself."""
        current_dict = self.translations.get(self.current_lang, {})
        text = current_dict.get(key)
        if text is None:
            # Fallback to English
            en_dict = self.translations.get("en", {})
            text = en_dict.get(key, key)
        
        if kwargs and isinstance(text, str):
            try:
                text = text.format(**kwargs)
            except Exception:
                pass
        return text

# Global instance and convenient helper
_i18n = I18NManager()

def t(key: str, **kwargs) -> str:
    """Translate function used everywhere across the application."""
    return _i18n.translate(key, **kwargs)

def set_language(lang_code: str):
    _i18n.set_language(lang_code)

def get_current_language() -> str:
    return _i18n.current_lang

def subscribe_language_change(callback: Callable[[], None]):
    _i18n.subscribe(callback)
