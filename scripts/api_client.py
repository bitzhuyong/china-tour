#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
api_client.py - Backend API client for ChinaTour Skill

Usage:
    from api_client import ChinaTourClient

    client = ChinaTourClient()
    result = await client.ask("故宫开放时间?")
"""

import asyncio
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

# Handle Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')


# ============== Configuration ==============

# 默认 API 地址 - 云服务器
DEFAULT_API_URL = os.environ.get('CHINATOUR_API_URL', 'http://localhost:3000')
DEFAULT_TIMEOUT = int(os.environ.get('CHINATOUR_API_TIMEOUT', '90'))  # 90 seconds
# 统一认证 Token（从环境变量获取，不硬编码）
CHINATOUR_API_TOKEN = os.environ.get('CHINATOUR_API_TOKEN', '')


# ============== Data Classes ==============

@dataclass
class AskResult:
    """Result from ask API"""
    success: bool
    answer: str
    question: str
    language: str
    from_cache: bool
    sources: List[Dict]
    processing_time_ms: int
    error: Optional[str] = None


@dataclass
class HealthResult:
    """Result from health check"""
    success: bool
    status: str
    database: str
    ai: str
    embedding: str
    error: Optional[str] = None


@dataclass
class AttractionInfo:
    """Attraction information"""
    id: int
    name: str
    province: str
    city: str
    category: str
    rating: float


# ============== Client Class ==============

class ChinaTourClient:
    """
    Client for ChinaTour Backend API

    Example:
        client = ChinaTourClient()
        result = client.ask("故宫开放时间?")
        print(result.answer)
    """

    def __init__(
        self,
        api_url: str = DEFAULT_API_URL,
        timeout: int = DEFAULT_TIMEOUT,
        debug: bool = False
    ):
        self.api_url = api_url.rstrip('/')
        self.timeout = timeout
        self.debug = debug

    def _log(self, message: str) -> None:
        """Debug logging"""
        if self.debug:
            print(f"[ChinaTourClient] {message}")

    def _make_request(
        self,
        endpoint: str,
        method: str = 'GET',
        data: Optional[Dict] = None
    ) -> Dict:
        """
        Make HTTP request to API

        Args:
            endpoint: API endpoint (e.g., '/api/v1/guide/ask')
            method: HTTP method
            data: Request body data

        Returns:
            Response dict
        """
        url = f"{self.api_url}{endpoint}"
        headers = {'Content-Type': 'application/json'}

        # 添加 Bearer Token 认证（从环境变量获取，不硬编码）
        if CHINATOUR_API_TOKEN:
            headers['Authorization'] = f'Bearer {CHINATOUR_API_TOKEN}'

        self._log(f"Request: {method} {url}")

        try:
            if data:
                body = json.dumps(data, ensure_ascii=False).encode('utf-8')
                request = urllib.request.Request(
                    url,
                    data=body,
                    headers=headers,
                    method=method
                )
            else:
                request = urllib.request.Request(url, headers=headers, method=method)

            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                response_body = response.read().decode('utf-8')
                self._log(f"Response: {response.status}")
                return json.loads(response_body)

        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else ''
            self._log(f"HTTP Error: {e.code} - {error_body}")
            return {
                'success': False,
                'error': {
                    'code': f'HTTP_{e.code}',
                    'message': error_body or str(e)
                }
            }

        except urllib.error.URLError as e:
            self._log(f"URL Error: {e.reason}")
            return {
                'success': False,
                'error': {
                    'code': 'CONNECTION_ERROR',
                    'message': str(e.reason)
                }
            }

        except TimeoutError:
            self._log(f"Timeout after {self.timeout}s")
            return {
                'success': False,
                'error': {
                    'code': 'TIMEOUT',
                    'message': f'Request timed out after {self.timeout} seconds'
                }
            }

        except Exception as e:
            self._log(f"Error: {str(e)}")
            return {
                'success': False,
                'error': {
                    'code': 'UNKNOWN_ERROR',
                    'message': str(e)
                }
            }

    def ask(
        self,
        question: str,
        attraction_id: Optional[int] = None,
        language: str = 'auto',
        depth: str = 'L2',
        conversation_history: Optional[List[Dict]] = None,
        use_cache: bool = True
    ) -> AskResult:
        """
        Ask a question to AI guide

        Args:
            question: User question
            attraction_id: Optional attraction ID for context
            language: Language ('auto', 'zh', 'en')
            depth: Response depth ('L1', 'L2', 'L3')
            conversation_history: Previous conversation messages
            use_cache: Whether to use cached responses

        Returns:
            AskResult with answer and metadata
        """
        self._log(f"Ask: {question[:50]}...")

        start_time = time.time()

        data = {
            'question': question,
            'attraction_id': attraction_id,
            'language': language,
            'depth': depth,
            'conversation_history': conversation_history or [],
            'use_cache': use_cache,
        }

        response = self._make_request('/api/v1/guide/ask', 'POST', data)

        if not response.get('success'):
            return AskResult(
                success=False,
                answer='',
                question=question,
                language=language,
                from_cache=False,
                sources=[],
                processing_time_ms=int((time.time() - start_time) * 1000),
                error=response.get('error', {}).get('message', 'Unknown error')
            )

        result_data = response.get('data', {})
        meta = response.get('meta', {})

        return AskResult(
            success=True,
            answer=result_data.get('answer', ''),
            question=result_data.get('question', question),
            language=result_data.get('language', language),
            from_cache=result_data.get('from_cache', False),
            sources=result_data.get('sources', []),
            processing_time_ms=meta.get('processing_time_ms', 0)
        )

    def ask_with_fallback(self, question: str, **kwargs) -> AskResult:
        """
        Ask question - API first, fallback to local Q&A on failure

        Args:
            question: User question
            **kwargs: Arguments passed to ask()

        Returns:
            AskResult with answer and metadata
        """
        # 1. 尝试 API
        result = self.ask(question, **kwargs)
        if result.success:
            return result

        # 2. API 失败，查本地 Q&A 文件
        import logging
        logging.warning(f"[ChinaTourClient] API ask failed, trying local Q&A: {result.error}")

        local_answer = self._search_local_qa(question)
        if local_answer:
            return AskResult(
                success=True,
                answer=local_answer,
                question=question,
                language='zh',
                from_cache=False,
                sources=[],
                processing_time_ms=0
            )

        # 3. 本地也找不到，返回原始错误
        return result

    def _search_local_qa(self, question: str) -> Optional[str]:
        """
        Search local Q&A files for offline fallback

        Args:
            question: User question

        Returns:
            Answer string or None if not found
        """
        import re

        script_dir = os.path.dirname(os.path.abspath(__file__))
        qa_dir = os.path.join(script_dir, '..', 'references', 'culture-stories')

        if not os.path.exists(qa_dir):
            return None

        question_lower = question.lower()
        keywords = self._extract_keywords(question_lower)

        # 遍历本地文件搜索
        for province in os.listdir(qa_dir):
            province_path = os.path.join(qa_dir, province)
            if not os.path.isdir(province_path):
                continue
            for filename in os.listdir(province_path):
                if not filename.endswith('-stories.md'):
                    continue
                file_path = os.path.join(province_path, filename)
                answer = self._search_in_file(file_path, keywords)
                if answer:
                    return answer
        return None

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from question text"""
        # 去除标点，提取中文/英文词
        words = re.findall(r'[\u4e00-\u9fa5]+|[a-zA-Z0-9-]+', text)
        # 过滤停用词
        stopwords = {'的', '是', '在', '和', '了', '有', '怎么', '如何', '什么', '吗', '呢', '请', '介绍一下'}
        return [w for w in words if w not in stopwords and len(w) > 1]

    def _search_in_file(self, file_path: str, keywords: List[str]) -> Optional[str]:
        """Search for keywords in a single file"""
        import re
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 支持中英文句号：。和.
            sentence_end = r'[。.]'

            for keyword in keywords:
                if keyword.lower() in content.lower():
                    # 使用负向前瞻匹配包含关键词的完整句子
                    pattern = f'(?:(?!{sentence_end}).)*{re.escape(keyword)}(?:(?!{sentence_end}).)*{sentence_end}'
                    match = re.search(pattern, content)
                    if match:
                        return match.group(0)
            return None
        except Exception:
            return None

    def health_check(self) -> HealthResult:
        """
        Check API health status

        Returns:
            HealthResult with status of each component
        """
        self._log("Health check...")

        response = self._make_request('/api/v1/guide/health', 'GET')

        if not response.get('success'):
            return HealthResult(
                success=False,
                status='error',
                database='unknown',
                ai='unknown',
                embedding='unknown',
                error=response.get('error', {}).get('message', 'Health check failed')
            )

        data = response.get('data', {})
        checks = data.get('checks', {})

        return HealthResult(
            success=data.get('status') == 'healthy',
            status=data.get('status', 'unknown'),
            database=checks.get('database', 'unknown'),
            ai=checks.get('ai', 'unknown'),
            embedding=checks.get('embedding', 'unknown')
        )

    def get_attractions(
        self,
        search: Optional[str] = None,
        limit: int = 20
    ) -> List[AttractionInfo]:
        """
        Get list of attractions

        Args:
            search: Search keyword
            limit: Maximum number of results

        Returns:
            List of AttractionInfo
        """
        self._log(f"Get attractions: search={search}, limit={limit}")

        params = f"?limit={limit}"
        if search:
            params += f"&search={urllib.parse.quote(search)}"

        response = self._make_request(f'/api/v1/guide/attractions{params}', 'GET')

        if not response.get('success'):
            return []

        attractions = response.get('data', [])
        return [
            AttractionInfo(
                id=a.get('id', 0),
                name=a.get('name', ''),
                province=a.get('province', ''),
                city=a.get('city', ''),
                category=a.get('category', ''),
                rating=a.get('rating', 0)
            )
            for a in attractions
        ]

    def get_scenic_info(self, scenic_id: int) -> Optional[Dict[str, Any]]:
        """
        Get scenic spot information

        Args:
            scenic_id: Scenic spot ID

        Returns:
            Scenic spot data or None if not found
        """
        self._log(f"Get scenic info: id={scenic_id}")

        response = self._make_request(f'/api/v1/guide/scenic/{scenic_id}', 'GET')

        if not response.get('success'):
            return None

        return response.get('data')

    def get_attraction_data(self, attraction_id: int) -> Optional[Dict[str, Any]]:
        """
        Get attraction full data (includes basic, stories, photoSpots, routes)

        Args:
            attraction_id: Attraction ID

        Returns:
            Attraction data dict or None if not found
        """
        self._log(f"Get attraction data: id={attraction_id}")

        response = self._make_request(f'/api/v1/guide/attraction/{attraction_id}', 'GET')

        if not response.get('success'):
            return None

        return response.get('data')

    def quick_ask(self, question: str, language: str = 'auto') -> str:
        """
        Quick ask - returns just the answer string

        Args:
            question: User question
            language: Language preference

        Returns:
            Answer string or error message
        """
        result = self.ask(question, language=language)
        return result.answer if result.success else f"Error: {result.error}"


