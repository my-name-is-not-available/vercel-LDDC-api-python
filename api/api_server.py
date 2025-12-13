import asyncio
import json
import logging
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
import enum
from contextlib import asynccontextmanager
from dataclasses import replace
from typing import Optional
from functools import reduce

from fastapi import FastAPI, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, PlainTextResponse

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
from kuwo import fetch_and_convert_kuwo_lrc

# 源名称到中文的映射
SOURCE_MAP = {
    Source.KG: "酷狗音乐",
    Source.NE: "网易云音乐",
    Source.QM: "QQ音乐",
    Source.KW: "酷我音乐",
}

# 全局线程池
executor = ThreadPoolExecutor(max_workers=10)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Lifespan anager for the application.
    # Code before the yield runs on startup.
    yield
    # Code after the yield runs on shutdown.
    executor.shutdown(wait=True)
    logging.info("线程池已成功关闭。")

# 初始化 FastAPI 应用
app = FastAPI(
    title="LDDC Lyrics API",
    description="一个用于获取歌词的API服务，基于LDDC项目。",
    version=__version__,
    lifespan=lifespan,
)

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def search_lyrics_api(keyword: str, sources_param: Optional[str] = None):
    """
    API 搜索功能的同步版本，支持选择词源
    
    :param keyword: 搜索关键词
    :param sources_param: 词源选择，格式为逗号分隔的字符串，如"qm,ne,kg"，为空则选择所有词源
    """
    # 默认所有词源
    all_sources = [Source.QM, Source.NE, Source.KG, Source.KW]
    
    # 解析词源参数
    selected_sources = all_sources
    if sources_param:
        source_map = {
            "qm": Source.QM,
            "ne": Source.NE,
            "kg": Source.KG,
            "kw": Source.KW,
        }
        
        sources_list = [s.strip().lower() for s in sources_param.split(",")]
        selected_sources = [source_map.get(s) for s in sources_list if s in source_map]
        
        # 如果选择无效，则默认使用所有词源
        if not selected_sources:
            selected_sources = all_sources
    
    results_by_source = {source: [] for source in all_sources if source in selected_sources}
    
    with ThreadPoolExecutor(max_workers=len(results_by_source)) as executor:
        future_to_source = {
            executor.submit(search, source, keyword, SearchType.SONG): source
            for source in results_by_source.keys()
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
    
    # 保持交错排序逻辑，但只使用选定的词源
    for i in range(max_len):
        for source in all_sources:  # 使用所有源的顺序，但跳过未选中的
            if source in results_by_source and i < len(results_by_source[source]):
                final_results.append(results_by_source[source][i])
    
    return final_results


@app.get("/")
def read_root():
    return {"message": "欢迎使用 LDDC Lyrics API", "docs": "/docs"}

@app.get("/api/search")
async def search_lyrics_endpoint(keyword: str, sources: Optional[str] = None):
    loop = asyncio.get_event_loop()
    results_list = await loop.run_in_executor(executor, search_lyrics_api, keyword, sources)
    
    response_data = []
    for song_info in results_list:
        serializable_info_dict = jsonable_encoder(song_info)
        song_info_json_str = json.dumps(serializable_info_dict)

        def stringify(value):
            if isinstance(value, list):
                return " / ".join(map(str, value))
            return str(value) if value is not None else ""

        response_item = {
            "title": stringify(song_info.title),
            "artist": stringify(song_info.artist),
            "album": stringify(song_info.album),
            "duration": song_info.format_duration,
            "source": SOURCE_MAP.get(song_info.source, str(song_info.source)),
            "song_info_json": song_info_json_str,
        }
        response_data.append(response_item)

    return JSONResponse(content=response_data)


@app.get("/api/match_lyrics", response_class=PlainTextResponse)
async def match_lyrics_endpoint(
    title: Optional[str] = Query(None, description="歌曲标题"),
    artist: Optional[str] = Query(None, description="歌手名称"),
    keyword: Optional[str] = Query(None, description="关键词（如文件名），用于匹配"),
    album: Optional[str] = Query(None, description="专辑名称"),
    duration: Optional[int] = Query(None, description="歌曲时长（毫秒）"),
    include_romaji: Optional[str] = Query(None, description="是否包含罗马音。接受 'true', '1', 'yes'（不区分大小写）。默认为 false。罗马音仅在源数据包含时才会出现。")
):
    """
    根据歌曲信息自动匹配并返回最佳的LRC歌词。
    支持多种参数组合，并能处理歌名/歌手互换的情况。
    """
    loop = asyncio.get_event_loop()
    song_info_to_try: list[SongInfo] = []
    
    # 解析 include_romaji 参数
    should_include_romaji = include_romaji and include_romaji.lower() in ('true', '1', 'yes')

    if title and artist:
        song_info_to_try.append(
            SongInfo(source=Source.QM, title=title, artist=Artist(artist), album=album, duration=duration)
        )
        song_info_to_try.append(
            SongInfo(source=Source.QM, title=artist, artist=Artist(title), album=album, duration=duration)
        )
    elif keyword:
        from pathlib import Path
        song_info_to_try.append(
            SongInfo(source=Source.QM, path=Path(keyword), duration=duration)
        )
    else:
        return PlainTextResponse(content="[00:00.00]必须提供 'title' 和 'artist' 或 'keyword' 参数", status_code=400, media_type="text/plain; charset=utf-8")

    for info in song_info_to_try:
        try:
            lyrics: Optional[Lyrics] = await loop.run_in_executor(executor, auto_fetch, info)
            if lyrics and lyrics.get("orig"):
                langs = ["orig"]
                if should_include_romaji and lyrics.get("roma"):
                    langs.append("roma")
                if lyrics.get("ts"):
                    langs.append("ts")
                lrc_text = lyrics.to(lyrics_format=LyricsFormat.VERBATIMLRC, langs=langs)
                final_lrc = re.sub(r"\[tool:.*?\]\n\n", "", lrc_text, count=1)
                return PlainTextResponse(content=final_lrc, media_type="text/plain; charset=utf-8")
        except (LyricsNotFoundError, NotEnoughInfoError):
            continue
        except Exception as e:
            logging.error(f"为 '{info.artist_title()}' 匹配时发生未知错误", exc_info=True)
            continue
            
    return PlainTextResponse(content="[00:00.00]未找到匹配的歌词", status_code=404, media_type="text/plain; charset=utf-8")


@app.get("/api/get_lyrics_by_id", response_class=PlainTextResponse)
async def get_lyrics_by_id_api(
    song_info_json: str,
    include_romaji: Optional[str] = Query(None, description="是否包含罗马音。接受 'true', '1', 'yes'（不区分大小写）。默认为 false。罗马音仅在源数据包含时才会出现。")
):
    """
    根据歌曲ID和来源获取歌词，并以LRC格式返回。
    """
    try:
        loop = asyncio.get_event_loop()
        
        # 解析 include_romaji 参数
        should_include_romaji = include_romaji and include_romaji.lower() in ('true', '1', 'yes')

        # 1. 将 JSON 字符串解析为字典, 并重建 SongInfo 对象
        song_info_dict = json.loads(song_info_json)
        original_song_info = SongInfo.from_dict(song_info_dict)

        # 2. 关键修复：使用 replace() 创建一个新的实例，并强制设置 language=0 以获取翻译
        song_info_for_trans = replace(original_song_info, language=0)

        # 3. 使用修改后的 song_info 调用 get_lyrics
        lyrics: Optional[Lyrics] = await loop.run_in_executor(executor, get_lyrics, song_info_for_trans)

        if not lyrics or not lyrics.get("orig"):
            return PlainTextResponse(content="[00:00.00]没有找到歌词", media_type="text/plain; charset=utf-8")

        # 4. 确定需要的语言，如果存在翻译则加入
        langs = ["orig"]
        if should_include_romaji and lyrics.get("roma"):
            langs.append("roma")
        if lyrics.get("ts"):
            langs.append("ts")

        # 5. 直接调用Lyrics对象的to方法进行转换，使用逐字格式
        lrc_text = lyrics.to(
            lyrics_format=LyricsFormat.VERBATIMLRC,
            langs=langs
        )
        
        # 6. 移除可选的 tool 标签行，让歌词更纯净
        final_lrc = re.sub(r"\[tool:.*?\]\n\n", "", lrc_text, count=1)

        return PlainTextResponse(content=final_lrc, media_type="text/plain; charset=utf-8")

    except Exception as e:
        logging.error(f"调用 get_lyrics 时发生错误", exc_info=True)
        return PlainTextResponse(content=f"获取歌词时出错: {e}", status_code=500, media_type="text/plain; charset=utf-8")


@app.get("/api/kuwo_lrc", response_class=PlainTextResponse)
async def get_kuwo_lrc_endpoint(music_id: int = Query(..., description="酷我音乐的歌曲ID")):
    """
    根据酷我音乐ID获取并转换逐字LRC歌词。
    """
    loop = asyncio.get_event_loop()
    try:
        lrc_text = await loop.run_in_executor(executor, fetch_and_convert_kuwo_lrc, music_id)
        if lrc_text:
            return PlainTextResponse(content=lrc_text, media_type="text/plain; charset=utf-8")
        else:
            return PlainTextResponse(content="[00:00.00]无法获取或转换歌词", status_code=404, media_type="text/plain; charset=utf-8")
    except Exception as e:
        logging.error(f"处理酷我歌词时发生错误 (music_id: {music_id})", exc_info=True)
        return PlainTextResponse(content=f"处理歌词时发生内部错误: {e}", status_code=500, media_type="text/plain; charset=utf-8")


if __name__ == "__main__":
    import uvicorn
    print("API 服务器正在启动...")
    print("访问 http://127.0.0.1:8000/docs 查看 API 文档")
    uvicorn.run(app, host="0.0.0.0", port=8000)
