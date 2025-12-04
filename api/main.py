import asyncio
import json
import logging
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
import enum
from dataclasses import replace, asdict
from typing import Optional
from functools import reduce

from flask import Flask, jsonify, request, Response

# 将项目根目录添加到 sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# =====================================================================================
# API 对 LDDC 源程序的依赖说明 (API's Dependencies on LDDC Source Code)
#
# 本 API 服务器的核心功能严重依赖于 LDDC 项目的内部模块。
# 如果 LDDC 源程序被更新，以下部分是维护此 API 时需要重点关注的：
#
# 1. 核心API调用 (Core API Calls):
#    - `LDDC.core.api.lyrics.search`: 用于实现并行搜索功能。
#    - `LDDC.core.api.lyrics.get_lyrics`: 用于获取最终的歌词文件。
#    如果这些函数的签名（参数、返回值）或行为发生变化，本文件中的调用逻辑可能需要同步修改。
#
# 2. 数据模型 (Data Models):
#    - `LDDC.common.models._info.SongInfo`: 这是最核心的歌曲信息对象，API的两个接口都围绕它进行操作。
#      它的 `.from_dict()` 和 `.format_duration` 方法至关重要。
#    - `LDDC.common.models._lyrics.Lyrics`: 歌词数据对象，是 `get_lyrics` 的返回类型。
#    - `LDDC.common.models._enums`: `Source`, `LyricsFormat`, `SearchType` 等枚举类型。
#    如果这些数据模型的结构发生变化（例如增删字段），本文件的序列化和反序列化逻辑可能需要调整。
#
# 3. 版本号 (Version):
#    - `LDDC.common.version.__version__`: 用于在API文档中显示版本号。
# =====================================================================================

from LDDC.common.models._lyrics import Lyrics
from LDDC.common.models._info import SongInfo, Artist
from LDDC.common.models._enums import Source, LyricsFormat, SearchType
from LDDC.core.api.lyrics import search, get_lyrics
from LDDC.common.version import __version__
from LDDC.core.auto_fetch_sync import auto_fetch
from LDDC.common.exceptions import LDDCError, LyricsNotFoundError, NotEnoughInfoError

# 源名称到中文的映射
SOURCE_MAP = {
    Source.KG: "酷狗音乐",
    Source.NE: "网易云音乐",
    Source.QM: "QQ音乐",
}

# 初始化 Flask 应用
app = Flask(__name__)

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def search_lyrics_api(keyword: str):
    """
    API 搜索功能的同步版本
    """
    sources_to_search = [Source.QM, Source.NE, Source.KG]  # 定义了交错排序的优先级
    results_by_source = {source: [] for source in sources_to_search}

    with ThreadPoolExecutor(max_workers=len(sources_to_search)) as executor:
        future_to_source = {
            executor.submit(search, source, keyword, SearchType.SONG): source
            for source in sources_to_search
        }

        for future in as_completed(future_to_source):
            source = future_to_source[future]
            try:
                result = future.result()
                if result:
                    results_by_source[source] = list(result)
            except Exception as e:
                source_name = SOURCE_MAP.get(source, str(source))
                logging.error(f"搜索源 {source_name} 时出错: {e}")

    # 将结果交错合并以获得更平衡的列表
    final_results = []
    max_len = 0
    if any(results_by_source.values()):
        max_len = max(len(v) for v in results_by_source.values())

    for i in range(max_len):
        for source in sources_to_search:
            if i < len(results_by_source[source]):
                final_results.append(results_by_source[source][i])

    return final_results

def make_serializable(obj):
    """递归地将包含枚举等特殊类型的对象转换为可JSON序列化的字典。"""
    if isinstance(obj, dict):
        return {k: make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, frozenset)):
        return [make_serializable(i) for i in obj]
    if isinstance(obj, enum.Enum):
        return obj.value
    return obj

def stringify(value):
    """健壮地将值转换为字符串，如果是列表则用 ' / ' 连接"""
    if isinstance(value, list):
        return " / ".join(map(str, value))
    return str(value) if value is not None else ""

@app.route("/")
def read_root():
    return jsonify({"message": f"欢迎使用 LDDC Lyrics API (Flask Version {__version__})"})

