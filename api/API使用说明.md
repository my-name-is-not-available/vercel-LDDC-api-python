# LDDC Lyrics API 使用说明

## 概述

LDDC Lyrics API 是一个基于 Flask 的歌词服务接口，支持歌词搜索、自动匹配和按ID获取功能。所有接口都支持罗马音（Romaji）输出。

## 启动服务器

```bash
python flask_server.py
```

服务器将在 `http://localhost:8000` 启动。

---

## API 接口说明

### 1. 根路径 - 服务状态

**端点**: `GET /`

**描述**: 检查服务是否正常运行

**示例**:
```bash
curl http://localhost:8000/
```

**响应**:
```json
{
  "message": "欢迎使用 LDDC Lyrics API (Flask Version x.x.x)"
}
```

---

### 2. 搜索歌词 - `/api/search`

**端点**: `GET /api/search`

**描述**: 根据关键词搜索歌曲信息

**参数**:
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| keyword | string | 是 | 搜索关键词（歌名、歌手等） |
| sources | string | 否 | 词源选择，逗号分隔，如 "qm,ne,kg,kw"<br>qm=QQ音乐, ne=网易云, kg=酷狗, kw=酷我<br>不填则搜索所有源 |

**示例**:
```bash
# 搜索所有源
curl "http://localhost:8000/api/search?keyword=夜に駆ける"

# 只搜索QQ音乐和网易云
curl "http://localhost:8000/api/search?keyword=夜に駆ける&sources=qm,ne"
```

**响应示例**:
```json
[
  {
    "title": "夜に駆ける",
    "artist": "YOASOBI",
    "album": "THE BOOK",
    "duration": "4:23",
    "song_info_json": "{...}",
    "source": "QQ音乐"
  }
]
```

---

### 3. 自动匹配歌词 - `/api/match_lyrics`

**端点**: `GET /api/match_lyrics`

**描述**: 根据歌曲信息自动匹配并返回最佳的LRC歌词

**参数**:
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| title | string | 条件必填* | 歌曲标题 |
| artist | string | 条件必填* | 歌手名称 |
| keyword | string | 条件必填* | 搜索关键词（当title和artist不可用时） |
| album | string | 否 | 专辑名称 |
| duration | integer | 否 | 歌曲时长（秒） |
| include_romaji | string | 否 | 是否包含罗马音<br>接受: 'true', '1', 'yes'（不区分大小写）<br>默认: false |

\* 必须提供 `title` + `artist` 或 `keyword` 其中一种组合

**示例**:

```bash
# 使用歌名和歌手（不含罗马音）
curl "http://localhost:8000/api/match_lyrics?title=夜に駆ける&artist=YOASOBI"

# 使用歌名和歌手（包含罗马音）
curl "http://localhost:8000/api/match_lyrics?title=夜に駆ける&artist=YOASOBI&include_romaji=true"

# 使用关键词
curl "http://localhost:8000/api/match_lyrics?keyword=夜に駆ける YOASOBI"

# 包含更多信息以提高匹配准确度
curl "http://localhost:8000/api/match_lyrics?title=夜に駆ける&artist=YOASOBI&album=THE BOOK&duration=263&include_romaji=1"
```

**响应示例（不含罗马音）**:
```
[00:00.00]夜に駆ける - YOASOBI
[00:01.50]沈むように溶けてゆくように
[00:05.80]二人だけの空が広がる夜に
...
[00:10.20]永远留在黑夜中
[00:14.50]只属于我们两人的天空在夜晚展开
...
```

**响应示例（包含罗马音）**:
```
[00:00.00]夜に駆ける - YOASOBI
[00:01.50]沈むように溶けてゆくように
[00:01.50]shizumu you ni tokete yuku you ni
[00:05.80]二人だけの空が広がる夜に
[00:05.80]futari dake no sora ga hirogaru yoru ni
...
[00:10.20]永远留在黑夜中
[00:14.50]只属于我们两人的天空在夜晚展开
...
```

---

### 4. 按ID获取歌词 - `/api/get_lyrics_by_id`

**端点**: `GET /api/get_lyrics_by_id`

**描述**: 根据歌曲ID和来源获取歌词，并以LRC格式返回

**参数**:
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| song_info_json | string | 是 | 歌曲信息的JSON字符串（从 `/api/search` 获取） |
| include_romaji | string | 否 | 是否包含罗马音<br>接受: 'true', '1', 'yes'（不区分大小写）<br>默认: false |

**示例**:

```bash
# 第一步：搜索歌曲
curl "http://localhost:8000/api/search?keyword=夜に駆ける" > search_result.json

# 第二步：从结果中提取 song_info_json（这里用变量代替）
SONG_INFO='{"source":"qm","id":"001abc","title":"夜に駆ける",...}'

# 第三步：获取歌词（不含罗马音）
curl -G "http://localhost:8000/api/get_lyrics_by_id" \
  --data-urlencode "song_info_json=$SONG_INFO"

# 获取歌词（包含罗马音）
curl -G "http://localhost:8000/api/get_lyrics_by_id" \
  --data-urlencode "song_info_json=$SONG_INFO" \
  --data-urlencode "include_romaji=true"
```

**使用 Python 测试**:
```python
import requests
import json

# 1. 搜索歌曲
response = requests.get('http://localhost:8000/api/search', params={'keyword': '夜に駆ける'})
results = response.json()

if results:
    # 2. 获取第一个结果的 song_info_json
    song_info_json = results[0]['song_info_json']
    
    # 3. 获取歌词（不含罗马音）
    lyrics_response = requests.get('http://localhost:8000/api/get_lyrics_by_id', 
                                   params={'song_info_json': song_info_json})
    print("不含罗马音:")
    print(lyrics_response.text)
    
    # 4. 获取歌词（包含罗马音）
    lyrics_with_romaji = requests.get('http://localhost:8000/api/get_lyrics_by_id', 
                                      params={
                                          'song_info_json': song_info_json,
                                          'include_romaji': 'true'
                                      })
    print("\n包含罗马音:")
    print(lyrics_with_romaji.text)
```

