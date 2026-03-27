#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rag_status_checker.py - RAG 入库状态检查脚本

检查景区数据是否已正确入库到向量数据库

Usage:
    python rag_status_checker.py [--api-url URL] [--output reports/rag-status-report.md]
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from api_client import ChinaTourClient, DEFAULT_API_URL
except ImportError:
    DEFAULT_API_URL = os.environ.get('CHINATOUR_API_URL', 'http://1.13.252.172:3000')


# ============== Configuration ==============

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFERENCES_DIR = os.path.join(PROJECT_ROOT, 'references')
REPORTS_DIR = os.path.join(PROJECT_ROOT, 'reports')

# Test queries for RAG verification
TEST_QUERIES = [
    # 基础信息查询
    {"query": "故宫开放时间", "expected": "forbidden-city", "category": "basic"},
    {"query": "长城门票价格", "expected": "great-wall", "category": "basic"},
    {"query": "西湖怎么逛", "expected": "west-lake", "category": "basic"},
    {"query": "兵马俑在哪里", "expected": "terracotta-army", "category": "basic"},
    
    # 拍照相关
    {"query": "故宫最佳拍照点", "expected": "forbidden-city", "category": "photo"},
    {"query": "兵马俑摄影攻略", "expected": "terracotta-army", "category": "photo"},
    {"query": "长城拍照机位", "expected": "great-wall", "category": "photo"},
    
    # 文化故事
    {"query": "太和殿的历史", "expected": "forbidden-city", "category": "culture"},
    {"query": "布达拉宫的故事", "expected": "potala-palace", "category": "culture"},
    {"query": "兵马俑的发现过程", "expected": "terracotta-army", "category": "culture"},
    
    # 英文查询
    {"query": "Forbidden City opening hours", "expected": "forbidden-city", "category": "english"},
    {"query": "West Lake photo spots", "expected": "west-lake", "category": "english"},
    {"query": "Great Wall ticket price", "expected": "great-wall", "category": "english"},
]


# ============== Data Classes ==============

@dataclass
class TestResult:
    """Single test result"""
    query: str
    passed: bool
    expected: str
    actual: Optional[str]
    score: float
    category: str
    response_time_ms: int
    error: Optional[str] = None


@dataclass
class AttractionStatus:
    """Attraction indexing status"""
    id: str
    name: str
    province: str
    has_basic_info: bool
    has_photo_spots: bool
    has_stories_zh: bool
    has_stories_en: bool
    indexed: bool


@dataclass
class RAGStatusReport:
    """RAG status report"""
    timestamp: str
    api_status: str
    total_attractions: int
    indexed_attractions: int
    total_vectors: int
    index_rate: str
    test_results: List[Dict]
    pass_rate: str
    issues: List[str]
    recommendations: List[str]


# ============== Checker Class ==============