@app.route("/api/search", methods=['GET'])
def search_lyrics_endpoint():
    keyword = request.args.get('keyword')
    if not keyword:
        return jsonify({"error": "keyword is required"}), 400
        
    results_list = search_lyrics_api(keyword)
    
    response_data = []
    for song_info in results_list:
        serializable_info_dict = make_serializable(asdict(song_info))
        song_info_json_str = json.dumps(serializable_info_dict)

        ordered_item = {
            "title": stringify(song_info.title),
            "artist": stringify(song_info.artist),
            "album": stringify(song_info.album),
            "duration": song_info.format_duration,
            "song_info_json": song_info_json_str,
            "source": SOURCE_MAP.get(song_info.source, str(song_info.source)),
        }
        response_data.append(ordered_item)

    # Manually dump JSON to preserve key order and handle encoding
    json_string = json.dumps(response_data, ensure_ascii=False)
    return Response(json_string, mimetype='application/json; charset=utf-8')


@app.route("/api/match_lyrics", methods=['GET'])
def match_lyrics_endpoint():
    """
    根据歌曲信息自动匹配并返回最佳的LRC歌词。
    支持多种参数组合，并能处理歌名/歌手互换的情况。
    """
    title = request.args.get('title')
    artist = request.args.get('artist')
    keyword = request.args.get('keyword')
    album = request.args.get('album')
    duration_str = request.args.get('duration')
    duration = int(duration_str) if duration_str and duration_str.isdigit() else None

    song_info_to_try: list[SongInfo] = []

    # 优先处理 title 和 artist
    if title and artist:
        # 正常顺序
        song_info_to_try.append(
            SongInfo(source=Source.QM, title=title, artist=Artist(artist), album=album, duration=duration)
        )
        # 交换顺序，以提高容错性
        song_info_to_try.append(
            SongInfo(source=Source.QM, title=artist, artist=Artist(title), album=album, duration=duration)
        )
    # 其次处理 keyword
    elif keyword:
        # 将 keyword 作为路径处理，auto_fetch 可以利用其 .stem
        from pathlib import Path
        song_info_to_try.append(
            SongInfo(source=Source.QM, path=Path(keyword), duration=duration)
        )
    else:
        return Response("[00:00.00]必须提供 'title' 和 'artist' 或 'keyword' 参数", mimetype="text/plain; charset=utf-8", status=400)

    for info in song_info_to_try:
        try:
            # 调用核心匹配函数
            lyrics: Optional[Lyrics] = auto_fetch(info)
            
            if lyrics and lyrics.get("orig"):
                langs = ["orig"]
                if lyrics.get("ts"):
                    langs.append("ts")
                
                lrc_text = lyrics.to(lyrics_format=LyricsFormat.VERBATIMLRC, langs=langs)
                final_lrc = re.sub(r"\[tool:.*?\]\n\n", "", lrc_text, count=1)
                return Response(final_lrc, mimetype="text/plain; charset=utf-8")

        except (LyricsNotFoundError, NotEnoughInfoError):
            # 这是预期的失败，继续尝试下一个候选
            continue
        except Exception as e:
            # 记录意外错误，但仍然继续尝试
            logging.error(f"为 '{info.artist_title()}' 匹配时发生未知错误", exc_info=True)
            continue
    
    # 所有尝试都失败了
    return Response("[00:00.00]未找到匹配的歌词", mimetype="text/plain; charset=utf-8", status=404)


@app.route("/api/get_lyrics_by_id", methods=['GET'])
def get_lyrics_by_id_api():
    """
    根据歌曲ID和来源获取歌词，并以LRC格式返回。
    """
    song_info_json = request.args.get('song_info_json')
    if not song_info_json:
        return Response("[00:00.00]缺少参数 song_info_json", mimetype="text/plain; charset=utf-8", status=400)

    try:
        song_info_dict = json.loads(song_info_json)
        original_song_info: SongInfo = SongInfo.from_dict(song_info_dict)

        song_info_for_trans = replace(original_song_info, language=0)

        lyrics: Optional[Lyrics] = get_lyrics(song_info_for_trans)

        if not lyrics or not lyrics.get("orig"):
            return Response("[00:00.00]没有找到歌词", mimetype="text/plain; charset=utf-8")

        langs = ["orig"]
        if lyrics.get("ts"):
            langs.append("ts")

        lrc_text = lyrics.to(
            lyrics_format=LyricsFormat.VERBATIMLRC,
            langs=langs
        )
        
        final_lrc = re.sub(r"\[tool:.*?\]\n\n", "", lrc_text, count=1)

        return Response(final_lrc, mimetype="text/plain; charset=utf-8")

    except Exception as e:
        logging.error(f"调用 get_lyrics 时发生错误", exc_info=True)
        return Response(f"获取歌词时出错: {e}", mimetype="text/plain; charset=utf-8", status=500)


if __name__ == "__main__":
    # 建议在生产环境中使用 waitress 或 Gunicorn 等 WSGI 服务器
    app.run(host="0.0.0.0", port=5000) 
