#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
api_test.py - API Endpoint Test Script for ChinaTour Backend

Tests all API endpoints and generates a test report.

Usage:
    python api_test.py [--api-url URL] [--output reports/api-test-report.md]
"""

import sys
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import json
import os
import time
import urllib.request
import urllib.error
import urllib.parse
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

# ============== Configuration ==============

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(PROJECT_ROOT, 'reports')

DEFAULT_API_URL = os.environ.get('CHINATOUR_API_URL', 'http://1.13.252.172:3000')
DEFAULT_TIMEOUT = 30

# ============== Data Classes ==============

@dataclass
class TestResult:
    """Single test result"""
    endpoint: str
    method: str
    description: str
    passed: bool
    status_code: int
    response_time_ms: int
    error: Optional[str] = None
    details: Optional[Dict] = None


@dataclass
class APITestReport:
    """API test report"""
    timestamp: str
    api_url: str
    total_tests: int
    passed: int
    failed: int
    pass_rate: str
    results: List[Dict]
    issues: List[str]


# ============== Test Cases ==============

TEST_CASES = [
    {
        "endpoint": "/api/v1/guide/health",
        "method": "GET",
        "description": "Health check endpoint",
        "expected_status": 200,
        "validate": lambda r: r.get('success') and 'data' in r
    },
    {
        "endpoint": "/api/v1/guide/attractions",
        "method": "GET",
        "description": "List attractions",
        "expected_status": 200,
        "validate": lambda r: r.get('success') and isinstance(r.get('data'), list)
    },
    {
        "endpoint": "/api/v1/guide/attractions?limit=5",
        "method": "GET",
        "description": "List attractions with limit",
        "expected_status": 200,
        "validate": lambda r: r.get('success') and len(r.get('data', [])) <= 5
    },
    {
        "endpoint": "/api/v1/guide/attractions?search=故宫",
        "method": "GET",
        "description": "Search attractions",
        "expected_status": 200,
        "validate": lambda r: r.get('success')
    },
    {
        "endpoint": "/api/v1/guide/ask",
        "method": "POST",
        "description": "Ask question (basic)",
        "data": {"question": "故宫开放时间"},
        "expected_status": 200,
        "validate": lambda r: r.get('success') and 'answer' in r.get('data', {})
    },
    {
        "endpoint": "/api/v1/guide/ask",
        "method": "POST",
        "description": "Ask question (English)",
        "data": {"question": "Forbidden City opening hours", "language": "en"},
        "expected_status": 200,
        "validate": lambda r: r.get('success') and 'answer' in r.get('data', {})
    },
    {
        "endpoint": "/api/v1/guide/scenic/1",
        "method": "GET",
        "description": "Get scenic info (if exists)",
        "expected_status": [200, 404],  # 404 is acceptable if ID doesn't exist
        "validate": lambda r: r.get('success') or r.get('error', {}).get('code') == 'NOT_FOUND'
    },
]


# ============== Tester Class ==============

class APITester:
    """API endpoint tester"""

    def __init__(self, api_url: str = DEFAULT_API_URL, timeout: int = DEFAULT_TIMEOUT):
        self.api_url = api_url.rstrip('/')
        self.timeout = timeout
        self.results: List[TestResult] = []

    def make_request(
        self,
        endpoint: str,
        method: str = 'GET',
        data: Optional[Dict] = None
    ) -> Tuple[int, Dict, int]:
        """Make HTTP request and return (status_code, response, time_ms)"""
        # Handle non-ASCII characters in URL
        parsed = urllib.parse.urlparse(endpoint)
        encoded_path = urllib.parse.quote(parsed.path, safe='/', encoding='utf-8')
        encoded_query = urllib.parse.quote(parsed.query, safe='=&?', encoding='utf-8') if parsed.query else ''
        encoded_endpoint = f"{encoded_path}?{encoded_query}" if encoded_query else encoded_path
        url = f"{self.api_url}{encoded_endpoint}"
        headers = {'Content-Type': 'application/json'}

        start_time = time.time()

        try:
            if data:
                body = json.dumps(data, ensure_ascii=False).encode('utf-8')
                request = urllib.request.Request(
                    url, data=body, headers=headers, method=method
                )
            else:
                request = urllib.request.Request(url, headers=headers, method=method)

            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                response_body = response.read().decode('utf-8')
                status_code = response.status
                result = json.loads(response_body)

        except urllib.error.HTTPError as e:
            status_code = e.code
            try:
                result = json.loads(e.read().decode('utf-8'))
            except:
                result = {'error': str(e)}

        except urllib.error.URLError as e:
            status_code = 0
            result = {'error': f'Connection failed: {e.reason}'}

        except TimeoutError:
            status_code = 0
            result = {'error': 'Request timed out'}

        except Exception as e:
            status_code = 0
            result = {'error': str(e)}

        time_ms = int((time.time() - start_time) * 1000)
        return status_code, result, time_ms

    def run_test(self, test_case: Dict) -> TestResult:
        """Run a single test case"""
        endpoint = test_case['endpoint']
        method = test_case['method']
        description = test_case['description']
        expected_status = test_case['expected_status']
        validate_fn = test_case.get('validate')
        data = test_case.get('data')

        status_code, response, time_ms = self.make_request(endpoint, method, data)

        # Check if status code matches expected
        if isinstance(expected_status, list):
            status_ok = status_code in expected_status
        else:
            status_ok = status_code == expected_status

        # Run validation if provided
        validation_ok = True
        if validate_fn and status_ok:
            try:
                validation_ok = validate_fn(response)
            except Exception as e:
                validation_ok = False

        passed = status_ok and validation_ok

        error = None
        if not passed:
            if not status_ok:
                error = f"Expected status {expected_status}, got {status_code}"
            elif not validation_ok:
                error = "Response validation failed"
            err_data = response.get('error')
            if err_data:
                if isinstance(err_data, dict):
                    error = err_data.get('message', str(err_data))
                else:
                    error = str(err_data)

        return TestResult(
            endpoint=endpoint,
            method=method,
            description=description,
            passed=passed,
            status_code=status_code,
            response_time_ms=time_ms,
            error=error,
            details=response if not passed else None
        )

    def run_all_tests(self) -> List[TestResult]:
        """Run all test cases"""
        results = []

        print(f"\n{'='*60}")
        print(f"Running {len(TEST_CASES)} API tests...")
        print(f"API URL: {self.api_url}")
        print(f"{'='*60}\n")

        for i, test_case in enumerate(TEST_CASES, 1):
            print(f"[{i}/{len(TEST_CASES)}] {test_case['method']} {test_case['endpoint']}")
            print(f"         {test_case['description']}")

            result = self.run_test(test_case)
            results.append(result)

            status = "PASS" if result.passed else "FAIL"
            icon = "OK" if result.passed else "ERROR"
            print(f"         [{icon}] {status} (status: {result.status_code}, time: {result.response_time_ms}ms)")

            if result.error:
                print(f"         Error: {result.error}")

        self.results = results
        return results

    def generate_report(self) -> APITestReport:
        """Generate test report"""
        passed = [r for r in self.results if r.passed]
        failed = [r for r in self.results if not r.passed]

        pass_rate = f"{len(passed)}/{len(self.results)} ({100*len(passed)/len(self.results):.0f}%)" if self.results else "N/A"

        issues = []
        for r in failed:
            issues.append(f"{r.method} {r.endpoint}: {r.error or 'Failed'}")

        return APITestReport(
            timestamp=datetime.now().isoformat(),
            api_url=self.api_url,
            total_tests=len(self.results),
            passed=len(passed),
            failed=len(failed),
            pass_rate=pass_rate,
            results=[asdict(r) for r in self.results],
            issues=issues
        )

    def save_report(self, report: APITestReport, output_path: str) -> None:
        """Save report to Markdown file"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        md_content = f"""# API 端点测试报告