class RAGStatusChecker:
    """
    RAG 状态检查器
    
    检查景区数据是否已正确入库到向量数据库
    """
    
    def __init__(self, api_url: str = DEFAULT_API_URL, timeout: int = 30):
        self.api_url = api_url.rstrip('/')
        self.timeout = timeout
        self.results: List[TestResult] = []
        self.attractions: List[AttractionStatus] = []
    
    def check_api_health(self) -> Tuple[bool, str]:
        """Check API health status"""
        try:
            url = f"{self.api_url}/api/v1/guide/health"
            request = urllib.request.Request(url)
            
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode('utf-8'))
                
            if data.get('success') and data.get('data', {}).get('status') == 'healthy':
                return True, "healthy"
            else:
                return False, data.get('data', {}).get('status', 'unknown')
                
        except Exception as e:
            return False, f"error: {str(e)}"
    
    def get_local_attractions(self) -> List[AttractionStatus]:
        """Get list of attractions from local data files"""
        attractions = []
        
        # Scan attractions directory
        attractions_dir = os.path.join(REFERENCES_DIR, 'attractions')
        if not os.path.exists(attractions_dir):
            return attractions
        
        for province in os.listdir(attractions_dir):
            province_dir = os.path.join(attractions_dir, province)
            if not os.path.isdir(province_dir):
                continue
            
            for file in os.listdir(province_dir):
                if not file.endswith('.md'):
                    continue
                
                attraction_id = file[:-3]  # Remove .md
                name = attraction_id.replace('-', ' ').title()
                
                # Check for related files
                photo_spots_dir = os.path.join(REFERENCES_DIR, 'photo-spots', province)
                culture_dir = os.path.join(REFERENCES_DIR, 'culture-stories', province)
                
                has_photo_spots = os.path.exists(os.path.join(photo_spots_dir, f"{attraction_id}-spots.md"))
                has_stories_zh = os.path.exists(os.path.join(culture_dir, f"{attraction_id}-stories.md"))
                has_stories_en = os.path.exists(os.path.join(culture_dir, f"{attraction_id}-stories-en.md"))
                
                attractions.append(AttractionStatus(
                    id=attraction_id,
                    name=name,
                    province=province,
                    has_basic_info=True,
                    has_photo_spots=has_photo_spots,
                    has_stories_zh=has_stories_zh,
                    has_stories_en=has_stories_en,
                    indexed=False  # Will be updated from API
                ))
        
        return attractions
    
    def test_query(self, query: str, expected: str, category: str) -> TestResult:
        """Test a single query against the API"""
        start_time = time.time()
        
        try:
            url = f"{self.api_url}/api/v1/guide/ask"
            data = json.dumps({'question': query}, ensure_ascii=False).encode('utf-8')
            request = urllib.request.Request(
                url,
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode('utf-8'))
            
            response_time_ms = int((time.time() - start_time) * 1000)
            
            if not result.get('success'):
                return TestResult(
                    query=query,
                    passed=False,
                    expected=expected,
                    actual=None,
                    score=0,
                    category=category,
                    response_time_ms=response_time_ms,
                    error=result.get('error', {}).get('message', 'Unknown error')
                )
            
            # Check if expected attraction appears in response
            answer = result.get('data', {}).get('answer', '').lower()
            sources = result.get('data', {}).get('sources', [])
            
            # Check sources for expected attraction
            actual = None
            score = 0
            
            if sources:
                for source in sources:
                    source_id = source.get('attraction_id', '') or source.get('id', '')
                    if source_id:
                        actual = source_id
                        break
            
            # If no source, check if expected keyword appears in answer
            if not actual:
                expected_keywords = expected.replace('-', ' ').split()
                if any(kw in answer for kw in expected_keywords):
                    actual = expected
                    score = 0.7
                else:
                    score = 0.3
            else:
                score = 1.0 if actual == expected else 0.5
            
            passed = actual == expected or score >= 0.7
            
            return TestResult(
                query=query,
                passed=passed,
                expected=expected,
                actual=actual,
                score=score,
                category=category,
                response_time_ms=response_time_ms
            )
            
        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            return TestResult(
                query=query,
                passed=False,
                expected=expected,
                actual=None,
                score=0,
                category=category,
                response_time_ms=response_time_ms,
                error=str(e)
            )
    
    def run_all_tests(self) -> List[TestResult]:
        """Run all test queries"""
        results = []
        
        print(f"\n{'='*60}")
        print(f"Running {len(TEST_QUERIES)} test queries...")
        print(f"{'='*60}\n")
        
        for i, test in enumerate(TEST_QUERIES, 1):
            print(f"[{i}/{len(TEST_QUERIES)}] Testing: {test['query'][:30]}...")
            
            result = self.test_query(
                query=test['query'],
                expected=test['expected'],
                category=test['category']
            )
            results.append(result)
            
            status = "✓ PASS" if result.passed else "✗ FAIL"
            print(f"         {status} (score: {result.score:.2f}, time: {result.response_time_ms}ms)")
            
            if result.error:
                print(f"         Error: {result.error}")
        
        self.results = results
        return results
    
    def check_indexed_attractions(self) -> Tuple[int, int]:
        """Check how many attractions are indexed in the API"""
        try:
            url = f"{self.api_url}/api/v1/guide/attractions?limit=100"
            request = urllib.request.Request(url)
            
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode('utf-8'))
            
            if data.get('success'):
                attractions = data.get('data', [])
                indexed_ids = [a.get('id') or a.get('attraction_id') for a in attractions]
                
                # Update local attractions status
                for attr in self.attractions:
                    if attr.id in indexed_ids:
                        attr.indexed = True
                
                return len(attractions), len(indexed_ids)
            else:
                return 0, 0
                
        except Exception as e:
            print(f"Error checking indexed attractions: {e}")
            return 0, 0
    
    def generate_report(self) -> RAGStatusReport:
        """Generate comprehensive RAG status report"""
        
        # Get local attractions
        self.attractions = self.get_local_attractions()
        
        # Check API health
        api_healthy, api_status = self.check_api_health()
        
        # Run tests if API is healthy
        if api_healthy:
            self.run_all_tests()
            indexed_count, total_vectors = self.check_indexed_attractions()
        else:
            self.results = []
            indexed_count = 0
            total_vectors = 0
        
        # Calculate pass rate
        passed_tests = [r for r in self.results if r.passed]
        pass_rate = f"{len(passed_tests)}/{len(self.results)} ({100*len(passed_tests)/len(self.results):.0f}%)" if self.results else "N/A"
        
        # Identify issues
        issues = []
        
        if not api_healthy:
            issues.append(f"API 不可用: {api_status}")
        
        failed_tests = [r for r in self.results if not r.passed]
        if failed_tests:
            issues.append(f"{len(failed_tests)} 个测试查询失败")
        
        missing_files = []
        for attr in self.attractions:
            if not attr.has_photo_spots:
                missing_files.append(f"{attr.id}: 缺少拍照机位数据")
            if not attr.has_stories_zh:
                missing_files.append(f"{attr.id}: 缺少中文文化故事")
            if not attr.has_stories_en:
                missing_files.append(f"{attr.id}: 缺少英文文化故事")
        
        if missing_files:
            issues.append(f"{len(missing_files)} 个数据文件缺失")
        
        # Generate recommendations
        recommendations = []
        
        if not api_healthy:
            recommendations.append("检查 API 服务器状态，确保后端服务正常运行")
            recommendations.append("验证网络连接和防火墙配置")
        
        if failed_tests:
            recommendations.append("分析失败查询，优化 RAG 检索质量")
        
        if missing_files:
            recommendations.append("补充缺失的数据文件")
        
        if indexed_count < len(self.attractions):
            recommendations.append(f"将剩余 {len(self.attractions) - indexed_count} 个景区数据入库")
        
        return RAGStatusReport(
            timestamp=datetime.now().isoformat(),
            api_status=api_status,
            total_attractions=len(self.attractions),
            indexed_attractions=indexed_count,
            total_vectors=total_vectors,
            index_rate=f"{indexed_count}/{len(self.attractions)} ({100*indexed_count/len(self.attractions):.0f}%)" if self.attractions else "N/A",
            test_results=[asdict(r) for r in self.results],
            pass_rate=pass_rate,
            issues=issues,
            recommendations=recommendations
        )
    
    def save_report(self, report: RAGStatusReport, output_path: str) -> None:
        """Save report to Markdown file"""
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        md_content = f"""# RAG 入库状态报告

> 生成时间: {report.timestamp}

## 概览

| 指标 | 值 |
|------|-----|
| API 状态 | {report.api_status} |
| 本地景区总数 | {report.total_attractions} |
| 已入库景区 | {report.indexed_attractions} |
| 总向量数 | {report.total_vectors} |
| 入库率 | {report.index_rate} |
| 测试通过率 | {report.pass_rate} |

## 测试结果详情

### 按类别统计

"""
        
        # Category statistics
        categories = {}
        for result in report.test_results:
            cat = result['category']
            if cat not in categories:
                categories[cat] = {'passed': 0, 'total': 0}
            categories[cat]['total'] += 1
            if result['passed']:
                categories[cat]['passed'] += 1
        
        md_content += "| 类别 | 通过/总数 | 通过率 |\n|------|-----------|--------|\n"
        for cat, stats in categories.items():
            rate = f"{100*stats['passed']/stats['total']:.0f}%" if stats['total'] > 0 else "N/A"
            md_content += f"| {cat} | {stats['passed']}/{stats['total']} | {rate} |\n"
        
        md_content += "\n### 详细结果\n\n"
        md_content += "| 查询 | 预期 | 实际 | 分数 | 耗时 | 状态 |\n"
        md_content += "|------|------|------|------|------|------|\n"
        
        for result in report.test_results:
            status = "✓" if result['passed'] else "✗"
            actual = result['actual'] or "N/A"
            md_content += f"| {result['query'][:30]} | {result['expected']} | {actual} | {result['score']:.2f} | {result['response_time_ms']}ms | {status} |\n"
        
        # Issues
        if report.issues:
            md_content += "\n## 问题列表\n\n"
            for issue in report.issues:
                md_content += f"- {issue}\n"
        
        # Recommendations
        if report.recommendations:
            md_content += "\n## 建议\n\n"
            for rec in report.recommendations:
                md_content += f"- {rec}\n"
        
        # Attraction status
        md_content += "\n## 景区入库状态\n\n"
        md_content += "| ID | 名称 | 省份 | 基础信息 | 拍照机位 | 中文故事 | 英文故事 | 入库状态 |\n"
        md_content += "|----|------|------|----------|----------|----------|----------|----------|\n"
        
        for attr in self.attractions:
            basic = "✓" if attr.has_basic_info else "✗"
            photo = "✓" if attr.has_photo_spots else "✗"
            story_zh = "✓" if attr.has_stories_zh else "✗"
            story_en = "✓" if attr.has_stories_en else "✗"
            indexed = "✓" if attr.indexed else "✗"
            md_content += f"| {attr.id} | {attr.name} | {attr.province} | {basic} | {photo} | {story_zh} | {story_en} | {indexed} |\n"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        print(f"\n报告已保存到: {output_path}")


# ============== CLI ==============

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='RAG 入库状态检查')
    parser.add_argument('--api-url', default=DEFAULT_API_URL, help='API URL')
    parser.add_argument('--output', default=os.path.join(REPORTS_DIR, 'rag-status-report.md'), help='Output report path')
    parser.add_argument('--timeout', type=int, default=30, help='Request timeout in seconds')
    
    args = parser.parse_args()
    
    checker = RAGStatusChecker(api_url=args.api_url, timeout=args.timeout)
    report = checker.generate_report()
    checker.save_report(report, args.output)
    
    # Print summary
    print(f"\n{'='*60}")
    print("RAG 入库状态检查完成")
    print(f"{'='*60}")
    print(f"API 状态: {report.api_status}")
    print(f"景区总数: {report.total_attractions}")
    print(f"已入库: {report.indexed_attractions}")
    print(f"测试通过率: {report.pass_rate}")
    
    if report.issues:
        print(f"\n发现 {len(report.issues)} 个问题:")
        for issue in report.issues:
            print(f"  - {issue}")


if __name__ == '__main__':
    main()