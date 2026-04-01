#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
recommend_route.py - 根据用户画像推荐个性化游览路线

API 唯一数据源，无本地回退。

Usage:
    python recommend_route.py --attraction "forbidden-city" --profile "solo-photographer" --time "14:00"
"""

import argparse
import json
import os
import re
import sys
from typing import Dict, List, Optional
from datetime import datetime

# 导入 API-First 数据加载器
from data_loader import APIFirstLoader, ATTRACTION_ID_MAP

# 处理 Windows 控制台编码
if sys.platform == 'win32':
    import io
    if not isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')


# ============== 支持的景区列表（从 ATTRACTION_ID_MAP 派生）==============

def get_supported_attractions() -> List[str]:
    """获取所有支持的景区列表"""
    return list(ATTRACTION_ID_MAP.keys())


# ============== 用户画像模板 ==============

PROFILE_TEMPLATES = {
    "solo-photographer": {
        "companions": "solo",
        "interests": ["photography", "architecture"],
        "pace": "slow",
        "priority": "photo_spots",
        "description": "独自摄影爱好者，追求光影和人少机位"
    },
    "couple-romantic": {
        "companions": "couple",
        "interests": ["romance", "photography", "culture"],
        "pace": "medium",
        "priority": "romantic_spots",
        "description": "情侣出游，注重浪漫场景和合影点"
    },
    "family-kids": {
        "companions": "family",
        "interests": ["interactive", "fun", "education"],
        "pace": "slow",
        "priority": "rest_areas",
        "description": "带娃家庭，需要互动体验和休息点"
    },
    "history-buff": {
        "companions": "solo",
        "interests": ["history", "culture", "architecture"],
        "pace": "medium",
        "priority": "deep_explanation",
        "description": "历史爱好者，追求深度讲解和冷门景点"
    },
    "quick-visit": {
        "companions": "any",
        "interests": ["highlights"],
        "pace": "fast",
        "priority": "efficiency",
        "description": "快速游览，只看精华打卡点"
    }
}


# ============== 景区数据加载（API-First）==============

# 全局数据加载器实例
_loader: Optional[APIFirstLoader] = None


def get_loader() -> APIFirstLoader:
    """获取或创建数据加载器实例"""
    global _loader
    if _loader is None:
        _loader = APIFirstLoader()
    return _loader


def load_attraction_data(attraction_name: str) -> Optional[Dict]:
    """
    加载景区数据 - API 唯一数据源

    Args:
        attraction_name: 景区英文名（如 forbidden-city）

    Returns:
        景区数据字典，如加载失败返回 None
    """
    loader = get_loader()
    data = loader.get_attraction_data(attraction_name)

    if not data:
        return None

    # 转换为 recommend_route 期望的格式
    basic = data.get('basic', {})
    stories = data.get('stories', [])

    # 按景点名分组story，保留L2深度讲解内容
    spot_stories = {}
    for story in stories:
        title = story.get('story_title', '')
        if not title:
            continue
        story_type = story.get('story_type', 'L1')
        content = story.get('story_content', '')

        if title not in spot_stories:
            spot_stories[title] = {}

        # 优先用L2，其次L1
        if story_type == 'L2' or (story_type == 'L1' and 'L2' not in spot_stories[title]):
            spot_stories[title][story_type] = content

    # 转换为spots列表，每个spot包含故事内容
    spots = []
    for name, story_content in spot_stories.items():
        # 获取L2或L1内容
        content = story_content.get('L2') or story_content.get('L1', '')
        # 截取前200字作为简短介绍
        short_intro = content[:200] + '...' if len(content) > 200 else content
        # 计算故事长度（用于排序）
        story_length = len(story_content.get('L2', '')) or len(story_content.get('L1', ''))
        spots.append({
            "name": name,
            "stay_time": "30 分钟",
            "story_l2": story_content.get('L2', ''),
            "story_l1": story_content.get('L1', ''),
            "short_intro": short_intro,
            "highlight": "景区景点",
            "_story_length": story_length  # 用于排序
        })

    # 按故事长度排序（内容越丰富越重要，排在前面的核心景点）
    spots.sort(key=lambda x: x['_story_length'], reverse=True)

    return {
        "name": basic.get('name', attraction_name),
        "basic_info": basic,
        "spots": spots,
        "_source": 'api'
    }


# ============== 路线推荐逻辑 ==============

def recommend_route(attraction_data: Dict, profile_type: str, current_time: str = "14:00") -> Dict:
    """
    根据画像推荐个性化路线

    Args:
        attraction_data: 景区数据
        profile_type: 画像类型
        current_time: 当前时间

    Returns:
        推荐路线字典
    """
    # 获取画像信息
    profile = PROFILE_TEMPLATES.get(profile_type, PROFILE_TEMPLATES["quick-visit"])

    # 获取景点列表
    spots = attraction_data.get("spots", [])

    # 根据画像类型筛选和排序景点
    if profile_type == "solo-photographer":
        # 摄影爱好者：选择拍照好的景点，时间充裕
        recommended_spots = spots[:5] if len(spots) >= 5 else spots
        stay_multiplier = 1.2
    elif profile_type == "family-kids":
        # 家庭亲子：选择有趣的景点，增加休息
        recommended_spots = spots[:4] if len(spots) >= 4 else spots
        stay_multiplier = 0.8
    elif profile_type == "history-buff":
        # 历史爱好者：选择有历史价值的景点，深度讲解
        # 排序后内容丰富的在前，取前8个或全部（如果少于8个）
        recommended_spots = spots[:8] if len(spots) >= 8 else spots
        stay_multiplier = 1.5
    elif profile_type == "quick-visit":
        # 快速游览：只去核心景点
        recommended_spots = spots[:3] if len(spots) >= 3 else spots
        stay_multiplier = 0.6
    else:
        # 默认
        recommended_spots = spots[:5] if len(spots) >= 5 else spots
        stay_multiplier = 1.0

    # 构建路线
    route = []
    for spot in recommended_spots:
        # 解析停留时间
        stay_time_str = spot.get("stay_time", "30 分钟")
        try:
            # 提取数字
            numbers = re.findall(r'\d+', stay_time_str)
            stay_minutes = int(numbers[0]) if numbers else 30
        except:
            stay_minutes = 30

        # 根据画像类型决定讲解深度
        if profile_type == "history-buff":
            story_content = spot.get('story_l2') or spot.get('story_l1', '')
        else:
            story_content = spot.get('story_l1', '')

        route.append({
            "spot": spot.get("name", "景点"),
            "stay_minutes": int(stay_minutes * stay_multiplier),
            "photo_tip": f"{spot.get('highlight', '拍照点')}，根据光线调整角度",
            "culture_highlight": spot.get("highlight", "景区亮点"),
            "story_content": story_content,
            "next_direction": "继续下一站"
        })

    # 计算总时长
    total_minutes = sum(int(stop["stay_minutes"]) for stop in route)

    return {
        "attraction": attraction_data.get("name", "景区"),
        "profile": profile,
        "route": route,
        "total_duration_minutes": total_minutes,
        "current_time": current_time,
        "summary": f"为您定制{profile['description']}路线，共{len(route)}站，预计{total_minutes}分钟"
    }


def format_output(result: Dict) -> str:
    """格式化输出为人类可读格式"""
    if not result or "error" in result:
        return "抱歉，暂时无法获取该景区数据，请检查网络连接后重试"

    is_history_profile = "历史" in result['profile'].get('description', '')

    output = []
    output.append(f"{result['attraction']} 个性化路线推荐")
    output.append("")
    output.append(f"画像：{result['profile']['description']}")
    output.append(f"总时长：{result['total_duration_minutes']} 分钟")
    output.append(f"共 {len(result['route'])} 站")
    output.append("")
    output.append("=" * 40)
    output.append("")

    for i, stop in enumerate(result['route'], 1):
        output.append(f"【第{i}站】{stop['spot']}")
        output.append(f"  建议停留：{int(stop['stay_minutes'])} 分钟")

        # 如果有故事内容，输出讲解
        story = stop.get('story_content', '')
        if story:
            if is_history_profile:
                # 历史爱好者：输出完整L2讲解
                output.append(f"  讲解：{story}")
            else:
                # 其他：输出简短介绍
                output.append(f"  简介：{stop.get('short_intro', story[:100])}")

        output.append(f"  拍照：{stop['photo_tip']}")
        output.append(f"  亮点：{stop['culture_highlight']}")
        output.append(f"  方向：{stop['next_direction']}")
        output.append("")

    output.append("=" * 40)
    output.append("")
    output.append("准备好出发了吗？")
    output.append("1. 开始导览")
    output.append("2. 调整路线")
    output.append("3. 查看拍照机位")
    output.append("")
    output.append('> 直接回复数字即可（如回复"1"）')

    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(description="景区个性化路线推荐")
    parser.add_argument("--attraction", type=str, help="景区英文名（如 forbidden-city）")
    parser.add_argument("--profile", type=str, default="quick-visit",
                       help="用户画像类型：solo-photographer/couple-romantic/family-kids/history-buff/quick-visit")
    parser.add_argument("--time", type=str, default="14:00", help="当前时间")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--list", action="store_true", help="列出所有支持的景区")

    args = parser.parse_args()

    # 验证参数
    if not args.list and not args.attraction:
        print("错误：必须指定 --attraction 或使用 --list")
        print("使用 --list 查看所有支持的景区")
        return

    # 列出所有支持的景区
    if args.list:
        supported = get_supported_attractions()
        print("ChinaTour 支持的景区：")
        print("=" * 50)
        for i, attraction in enumerate(supported, 1):
            print(f"{i:2d}. {attraction}")
        print("=" * 50)
        print(f"总计：{len(supported)} 个景区")
        return

    # 加载景区数据
    attraction_data = load_attraction_data(args.attraction)
    supported = get_supported_attractions()

    if not attraction_data:
        print(f"抱歉，暂时无法获取景区 '{args.attraction}' 的数据")
        print(f"请检查网络连接后重试")
        print(f"支持的景区({len(supported)}个): {', '.join(supported)}")
        print("使用 --list 参数查看所有支持的景区")
        return

    # 推荐路线
    result = recommend_route(attraction_data, args.profile, args.time)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_output(result))


if __name__ == "__main__":
    main()