# ============== Convenience Functions ==============

_client: Optional[ChinaTourClient] = None


def get_client(api_url: str = DEFAULT_API_URL) -> ChinaTourClient:
    """Get or create singleton client"""
    global _client
    if _client is None:
        _client = ChinaTourClient(api_url=api_url)
    return _client


def ask(question: str, **kwargs) -> AskResult:
    """Convenience function for asking questions"""
    return get_client().ask(question, **kwargs)


def quick_ask(question: str, **kwargs) -> str:
    """Convenience function for quick ask"""
    return get_client().quick_ask(question, **kwargs)


def health_check() -> HealthResult:
    """Convenience function for health check"""
    return get_client().health_check()


# ============== CLI Interface ==============

def main():
    """CLI interface for testing"""
    import argparse

    parser = argparse.ArgumentParser(description='ChinaTour API Client')
    parser.add_argument('--api-url', default=DEFAULT_API_URL, help='API URL')
    parser.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT, help='Timeout in seconds')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Ask command
    ask_parser = subparsers.add_parser('ask', help='Ask a question')
    ask_parser.add_argument('question', help='Question to ask')
    ask_parser.add_argument('--attraction-id', type=int, help='Attraction ID')
    ask_parser.add_argument('--language', default='auto', choices=['auto', 'zh', 'en'], help='Language')
    ask_parser.add_argument('--depth', default='L2', choices=['L1', 'L2', 'L3'], help='Response depth')
    ask_parser.add_argument('--no-cache', action='store_true', help='Disable cache')

    # Health command
    subparsers.add_parser('health', help='Health check')

    # Attractions command
    attractions_parser = subparsers.add_parser('attractions', help='List attractions')
    attractions_parser.add_argument('--search', help='Search keyword')
    attractions_parser.add_argument('--limit', type=int, default=20, help='Limit')

    # Scenic command
    scenic_parser = subparsers.add_parser('scenic', help='Get scenic info')
    scenic_parser.add_argument('id', type=int, help='Scenic ID')

    # Attraction command (new - Step 0)
    attraction_parser = subparsers.add_parser('attraction', help='Get attraction full data')
    attraction_parser.add_argument('id', type=int, help='Attraction ID')

    args = parser.parse_args()

    client = ChinaTourClient(
        api_url=args.api_url,
        timeout=args.timeout,
        debug=args.debug
    )

    if args.command == 'ask':
        result = client.ask(
            question=args.question,
            attraction_id=args.attraction_id,
            language=args.language,
            depth=args.depth,
            use_cache=not args.no_cache
        )

        if result.success:
            print(f"\n{'='*50}")
            print(f"Question: {result.question}")
            print(f"{'='*50}")
            print(result.answer)
            print(f"{'='*50}")
            print(f"Language: {result.language}")
            print(f"From cache: {result.from_cache}")
            print(f"Processing time: {result.processing_time_ms}ms")
            if result.sources:
                print(f"Sources: {len(result.sources)}")
        else:
            print(f"Error: {result.error}")

    elif args.command == 'health':
        result = client.health_check()
        print(f"\nStatus: {result.status}")
        print(f"Database: {result.database}")
        print(f"AI: {result.ai}")
        print(f"Embedding: {result.embedding}")
        if result.error:
            print(f"Error: {result.error}")

    elif args.command == 'attractions':
        attractions = client.get_attractions(search=args.search, limit=args.limit)
        print(f"\nFound {len(attractions)} attractions:")
        for a in attractions:
            print(f"  [{a.id}] {a.name} ({a.province} {a.city}) - {a.category}")

    elif args.command == 'scenic':
        scenic = client.get_scenic_info(args.id)
        if scenic:
            print(f"\nScenic Info:")
            print(json.dumps(scenic, ensure_ascii=False, indent=2))
        else:
            print(f"Scenic spot not found: {args.id}")

    elif args.command == 'attraction':
        data = client.get_attraction_data(args.id)
        if data:
            print(f"\nAttraction Data:")
            print(f"Basic: {data.get('basic', {}).get('name', 'N/A')}")
            print(f"Stories: {len(data.get('stories', []))} items")
            print(f"Photo Spots: {len(data.get('photoSpots', []))} items")
            print(f"Routes: {len(data.get('routes', []))} items")
            if data.get('stories'):
                print("\nFirst story:")
                s = data['stories'][0]
                print(f"  [{s.get('story_type')}] {s.get('story_title')}: {s.get('story_content', '')[:100]}...")
        else:
            print(f"Attraction not found: {args.id}")

    else:
        parser.print_help()


if __name__ == '__main__':
    main()