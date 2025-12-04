def srt2mdata(srt_content: str):
    """
    将SRT字幕转换为元数据格式
    Args:
        srt_content: SRT格式的字幕内容
    Returns:
        转换后的元数据字典
    """
    # 简单的SRT解析实现
    import re
    
    # SRT时间格式: 00:00:01,000 --> 00:00:03,000
    time_pattern = re.compile(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})')
    
    lines = srt_content.strip().split('\n')
    subtitles = []
    
    i = 0
    while i < len(lines):
        # 跳过空行
        if not lines[i].strip():
            i += 1
            continue
        
        # 序号
        try:
            index = int(lines[i].strip())
            i += 1
        except ValueError:
            i += 1
            continue
        
        # 时间轴
        if i < len(lines):
            match = time_pattern.match(lines[i])
            if match:
                start_time, end_time = match.groups()
                i += 1
                
                # 字幕文本
                text_lines = []
                while i < len(lines) and lines[i].strip() and not lines[i].strip().isdigit() and not time_pattern.match(lines[i]):
                    text_lines.append(lines[i].strip())
                    i += 1
                
                subtitles.append({
                    'index': index,
                    'start': start_time,
                    'end': end_time,
                    'text': ' '.join(text_lines)
                })
            else:
                i += 1
        else:
            i += 1
    
    return {
        'format': 'srt',
        'subtitle_count': len(subtitles),
        'subtitles': subtitles
    }

# 确保导出
__all__ = ['srt2mdata']  # 如果已有__all__，添加进去
