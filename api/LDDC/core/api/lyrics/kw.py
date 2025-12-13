# SPDX-FileCopyrightText: Copyright (C) 2024-2025 沉默の金 <cmzj@cmzj.org>
# SPDX-License-Identifier: GPL-3.0-only

import base64
import re
import zlib
from typing import Optional

import requests

from LDDC.common.models._enums import LyricsFormat, SearchType, Source
from LDDC.common.models._info import APIResultList, Artist, SearchInfo, SongInfo
from LDDC.common.models._lyrics import Lyrics
from LDDC.core.parser.lrc import lrc2mdata
from LDDC.core.parser.utils import judge_lyrics_type

KEY = b"yeelion"


def search(keyword: str, search_type: SearchType, page: int = 1) -> Optional[APIResultList[SongInfo]]:
    """搜索酷我音乐"""
    if search_type != SearchType.SONG:
        return None  # 酷我目前只支持歌曲搜索

    pagesize = 30
    search_url = "https://search.kuwo.cn/r.s"
    params = {
        "all": keyword,
        "ft": "music",
        "rformat": "json",
        "encoding": "utf8",
        "vipver": "MUSIC_9.4.0.0_W1",
        "pcjson": "1",
        "rn": pagesize,
        "pn": page - 1,
    }

    try:
        response = requests.get(search_url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
    except (requests.exceptions.RequestException, ValueError):
        return None

    results = []
    if "abslist" in data:
        for item in data.get("abslist", []):
            try:
                duration_sec = int(item.get("DURATION", 0))
            except (ValueError, TypeError):
                duration_sec = 0

            song_info = SongInfo(
                source=Source.KW,
                title=item.get("SONGNAME", ""),
                artist=Artist(item.get("ARTIST", "")),
                album=item.get("ALBUM", ""),
                duration=duration_sec * 1000,
                id=item.get("DC_TARGETID", ""),
            )
            results.append(song_info)

    total = int(data.get("TOTAL", 0))
    start_index = (page - 1) * pagesize
    end_index = start_index + len(results) - 1 if results else start_index
    
    search_info = SearchInfo(source=Source.KW, keyword=keyword, search_type=search_type, page=page)
    return APIResultList(
        result=results, 
        info=search_info, 
        ranges=(start_index, end_index, total)
    )


def get_lyrics(song_info: SongInfo) -> Optional[Lyrics]:
    """获取酷我音乐歌词"""
    if not song_info.id:
        return None
    
    try:
        music_id = int(song_info.id)
    except (ValueError, TypeError):
        return None

    lrc_text = _fetch_and_convert_kuwo_lrc(music_id)
    if not lrc_text:
        return None

    tags, mdata = lrc2mdata(lrc_text, source=Source.KW)
    
    lyrics = Lyrics(info=song_info)
    lyrics.tags = tags
    lyrics.set_data(mdata)

    for lang, lrc_data in mdata.items():
        lyrics.types[lang] = judge_lyrics_type(lrc_data)

    return lyrics


# =====================================================================================
# 以下代码是从 kuwo.py 和 kuwo_flask_server.py 迁移和适配而来
# =====================================================================================

def _format_time(ms: float) -> str:
    if ms < 0:
        ms = 0
    minutes = int(ms / 60000)
    seconds = int((ms % 60000) / 1000)
    milliseconds = int(ms % 1000)
    return f"[{minutes:02d}:{seconds:02d}.{milliseconds:03d}]"


def _build_params(music_id: int, is_get_lyricx: bool = True) -> str:
    params_str = f"user=12345,web,web,web&requester=localhost&req=1&rid=MUSIC_{music_id}"
    if is_get_lyricx:
        params_str += "&lrcx=1"

    buf_str = params_str.encode("utf-8")
    key_len = len(KEY)

    output = bytearray(len(buf_str))
    for i in range(len(buf_str)):
        output[i] = buf_str[i] ^ KEY[i % key_len]

    encrypted_buffer = bytes(output)
    final_params = base64.b64encode(encrypted_buffer).decode("utf-8")
    return final_params


def _decode_lyrics(buf: bytes, is_get_lyricx: bool = True) -> str:
    if not buf.startswith(b"tp=content"):
        return ""

    try:
        header_end = buf.index(b"\r\n\r\n") + 4
        compressed_data = buf[header_end:]
        inflated_data = zlib.decompress(compressed_data)
    except Exception:
        return ""

    if not is_get_lyricx:
        return inflated_data.decode("gb18030", errors="ignore")
    else:
        base64_str = inflated_data.decode("utf-8", errors="ignore")
        buf_str = base64.b64decode(base64_str)
        key_len = len(KEY)
        output = bytearray(len(buf_str))

        for i in range(len(buf_str)):
            output[i] = buf_str[i] ^ KEY[i % key_len]

        decrypted_buffer = bytes(output)
        final_lrc = decrypted_buffer.decode("gb18030", errors="ignore")
        return final_lrc


def _convert_kuwo_lrc(raw_lrc: str) -> str:
    lines = raw_lrc.splitlines()
    kuwo_offset = 1.0
    kuwo_offset2 = 1.0

    kuwo_tag_match = re.search(r'\[kuwo:(\d+)\]', raw_lrc)
    if kuwo_tag_match:
        kuwo_value = int(kuwo_tag_match.group(1), 8)
        kuwo_offset = kuwo_value // 10
        kuwo_offset2 = kuwo_value % 10
        if kuwo_offset == 0 or kuwo_offset2 == 0:
            kuwo_offset = 1.0
            kuwo_offset2 = 1.0

    line_time_regex = re.compile(r'^\[(\d{2}:\d{2}\.\d{3})\](.*)$')
    word_regex = re.compile(r'<(-?\d+),(-?\d+)>([^<]*)')
    translation_regex = re.compile(r'[\u4e00-\u9fa5]')

    processed_lrc = []
    i = 0
    while i < len(lines):
        line = lines[i]
        line_time_match = line_time_regex.match(line)

        if not line_time_match:
            processed_lrc.append(line)
            i += 1
            continue

        content = line_time_match.group(2)
        if re.sub(r'<0,0>', '', content).strip() == '':
            i += 1
            continue
        
        line_time_str = line_time_match.group(1)
        time_parts = re.split(r'[:.]', line_time_str)
        line_start_time_ms = int(time_parts[0]) * 60000 + int(time_parts[1]) * 1000 + int(time_parts[2])

        is_translation_line = content.startswith('<0,0>') and translation_regex.search(content)

        if not is_translation_line:
            new_content = ''
            matches = list(word_regex.finditer(content))
            for j, match in enumerate(matches):
                offset, offset2, text = int(match.group(1)), int(match.group(2)), match.group(3)
                word_start_time_ms = abs((offset + offset2) / (kuwo_offset * 2))
                absolute_time_ms = line_start_time_ms + word_start_time_ms
                
                if j == 0:
                    new_content += text
                else:
                    new_content += f"{_format_time(absolute_time_ms)}{text}"

            calculated_end_timestamp = ''
            if matches:
                last_match = matches[-1]
                offset, offset2 = int(last_match.group(1)), int(last_match.group(2))
                word_start_time_ms = abs((offset + offset2) / (kuwo_offset * 2))
                word_duration_ms = abs((offset - offset2) / (kuwo_offset2 * 2))
                absolute_end_time_ms = line_start_time_ms + word_start_time_ms + word_duration_ms
                calculated_end_timestamp = _format_time(absolute_end_time_ms)
            
            translation_text = ''
            translation_end_timestamp = ''
            if i + 1 < len(lines):
                next_line = lines[i+1]
                next_line_time_match = line_time_regex.match(next_line)
                if next_line_time_match and next_line_time_match.group(2).startswith('<0,0>') and translation_regex.search(next_line_time_match.group(2)):
                    translation_text = re.sub(r'<0,0>', '', next_line_time_match.group(2)).strip()
                    
                    for j in range(i + 2, len(lines)):
                        future_line_match = line_time_regex.match(lines[j])
                        if future_line_match:
                            translation_end_timestamp = f"[{future_line_match.group(1)}]"
                            break
                    
                    if not translation_end_timestamp:
                        translation_end_timestamp = calculated_end_timestamp
                    
                    i += 1
            
            processed_lrc.append(f"[{line_time_str}]{new_content}{calculated_end_timestamp}")
            if translation_text:
                processed_lrc.append(f"[{line_time_str}]{translation_text}{translation_end_timestamp or calculated_end_timestamp}")
        
        i += 1
        
    return "\n".join(processed_lrc)


def _fetch_and_convert_kuwo_lrc(music_id: int) -> Optional[str]:
    params = _build_params(music_id, True)
    url = f"http://newlyric.kuwo.cn/newlyric.lrc?{params}"

    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()

        raw_lrc_data = response.content
        decoded_lrc = _decode_lyrics(raw_lrc_data, True)

        if decoded_lrc:
            # 直接返回逐字LRC，后续由 LrcParser 处理
            return _convert_kuwo_lrc(decoded_lrc)
        return None

    except requests.exceptions.RequestException:
        return None