> 生成时间: {report.timestamp}
> API URL: {report.api_url}

## 概览

| 指标 | 值 |
|------|-----|
| 总测试数 | {report.total_tests} |
| 通过 | {report.passed} |
| 失败 | {report.failed} |
| 通过率 | {report.pass_rate} |

## 测试结果

| 端点 | 方法 | 描述 | 状态码 | 耗时 | 结果 |
|------|------|------|--------|------|------|
"""

        for r in report.results:
            status = "OK" if r['passed'] else "FAIL"
            md_content += f"| {r['endpoint']} | {r['method']} | {r['description']} | {r['status_code']} | {r['response_time_ms']}ms | {status} |\n"

        if report.issues:
            md_content += "\n## 问题列表\n\n"
            for issue in report.issues:
                md_content += f"- {issue}\n"

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md_content)

        print(f"\n报告已保存到: {output_path}")


# ============== CLI ==============

def main():
    import argparse

    parser = argparse.ArgumentParser(description='API 端点测试')
    parser.add_argument('--api-url', default=DEFAULT_API_URL, help='API URL')
    parser.add_argument('--output', default=os.path.join(REPORTS_DIR, 'api-test-report.md'), help='Output report path')
    parser.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT, help='Request timeout in seconds')

    args = parser.parse_args()

    tester = APITester(api_url=args.api_url, timeout=args.timeout)
    tester.run_all_tests()
    report = tester.generate_report()
    tester.save_report(report, args.output)

    # Print summary
    print(f"\n{'='*60}")
    print("API 端点测试完成")
    print(f"{'='*60}")
    print(f"通过: {report.passed}/{report.total_tests}")
    print(f"通过率: {report.pass_rate}")

    if report.issues:
        print(f"\n发现 {len(report.issues)} 个问题")


if __name__ == '__main__':
    main()