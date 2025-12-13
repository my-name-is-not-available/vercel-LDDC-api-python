# SPDX-FileCopyrightText: Copyright (C) 2024-2025 沉默の金 <cmzj@cmzj.org>
# SPDX-License-Identifier: GPL-3.0-only
from collections.abc import Sequence

from .models import LyricInfo, SongInfo


class ErrorMsgTranslator:
    """错误信息翻译器"""

    def translate(self, msg: str) -> str:
        """翻译错误信息

        :param msg: 错误信息
        :return: 错误信息
        """
        # 移除了对PySide6的依赖，直接返回原始消息
        return msg


translator = ErrorMsgTranslator()


class LDDCError(Exception):
    def __init__(self, msg: str) -> None:
        super().__init__(translator.translate(msg))


class LyricsRequestError(LDDCError):
    """歌词请求错误"""

    def __init__(self, msg: str) -> None:
        super().__init__(translator.translate(msg))


class LyricsProcessingError(LDDCError):
    """歌词处理错误"""

    def __init__(self, msg: str) -> None:
        super().__init__(translator.translate(msg))


class LyricsDecryptError(LyricsProcessingError):
    """歌词解密错误"""

    def __init__(self, msg: str) -> None:
        super().__init__(translator.translate(msg))


class LyricsFormatError(LyricsProcessingError):
    """歌词格式错误"""

    def __init__(self, msg: str) -> None:
        super().__init__(translator.translate(msg))


class DecodingError(LDDCError):
    """解码错误"""

    def __init__(self, msg: str) -> None:
        super().__init__(translator.translate(msg))


class GetSongInfoError(LDDCError):
    """获取歌曲信息错误"""

    def __init__(self, msg: str) -> None:
        super().__init__(translator.translate(msg))


class FileTypeError(LDDCError):
    """文件类型错误"""

    def __init__(self, msg: str) -> None:
        super().__init__(translator.translate(msg))


class DropError(LDDCError):
    """拖放错误"""

    def __init__(self, msg: str) -> None:
        super().__init__(translator.translate(msg))


class APIError(LDDCError):
    """API调用错误"""

    def __init__(self, msg: str) -> None:
        super().__init__(translator.translate(msg))


class TranslateError(APIError):
    """翻译错误"""

    def __init__(self, msg: str) -> None:
        super().__init__(translator.translate(msg))


class APIParamsError(APIError):
    """API参数错误"""

    def __init__(self, msg: str) -> None:
        super().__init__(translator.translate(msg))


class APIRequestError(APIError):
    """API请求错误"""

    def __init__(self, msg: str) -> None:
        super().__init__(translator.translate(msg))


class LyricsNotFoundError(APIError):
    """没有歌词错误"""

    def __init__(self, msg: str, info: SongInfo | LyricInfo | None = None) -> None:
        super().__init__(translator.translate(msg))
        self.info = info


class AutoFetchError(LDDCError):
    """自动获取错误"""

    def __init__(self, msg: str) -> None:
        super().__init__(translator.translate(msg))


class NotEnoughInfoError(AutoFetchError):
    """信息不足错误"""

    def __init__(self, msg: str) -> None:
        super().__init__(translator.translate(msg))


class AutoFetchUnknownError(AutoFetchError):
    """自动获取未知错误"""

    def __init__(self, msg: str, excs: Sequence[Exception]) -> None:
        super().__init__(translator.translate(msg))
        self.exceptions = tuple(excs)
