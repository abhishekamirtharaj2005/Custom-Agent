"""Internationalization (i18n) system.

Supports 16 languages with lazy-loaded translation dictionaries.
All user-facing strings should go through t() for translation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

# Default language
_current_lang = "en"

# Translation dictionaries
TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "welcome": "Welcome to Hermclaw!",
        "goodbye": "Goodbye! See you next time.",
        "thinking": "Thinking...",
        "error": "An error occurred",
        "no_results": "No results found.",
        "tool_running": "Running tool: {tool_name}",
        "tool_done": "Tool completed: {tool_name}",
        "tool_failed": "Tool failed: {tool_name}",
        "model_switched": "Switched to model: {model}",
        "session_started": "Session started",
        "session_ended": "Session ended",
        "file_saved": "File saved: {path}",
        "file_read": "Reading file: {path}",
        "search_results": "Found {count} results",
        "cost_info": "Cost this session: ${cost:.4f}",
        "achievement_unlocked": "Achievement unlocked: {name}!",
        "pet_hungry": "Your pet is hungry!",
        "goal_created": "Goal created: {title}",
        "goal_completed": "Goal completed: {title}",
        "help_hint": "Type /help for available commands",
        "profile": "Profile: {name}",
        "doctor_ok": "All checks passed!",
        "doctor_fail": "Some checks failed.",
        "plugin_loaded": "Plugin loaded: {name}",
        "no_sessions": "No sessions found.",
        "streak": "Daily streak: {days} days!",
    },
    "es": {
        "welcome": "Bienvenido a Hermclaw!",
        "goodbye": "Adios! Hasta la proxima.",
        "thinking": "Pensando...",
        "error": "Ocurrio un error",
        "no_results": "No se encontraron resultados.",
        "tool_running": "Ejecutando herramienta: {tool_name}",
        "tool_done": "Herramienta completada: {tool_name}",
        "tool_failed": "Herramienta fallo: {tool_name}",
        "model_switched": "Cambiado al modelo: {model}",
        "session_started": "Sesion iniciada",
        "session_ended": "Sesion terminada",
        "file_saved": "Archivo guardado: {path}",
        "file_read": "Leyendo archivo: {path}",
        "search_results": "Se encontraron {count} resultados",
        "cost_info": "Costo de esta sesion: ${cost:.4f}",
        "achievement_unlocked": "Logro desbloqueado: {name}!",
        "help_hint": "Escribe /help para los comandos disponibles",
    },
    "de": {
        "welcome": "Willkommen bei Hermclaw!",
        "goodbye": "Tschuess! Bis zum naechsten Mal.",
        "thinking": "Denke nach...",
        "error": "Ein Fehler ist aufgetreten",
        "no_results": "Keine Ergebnisse gefunden.",
        "tool_running": "Werkzeug wird ausgefuehrt: {tool_name}",
        "model_switched": "Modell gewechselt zu: {model}",
        "help_hint": "Gib /help ein fuer verfuegbare Befehle",
    },
    "fr": {
        "welcome": "Bienvenue sur Hermclaw!",
        "goodbye": "Au revoir! A la prochaine.",
        "thinking": "Reflexion en cours...",
        "error": "Une erreur s'est produite",
        "no_results": "Aucun resultat trouve.",
        "help_hint": "Tapez /help pour les commandes disponibles",
    },
    "ja": {
        "welcome": "Hermclawへようこそ!",
        "goodbye": "さようなら! また次回。",
        "thinking": "考え中...",
        "error": "エラーが発生しました",
        "no_results": "結果が見つかりませんでした。",
        "help_hint": "/helpで利用可能なコマンドを確認",
    },
    "ko": {
        "welcome": "Hermclaw에 오신 것을 환영합니다!",
        "goodbye": "안녕히 가세요! 다음에 만나요.",
        "thinking": "생각 중...",
        "error": "오류가 발생했습니다",
        "no_results": "결과를 찾을 수 없습니다.",
    },
    "zh": {
        "welcome": "欢迎使用 Hermclaw!",
        "goodbye": "再见! 下次见。",
        "thinking": "思考中...",
        "error": "发生了一个错误",
        "no_results": "没有找到结果。",
        "help_hint": "输入 /help 查看可用命令",
    },
    "pt": {
        "welcome": "Bem-vindo ao Hermclaw!",
        "goodbye": "Adeus! Ate a proxima.",
        "thinking": "Pensando...",
        "error": "Ocorreu um erro",
    },
    "ru": {
        "welcome": "Добро пожаловать в Hermclaw!",
        "goodbye": "До свидания! До следующего раза.",
        "thinking": "Думаю...",
        "error": "Произошла ошибка",
    },
    "hi": {
        "welcome": "Hermclaw में आपका स्वागत है!",
        "goodbye": "अलविदा! अगली बार मिलते हैं।",
        "thinking": "सोच रहा हूँ...",
        "error": "एक त्रुटि हुई",
    },
    "tr": {
        "welcome": "Hermclaw'a hosgeldiniz!",
        "goodbye": "Hosca kalin! Bir dahaki sefere gorusuruz.",
        "thinking": "Dusunuyor...",
        "error": "Bir hata olustu",
    },
    "it": {
        "welcome": "Benvenuto su Hermclaw!",
        "goodbye": "Arrivederci! Alla prossima.",
        "thinking": "Sto pensando...",
        "error": "Si e verificato un errore",
    },
    "uk": {
        "welcome": "Ласкаво просимо до Hermclaw!",
        "goodbye": "До побачення! До наступного разу.",
        "thinking": "Думаю...",
        "error": "Сталася помилка",
    },
    "af": {
        "welcome": "Welkom by Hermclaw!",
        "goodbye": "Totsiens! Sien jou volgende keer.",
        "thinking": "Dink...",
    },
    "ga": {
        "welcome": "Failte go Hermclaw!",
        "goodbye": "Slan! Feicfidh me tu an chead uair eile.",
    },
    "hu": {
        "welcome": "Udvozoljuk a Hermclaw-ban!",
        "goodbye": "Viszontlatasra! Legkozelebb talalkozunk.",
        "thinking": "Gondolkodom...",
    },
}


def set_language(lang: str) -> None:
    """Set the active language."""
    global _current_lang
    if lang in TRANSLATIONS:
        _current_lang = lang
    else:
        _current_lang = "en"


def get_language() -> str:
    """Get the current language code."""
    return _current_lang


def t(key: str, **kwargs: Any) -> str:
    """Translate a key to the current language.

    Falls back to English if the key is not found in the current language.
    Supports string formatting with keyword arguments.
    """
    lang_dict = TRANSLATIONS.get(_current_lang, TRANSLATIONS["en"])
    text = lang_dict.get(key, TRANSLATIONS["en"].get(key, key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError):
            return text
    return text


def available_languages() -> list[str]:
    """List all available language codes."""
    return sorted(TRANSLATIONS.keys())


# Make Any available for type hints
from typing import Any
