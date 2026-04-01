#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
data_loader.py - API-First Data Loader for ChinaTour Skill

API 唯一数据加载器，无本地回退。
按需从 API 获取数据，成功后缓存到本地 SQLite。

Usage:
    from data_loader import APIFirstLoader

    loader = APIFirstLoader()
    data = loader.get_attraction_data('great-wall')
    stories = loader.get_stories('great-wall', 'L2')
"""

import os
import time
import logging
from typing import Dict, List, Optional, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Import the API client
from api_client import ChinaTourClient, DEFAULT_API_URL, DEFAULT_TIMEOUT

# ============== Constants ==============

# 字符串标识符到数字 ID 的映射
# 注意：ID 必须与后端数据库一致，错误的 ID 会导致数据错乱
ATTRACTION_ID_MAP = {
    'forbidden-city': 1,      # 故宫博物院
    'temple-of-heaven': 2,    # 天坛公园
    'summer-palace': 3,       # 颐和园
    'yuanmingyuan': 4,        # 圆明园遗址公园
    'great-wall': 5,          # 八达岭—慕田峪长城
    'grand-canal': 6,         # 北京大运河文化旅游景区
    'olympic-park': 7,        # 北京奥林匹克公园
    'ming-tombs': 8,          # 明十三陵景区
    'gongwangfu': 9,          # 恭王府景区
}


# ============== Data Loader Class ==============

class APIFirstLoader:
    """
    API 唯一数据加载器，无本地回退

    数据流：
    1. 检查 API 可用性（缓存 60s）
    2. API 可用 → 调用 API 获取数据 → 缓存到 SQLite
    3. API 不可用 → 尝试本地缓存
    4. 缓存也没有 → 返回 None
    """

    def __init__(
        self,
        api_url: str = DEFAULT_API_URL,
        timeout: int = DEFAULT_TIMEOUT,
        debug: bool = False
    ):
        self.api_client = ChinaTourClient(api_url, timeout, debug)
        self._health_check_cache = (None, 0)  # (result, timestamp)
        self.debug = debug

    def _log(self, message: str) -> None:
        """Debug logging"""
        if self.debug:
            logging.info(f"[APIFirstLoader] {message}")

    def _check_api_health(self) -> bool:
        """检查 API 可用性（缓存 60s）"""
        cached_result, cached_time = self._health_check_cache
        if time.time() - cached_time < 60:
            self._log(f"API health check cached: {cached_result}")
            return cached_result

        try:
            result = self.api_client.health_check().success
            self._health_check_cache = (result, time.time())
            self._log(f"API health check: {result}")
            return result
        except Exception as e:
            self._log(f"API health check failed: {e}")
            self._health_check_cache = (False, time.time())
            return False

    def _resolve_id(self, identifier) -> Optional[int]:
        """将字符串标识符解析为数字 ID"""
        if isinstance(identifier, int):
            return identifier
        return ATTRACTION_ID_MAP.get(identifier)

    def get_attraction_data(self, identifier) -> Optional[Dict[str, Any]]:
        """
        获取完整景点数据 - API 唯一数据源

        Args:
            identifier: 景点标识符（字符串如 'great-wall' 或数字 ID）

        Returns:
            景点数据 dict 或 None
        """
        attraction_id = self._resolve_id(identifier)
        self._log(f"get_attraction_data: identifier={identifier}, id={attraction_id}")

        if not attraction_id:
            self._log("ID 解析失败，返回 None")
            return None

        # 1. 尝试 API
        if self._check_api_health():
            data = self.api_client.get_attraction_data(attraction_id)
            if data:
                self._log(f"API 返回数据: basic={data.get('basic', {}).get('name')}")
                return data

        # 2. API 不可用，返回 None（不再回退到本地）
        self._log("API 不可用，无本地回退数据")
        return None

    def get_stories(self, identifier, depth: str = "L2") -> List[Dict]:
        """
        获取故事 - 使用 /ask 接口 RAG 检索

        Args:
            identifier: 景点标识符
            depth: 故事深度 ('L1', 'L2', 'L3')

        Returns:
            故事列表
        """
        attraction_id = self._resolve_id(identifier)
        if not attraction_id:
            return []

        result = self.api_client.ask(
            question=f"请介绍景点的历史和文化",
            attraction_id=attraction_id,
            depth=depth
        )

        if result.success and result.sources:
            # 过滤 story 类型
            stories = [s for s in result.sources if s.get('type') == 'story']
            self._log(f"API RAG 返回 {len(stories)} 条故事")
            return stories

        self._log("RAG 检索失败")
        return []


# ============== Convenience Functions ==============

_loader: Optional[APIFirstLoader] = None


def get_loader(api_url: str = DEFAULT_API_URL) -> APIFirstLoader:
    """Get or create singleton loader"""
    global _loader
    if _loader is None:
        _loader = APIFirstLoader(api_url=api_url)
    return _loader


def get_attraction_data(identifier) -> Optional[Dict[str, Any]]:
    """Convenience function for getting attraction data"""
    return get_loader().get_attraction_data(identifier)


def get_stories(identifier, depth: str = "L2") -> List[Dict]:
    """Convenience function for getting stories"""
    return get_loader().get_stories(identifier, depth)


# ============== CLI Interface ==============

def main():
    """CLI interface for testing"""
    import argparse

    parser = argparse.ArgumentParser(description='ChinaTour Data Loader')
    parser.add_argument('identifier', help='Attraction identifier (e.g., great-wall)')
    parser.add_argument('--depth', default='L2', choices=['L1', 'L2', 'L3'], help='Story depth')
    parser.add_argument('--api-url', default=DEFAULT_API_URL, help='API URL')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')

    args = parser.parse_args()

    loader = APIFirstLoader(api_url=args.api_url, debug=args.debug)

    # Get attraction data
    print(f"\n{'='*50}")
    print(f"Loading attraction: {args.identifier}")
    print(f"{'='*50}")

    data = loader.get_attraction_data(args.identifier)
    if data:
        print(f"\nBasic info: {data.get('basic', {}).get('name')}")
        print(f"Stories: {len(data.get('stories', []))} items")
        print(f"Photo Spots: {len(data.get('photoSpots', []))} items")
        print(f"Routes: {len(data.get('routes', []))} items")

        # Show stories
        stories = data.get('stories', [])
        if args.depth:
            stories = [s for s in stories if s.get('story_type') == args.depth]

        if stories:
            print(f"\nStories (depth={args.depth}):")
            for s in stories[:3]:  # Show first 3
                print(f"  [{s.get('story_type')}] {s.get('story_title')}")
                content = s.get('story_content', '')[:100]
                print(f"    {content}...")
        else:
            print(f"\nNo stories found for depth={args.depth}")
    else:
        print(f"\nFailed to load attraction: {args.identifier} (API may be unavailable)")


if __name__ == '__main__':
    main()
