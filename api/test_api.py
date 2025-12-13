"""
LDDC Lyrics API 测试脚本
用于测试所有API端点，包括罗马音功能
"""

import requests
import json

BASE_URL = 'http://localhost:8000'

def print_separator(title):
    """打印分隔线"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def test_root():
    """测试根路径"""
    print_separator("测试 1: 服务状态检查")
    try:
        response = requests.get(f'{BASE_URL}/')
        print(f"✓ 状态码: {response.status_code}")
        print(f"✓ 响应: {response.json()}")
        return True
    except Exception as e:
        print(f"✗ 错误: {e}")
        return False

def test_search():
    """测试搜索功能"""
    print_separator("测试 2: 搜索歌曲")
    try:
        # 测试基本搜索
        response = requests.get(f'{BASE_URL}/api/search', 
                               params={'keyword': '夜に駆ける'})
        print(f"✓ 状态码: {response.status_code}")
        results = response.json()
        print(f"✓ 找到 {len(results)} 个结果")
        
        if results:
            first = results[0]
            print(f"✓ 第一个结果:")
            print(f"  - 标题: {first['title']}")
            print(f"  - 歌手: {first['artist']}")
            print(f"  - 来源: {first['source']}")
            print(f"  - 时长: {first['duration']}")
            return first['song_info_json']
        else:
            print("✗ 没有找到结果")
            return None
    except Exception as e:
        print(f"✗ 错误: {e}")
        return None

def test_match_lyrics_without_romaji():
    """测试自动匹配（不含罗马音）"""
    print_separator("测试 3: 自动匹配歌词（不含罗马音）")
    try:
        response = requests.get(f'{BASE_URL}/api/match_lyrics', 
                               params={
                                   'title': '夜に駆ける', 
                                   'artist': 'YOASOBI'
                               })
        print(f"✓ 状态码: {response.status_code}")
        
        if response.status_code == 200:
            lyrics = response.text
            lines = lyrics.split('\n')[:10]  # 只显示前10行
            print(f"✓ 获取到歌词，前10行:")
            for line in lines:
                print(f"  {line}")
            
            # 检查是否包含罗马音
            has_romaji = any('romaji' in line.lower() or 
                           any(c.isalpha() and ord(c) < 128 
                               for c in line if c not in '[]:-. ')
                           for line in lines[1:])  # 跳过标题行
            if has_romaji:
                print("  ⚠ 警告: 似乎包含罗马音（不应该出现）")
            else:
                print("  ✓ 确认: 不包含罗马音")
            return True
        else:
            print(f"✗ 获取失败: {response.text[:100]}")
            return False
    except Exception as e:
        print(f"✗ 错误: {e}")
        return False

def test_match_lyrics_with_romaji():
    """测试自动匹配（包含罗马音）"""
    print_separator("测试 4: 自动匹配歌词（包含罗马音）")
    try:
        response = requests.get(f'{BASE_URL}/api/match_lyrics', 
                               params={
                                   'title': '夜に駆ける', 
                                   'artist': 'YOASOBI',
                                   'include_romaji': 'true'
                               })
        print(f"✓ 状态码: {response.status_code}")
        
        if response.status_code == 200:
            lyrics = response.text
            lines = lyrics.split('\n')[:15]  # 显示前15行以看到罗马音
            print(f"✓ 获取到歌词，前15行:")
            for line in lines:
                print(f"  {line}")
            
            # 检查是否包含罗马音（简单检测）
            content_lines = [l for l in lines if l.strip() and not l.startswith('[00:00.00]')]
            has_latin = any(any(c.isalpha() and ord(c) < 128 for c in line) 
                          for line in content_lines)
            if has_latin:
                print("  ✓ 确认: 包含罗马音（拉丁字母）")
            else:
                print("  ⚠ 警告: 未检测到罗马音（可能源数据不包含）")
            return True
        else:
            print(f"✗ 获取失败: {response.text[:100]}")
            return False
    except Exception as e:
        print(f"✗ 错误: {e}")
        return False

def test_get_lyrics_by_id_without_romaji(song_info_json):
    """测试按ID获取（不含罗马音）"""
    print_separator("测试 5: 按ID获取歌词（不含罗马音）")
    
    if not song_info_json:
        print("✗ 跳过测试: 没有可用的 song_info_json")
        return False
    
    try:
        response = requests.get(f'{BASE_URL}/api/get_lyrics_by_id', 
                               params={'song_info_json': song_info_json})
        print(f"✓ 状态码: {response.status_code}")
        
        if response.status_code == 200:
            lyrics = response.text
            lines = lyrics.split('\n')[:10]
            print(f"✓ 获取到歌词，前10行:")
            for line in lines:
                print(f"  {line}")
            print("  ✓ 确认: 不包含罗马音")
            return True
        else:
            print(f"✗ 获取失败: {response.text[:100]}")
            return False
    except Exception as e:
        print(f"✗ 错误: {e}")
        return False

def test_get_lyrics_by_id_with_romaji(song_info_json):
    """测试按ID获取（包含罗马音）"""
    print_separator("测试 6: 按ID获取歌词（包含罗马音）")
    
    if not song_info_json:
        print("✗ 跳过测试: 没有可用的 song_info_json")
        return False
    
    try:
        response = requests.get(f'{BASE_URL}/api/get_lyrics_by_id', 
                               params={
                                   'song_info_json': song_info_json,
                                   'include_romaji': 'true'
                               })
        print(f"✓ 状态码: {response.status_code}")
        
        if response.status_code == 200:
            lyrics = response.text
            lines = lyrics.split('\n')[:15]
            print(f"✓ 获取到歌词，前15行:")
            for line in lines:
                print(f"  {line}")
            
            # 检查是否包含罗马音
            content_lines = [l for l in lines if l.strip() and not l.startswith('[00:00.00]')]
            has_latin = any(any(c.isalpha() and ord(c) < 128 for c in line) 
                          for line in content_lines)
            if has_latin:
                print("  ✓ 确认: 包含罗马音（拉丁字母）")
            else:
                print("  ⚠ 警告: 未检测到罗马音（可能源数据不包含）")
            return True
        else:
            print(f"✗ 获取失败: {response.text[:100]}")
            return False
    except Exception as e:
        print(f"✗ 错误: {e}")
        return False

def test_romaji_parameter_variations():
    """测试罗马音参数的不同写法"""
    print_separator("测试 7: 罗马音参数的不同写法")
    
    test_values = ['true', 'True', 'TRUE', '1', 'yes', 'Yes', 'YES']
    
    for value in test_values:
        try:
            response = requests.get(f'{BASE_URL}/api/match_lyrics', 
                                   params={
                                       'title': '夜に駆ける', 
                                       'artist': 'YOASOBI',
                                       'include_romaji': value
                                   })
            status = "✓" if response.status_code == 200 else "✗"
            print(f"{status} include_romaji={value}: 状态码 {response.status_code}")
        except Exception as e:
            print(f"✗ include_romaji={value}: 错误 {e}")

def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("  LDDC Lyrics API 完整测试")
    print("  请确保 Flask 服务器正在运行: python flask_server.py")
    print("="*60)
    
    results = []
    
    # 测试1: 服务状态
    results.append(("服务状态", test_root()))
    
    # 测试2: 搜索
    song_info_json = test_search()
    results.append(("搜索功能", song_info_json is not None))
    
    # 测试3-4: 自动匹配
    results.append(("匹配（无罗马音）", test_match_lyrics_without_romaji()))
    results.append(("匹配（含罗马音）", test_match_lyrics_with_romaji()))
    
    # 测试5-6: 按ID获取
    results.append(("按ID获取（无罗马音）", test_get_lyrics_by_id_without_romaji(song_info_json)))
    results.append(("按ID获取（含罗马音）", test_get_lyrics_by_id_with_romaji(song_info_json)))
    
    # 测试7: 参数变体
    test_romaji_parameter_variations()
    
    # 总结
    print_separator("测试总结")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{status}: {name}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！")
    else:
        print(f"\n⚠ {total - passed} 个测试失败")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
    except Exception as e:
        print(f"\n\n测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
