# SPDX-FileCopyrightText: Copyright (C) 2024-2025 沉默の金 <cmzj@cmzj.org>
# SPDX-License-Identifier: GPL-3.0-only
import platform

from .data.config import cfg
from .logger import logger

# 移除对PySide6的依赖，简化翻译功能

class _SignalHelper:
    def __init__(self):
        self.language_changed_callbacks = []

    def connect(self, callback):
        self.language_changed_callbacks.append(callback)

    def emit(self):
        for callback in self.language_changed_callbacks:
            try:
                callback()
            except Exception as e:
                logger.exception(f"Language changed signal error: {e}")


_signal_helper = _SignalHelper()
language_changed = _signal_helper


def get_system_language() -> tuple[str, str]:
    """获取系统语言

    返回: (语言代码, 脚本代码)
    """
    if platform.system() == 'Darwin':
        try:
            from Foundation import NSUserDefaults  # type: ignore[reportMissingImports]
            if (languages := NSUserDefaults.standardUserDefaults().objectForKey_("AppleLanguages")):
                language = languages[0]
                if language.startswith("zh"):
                    if language.startswith("zh-Hant"):
                        return "zh", "Hant"
                    return "zh", "Hans"
            return "en", ""
        except ImportError:
            logger.warning("Failed to get system language on macOS")
    elif platform.system() == 'Windows':
        import ctypes
        windll = ctypes.windll.kernel32
        lang_id = windll.GetUserDefaultUILanguage()
        lang_code = f"{lang_id & 0xFF}\{lang_id >> 8}"
        # 简化处理，只返回语言代码的前两位
        return lang_code[:2], ""
    else:
        # Linux及其他系统
        import locale
        lang_code, _ = locale.getdefaultlocale()
        if lang_code:
            if lang_code.startswith("zh"):
                if "HK" in lang_code or "TW" in lang_code:
                    return "zh", "Hant"
                return "zh", "Hans"
            return lang_code[:2], ""
    return "en", ""


def load_translation(emit: bool = True) -> None:
    """加载翻译

    在非GUI模式下，这个函数是简化的实现
    """
    lang = cfg.get("language", "auto")
    if lang == "auto":
        language, script = get_system_language()
        if language == "zh":
            lang = 'zh-Hant' if script == "Hant" else 'zh-Hans'
        elif language == "ja":
            lang = 'ja'
        else:
            lang = 'en'

    logger.info(f"Loading translation: {lang}")

    # 在非GUI模式下，我们不实际加载翻译文件
    # 但保持函数接口不变

    if emit:
        language_changed.emit()


# 添加一个简单的翻译函数替代Qt的tr
class Translator:
    def __init__(self):
        self.current_lang = "en"

    def tr(self, text: str) -> str:
        # 在实际应用中，可以在这里实现简单的翻译逻辑
        return text

translator = Translator()
# 保持与原有代码兼容的接口
tr = translator.tr


# 为了兼容原有代码，添加一个虚拟的QApplication类
class DummyQApplication:
    def __init__(self):
        pass

    def installTranslator(self, *args, **kwargs):
        pass

    def removeTranslator(self, *args, **kwargs):
        pass

# 创建一个全局的虚拟应用实例
app = DummyQApplication()