**响应格式**: 与 `/api/match_lyrics` 相同的 LRC 格式文本

---

## 罗马音功能说明

### 什么是罗马音？

罗马音（Romaji）是日语的拉丁字母转写形式，用于帮助不熟悉日语假名的用户阅读和演唱日语歌曲。

### 如何启用罗马音？

在 `/api/match_lyrics` 和 `/api/get_lyrics_by_id` 接口中，添加 `include_romaji` 参数：

- `include_romaji=true`
- `include_romaji=1`
- `include_romaji=yes`

### 重要说明

1. **数据源依赖**: 罗马音仅在源数据包含时才会出现。如果歌词源本身没有罗马音数据，即使设置了参数也不会返回罗马音。

2. **输出格式**: 当启用罗马音时，LRC文件中每行原文歌词后会紧跟一行对应的罗马音：
   ```
   [00:01.50]沈むように溶けてゆくように
   [00:01.50]shizumu you ni tokete yuku you ni
   ```

3. **翻译顺序**: 完整的输出顺序为：原文 → 罗马音 → 翻译
   ```
   [00:01.50]沈むように溶けてゆくように
   [00:01.50]shizumu you ni tokete yuku you ni
   [00:01.50]如同沉没般融化般
   ```

---

## 错误处理

### 常见错误响应

| HTTP状态码 | 说明 | 示例响应 |
|-----------|------|---------|
| 400 | 缺少必需参数 | `[00:00.00]缺少参数 song_info_json` |
| 404 | 未找到歌词 | `[00:00.00]未找到匹配的歌词` |
| 500 | 服务器内部错误 | `获取歌词时出错: ...` |

---

## 完整测试脚本

创建一个 `test_api.py` 文件：

```python
import requests

BASE_URL = 'http://localhost:8000'

def test_search():
    """测试搜索功能"""
    print("=== 测试搜索功能 ===")
    response = requests.get(f'{BASE_URL}/api/search', params={'keyword': '夜に駆ける'})
    print(f"状态码: {response.status_code}")
    results = response.json()
    print(f"找到 {len(results)} 个结果")
    if results:
        print(f"第一个结果: {results[0]['title']} - {results[0]['artist']}")
        return results[0]['song_info_json']
    return None

def test_match_lyrics():
    """测试自动匹配功能"""
    print("\n=== 测试自动匹配（不含罗马音）===")
    response = requests.get(f'{BASE_URL}/api/match_lyrics', 
                           params={'title': '夜に駆ける', 'artist': 'YOASOBI'})
    print(f"状态码: {response.status_code}")
    print(f"歌词前100字符:\n{response.text[:100]}")
    
    print("\n=== 测试自动匹配（包含罗马音）===")
    response = requests.get(f'{BASE_URL}/api/match_lyrics', 
                           params={
                               'title': '夜に駆ける', 
                               'artist': 'YOASOBI',
                               'include_romaji': 'true'
                           })
    print(f"状态码: {response.status_code}")
    print(f"歌词前200字符:\n{response.text[:200]}")

def test_get_lyrics_by_id(song_info_json):
    """测试按ID获取功能"""
    if not song_info_json:
        print("\n跳过按ID获取测试（没有搜索结果）")
        return
    
    print("\n=== 测试按ID获取（不含罗马音）===")
    response = requests.get(f'{BASE_URL}/api/get_lyrics_by_id', 
                           params={'song_info_json': song_info_json})
    print(f"状态码: {response.status_code}")
    print(f"歌词前100字符:\n{response.text[:100]}")
    
    print("\n=== 测试按ID获取（包含罗马音）===")
    response = requests.get(f'{BASE_URL}/api/get_lyrics_by_id', 
                           params={
                               'song_info_json': song_info_json,
                               'include_romaji': 'true'
                           })
    print(f"状态码: {response.status_code}")
    print(f"歌词前200字符:\n{response.text[:200]}")

if __name__ == '__main__':
    # 运行所有测试
    song_info = test_search()
    test_match_lyrics()
    test_get_lyrics_by_id(song_info)
    print("\n=== 测试完成 ===")
```

运行测试：
```bash
python test_api.py
```

---

## 使用浏览器测试

你也可以直接在浏览器中访问这些URL：

1. **测试服务状态**:
   ```
   http://localhost:8000/
   ```

2. **搜索歌曲**:
   ```
   http://localhost:8000/api/search?keyword=夜に駆ける
   ```

3. **自动匹配歌词（不含罗马音）**:
   ```
   http://localhost:8000/api/match_lyrics?title=夜に駆ける&artist=YOASOBI
   ```

4. **自动匹配歌词（包含罗马音）**:
   ```
   http://localhost:8000/api/match_lyrics?title=夜に駆ける&artist=YOASOBI&include_romaji=true
   ```

---

## 注意事项

1. 确保 LDDC 核心模块已正确安装
2. 某些歌词源可能需要网络连接
3. 罗马音的可用性取决于歌词源数据
4. 建议在生产环境使用 Gunicorn 或 Waitress 等 WSGI 服务器
5. 中文、日文等字符会以 UTF-8 编码返回

---

## 技术支持

如有问题，请检查：
- Flask 服务器是否正常运行
- 网络连接是否正常
- LDDC 依赖模块是否完整
- 日志输出中的错误信息
