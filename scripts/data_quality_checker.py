#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""data_quality_checker.py - Data Quality Checker for ChinaTour"""
import sys
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import json
import os
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFERENCES_DIR = os.path.join(PROJECT_ROOT, 'references')
REPORTS_DIR = os.path.join(PROJECT_ROOT, 'reports')

SAMPLE_ATTRACTIONS = [
    {"id": "forbidden-city", "name": "Forbidden City", "province": "beijing"},
    {"id": "terracotta-army", "name": "Terracotta Army", "province": "shaanxi"},
    {"id": "west-lake", "name": "West Lake", "province": "zhejiang"},
    {"id": "yellow-mountain", "name": "Yellow Mountain", "province": "anhui"},  # 文件名是 yellow-mountain
    {"id": "jiuzhaigou", "name": "Jiuzhaigou", "province": "sichuan"},
]

QUALITY_RULES = {
    "basic_info": {
        "required_fields": ["open", "ticket", "duration"],
        "recommended_fields": ["address", "transport", "season"],
        "min_word_count": 100,
    },
    "photo_spots": {
        "min_spots": 5,
        "required_fields": ["spot", "location", "time"],
        "recommended_fields": ["camera", "tips", "notes"],
    },
    "culture_stories": {
        "levels": ["L1", "L2", "L3"],
        "word_counts": {"L1": (50, 100), "L2": (300, 500), "L3": (800, 1500)},
        "required_elements": ["title", "content"],
    }
}

@dataclass
class QualityIssue:
    category: str
    field: str
    severity: str
    message: str

@dataclass
class AttractionQualityReport:
    attraction_id: str
    name: str
    province: str
    basic_info_score: int
    photo_spots_score: int
    stories_zh_score: int
    stories_en_score: int
    overall_score: int
    issues: List[Dict]
    recommendations: List[str]

@dataclass
class DataQualityReport:
    timestamp: str
    sampled_attractions: int
    attraction_reports: List[Dict]
    average_score: float
    summary: Dict
    recommendations: List[str]

class DataQualityChecker:
    def __init__(self):
        self.issues: List[QualityIssue] = []
    
    def read_file(self, file_path: str) -> Optional[str]:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return None
        except Exception as e:
            self.issues.append(QualityIssue("file", file_path, "error", f"Read failed: {str(e)}"))
            return None
    
    def check_basic_info(self, content: str, attraction_name: str) -> Tuple[int, List[Dict]]:
        issues = []
        score = 100
        
        if not content:
            return 0, [{"category": "basic_info", "severity": "error", "message": "File not found or empty"}]
        
        rules = QUALITY_RULES["basic_info"]
        
        # Check content indicators
        has_opening = any(kw in content.lower() for kw in ["open", "hour", "time", "open"])
        has_ticket = any(kw in content.lower() for kw in ["ticket", "price", "fee", "admission"])
        has_duration = any(kw in content.lower() for kw in ["hour", "duration", "time", "visit"])
        
        if not has_opening:
            issues.append({"category": "basic_info", "field": "opening", "severity": "warning", "message": "Missing opening hours"})
            score -= 15
        if not has_ticket:
            issues.append({"category": "basic_info", "field": "ticket", "severity": "warning", "message": "Missing ticket info"})
            score -= 15
        if not has_duration:
            issues.append({"category": "basic_info", "field": "duration", "severity": "warning", "message": "Missing visit duration"})
            score -= 10
        
        # Check word count
        word_count = len(content)
        if word_count < rules["min_word_count"]:
            issues.append({"category": "basic_info", "field": "word_count", "severity": "warning", "message": f"Word count: {word_count} < {rules['min_word_count']}"})
            score -= 10
        
        # Check structure
        if "## " not in content:
            issues.append({"category": "basic_info", "severity": "warning", "message": "Missing section headers"})
            score -= 5
        
        return max(0, score), issues
    
    def check_photo_spots(self, content: str, attraction_name: str) -> Tuple[int, List[Dict]]:
        issues = []
        score = 100
        
        if not content:
            return 0, [{"category": "photo_spots", "severity": "error", "message": "File not found or empty"}]
        
        rules = QUALITY_RULES["photo_spots"]
        
        # Count photo spots by headers
        spot_pattern = r'###?\s*(Spot|[\u4e00-\u9fa5]+\d+|\d+\.)'
        spots = re.findall(spot_pattern, content, re.IGNORECASE)
        spot_count = len(spots)
        
        # Estimate from content size
        if spot_count == 0:
            spot_count = max(1, content.count("## ") - 1)
        
        if spot_count < rules["min_spots"]:
            issues.append({"category": "photo_spots", "field": "spot_count", "severity": "warning", "message": f"Photo spots: {spot_count} < {rules['min_spots']}"})
            score -= (rules["min_spots"] - spot_count) * 8
        
        # Check for key elements
        has_location = "location" in content.lower() or "position" in content.lower() or "where" in content.lower()
        has_time = "time" in content.lower() or "hour" in content.lower() or "light" in content.lower()
        
        if not has_location:
            issues.append({"category": "photo_spots", "field": "location", "severity": "info", "message": "Missing location details"})
            score -= 5
        if not has_time:
            issues.append({"category": "photo_spots", "field": "time", "severity": "info", "message": "Missing best time info"})
            score -= 5
        
        return max(0, score), issues
    
    def check_culture_story(self, content: str, attraction_name: str, lang: str = "zh") -> Tuple[int, List[Dict]]:
        issues = []
        score = 100
        
        if not content:
            return 0, [{"category": f"stories_{lang}", "severity": "error", "message": "File not found or empty"}]
        
        rules = QUALITY_RULES["culture_stories"]
        
        # Check for depth levels
        for level in rules["levels"]:
            level_pattern = rf'##\s*{level}[:：\s]'
            if not re.search(level_pattern, content, re.IGNORECASE):
                issues.append({"category": f"stories_{lang}", "field": level, "severity": "warning", "message": f"Missing {level} version"})
                score -= 15
            else:
                # Check word count
                level_match = re.search(rf'##\s*{level}[:：\s](.*?)(?=##\s*[L\d]|$)', content, re.DOTALL | re.IGNORECASE)
                if level_match:
                    level_content = level_match.group(1)
                    word_count = len(level_content.strip())
                    min_words, max_words = rules["word_counts"][level]
                    
                    if word_count < min_words:
                        issues.append({"category": f"stories_{lang}", "field": f"{level}_words", "severity": "warning", "message": f"{level} words: {word_count} < {min_words}"})
                        score -= 5
        
        return max(0, score), issues
    
    def check_attraction(self, attraction: Dict) -> AttractionQualityReport:
        attraction_id = attraction["id"]
        name = attraction["name"]
        province = attraction["province"]
        
        basic_path = os.path.join(REFERENCES_DIR, "attractions", province, f"{attraction_id}.md")
        photo_path = os.path.join(REFERENCES_DIR, "photo-spots", province, f"{attraction_id}-spots.md")
        story_zh_path = os.path.join(REFERENCES_DIR, "culture-stories", province, f"{attraction_id}-stories.md")
        story_en_path = os.path.join(REFERENCES_DIR, "culture-stories", province, f"{attraction_id}-stories-en.md")
        
        basic_content = self.read_file(basic_path)
        photo_content = self.read_file(photo_path)
        story_zh_content = self.read_file(story_zh_path)
        story_en_content = self.read_file(story_en_path)
        
        basic_score, basic_issues = self.check_basic_info(basic_content, name)
        photo_score, photo_issues = self.check_photo_spots(photo_content, name)
        story_zh_score, story_zh_issues = self.check_culture_story(story_zh_content, name, "zh")
        story_en_score, story_en_issues = self.check_culture_story(story_en_content, name, "en")
        
        all_issues = basic_issues + photo_issues + story_zh_issues + story_en_issues
        
        overall_score = int(basic_score * 0.3 + photo_score * 0.25 + story_zh_score * 0.25 + story_en_score * 0.2)
        
        recommendations = []
        if basic_score < 70:
            recommendations.append("Improve basic info with required fields")
        if photo_score < 70:
            recommendations.append("Add more photo spots with details")
        if story_zh_score < 70:
            recommendations.append("Complete Chinese stories with L1/L2/L3 versions")
        if story_en_score < 70:
            recommendations.append("Complete English stories matching Chinese content")
        
        return AttractionQualityReport(
            attraction_id=attraction_id,
            name=name,
            province=province,
            basic_info_score=basic_score,
            photo_spots_score=photo_score,
            stories_zh_score=story_zh_score,
            stories_en_score=story_en_score,
            overall_score=overall_score,
            issues=all_issues,
            recommendations=recommendations
        )
    
    def check_all_attractions(self) -> DataQualityReport:
        attraction_reports = []
        total_score = 0
        
        print(f"\n{'='*60}")
        print(f"Checking quality for {len(SAMPLE_ATTRACTIONS)} attractions...")
        print(f"{'='*60}\n")
        
        for i, attraction in enumerate(SAMPLE_ATTRACTIONS, 1):
            print(f"[{i}/{len(SAMPLE_ATTRACTIONS)}] Checking {attraction['name']} ({attraction['id']})...")
            
            report = self.check_attraction(attraction)
            attraction_reports.append({
                "attraction_id": report.attraction_id,
                "name": report.name,
                "province": report.province,
                "basic_info_score": report.basic_info_score,
                "photo_spots_score": report.photo_spots_score,
                "stories_zh_score": report.stories_zh_score,
                "stories_en_score": report.stories_en_score,
                "overall_score": report.overall_score,
                "issues": report.issues,
                "recommendations": report.recommendations
            })
            
            total_score += report.overall_score
            
            status = "[OK]" if report.overall_score >= 85 else "[WARN]" if report.overall_score >= 70 else "[FAIL]"
            print(f"         {status} Score: {report.overall_score}")
            
            if report.issues:
                error_count = len([i for i in report.issues if i["severity"] == "error"])
                warning_count = len([i for i in report.issues if i["severity"] == "warning"])
                print(f"         Issues: {error_count} errors, {warning_count} warnings")
        
        avg_score = total_score / len(SAMPLE_ATTRACTIONS) if SAMPLE_ATTRACTIONS else 0
        
        summary = {
            "avg_basic_score": sum(r["basic_info_score"] for r in attraction_reports) / len(attraction_reports),
            "avg_photo_score": sum(r["photo_spots_score"] for r in attraction_reports) / len(attraction_reports),
            "avg_stories_zh_score": sum(r["stories_zh_score"] for r in attraction_reports) / len(attraction_reports),
            "avg_stories_en_score": sum(r["stories_en_score"] for r in attraction_reports) / len(attraction_reports),
            "excellent_count": len([r for r in attraction_reports if r["overall_score"] >= 90]),
            "good_count": len([r for r in attraction_reports if 70 <= r["overall_score"] < 90]),
            "poor_count": len([r for r in attraction_reports if r["overall_score"] < 70]),
        }
        
        recommendations = []
        if summary["avg_basic_score"] < 80:
            recommendations.append("Overall basic info needs improvement")
        if summary["avg_photo_score"] < 80:
            recommendations.append("Photo spots quality needs improvement")
        if summary["avg_stories_zh_score"] < 80:
            recommendations.append("Chinese stories need L1/L2/L3 versions")
        if summary["avg_stories_en_score"] < 80:
            recommendations.append("English stories need to match Chinese content")
        if summary["poor_count"] > 0:
            recommendations.append(f"{summary['poor_count']} attractions have poor quality")
        
        return DataQualityReport(
            timestamp=datetime.now().isoformat(),
            sampled_attractions=len(SAMPLE_ATTRACTIONS),
            attraction_reports=attraction_reports,
            average_score=round(avg_score, 1),
            summary=summary,
            recommendations=recommendations
        )
    
    def save_report(self, report: DataQualityReport, output_path: str) -> None:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        md_content = f"""# Data Quality Report

> Generated: {report.timestamp}

## Overview

| Metric | Value |
|--------|-------|
| Sampled Attractions | {report.sampled_attractions} |
| Average Score | {report.average_score} |
| Excellent (>=90) | {report.summary['excellent_count']} |
| Good (70-89) | {report.summary['good_count']} |
| Poor (<70) | {report.summary['poor_count']} |

## Category Average Scores

| Data Type | Average Score |
|-----------|---------------|
| Basic Info | {report.summary['avg_basic_score']:.1f} |
| Photo Spots | {report.summary['avg_photo_score']:.1f} |
| Chinese Stories | {report.summary['avg_stories_zh_score']:.1f} |
| English Stories | {report.summary['avg_stories_en_score']:.1f} |

## Attraction Details

"""
        
        for r in report.attraction_reports:
            status = "[OK]" if r["overall_score"] >= 85 else "[WARN]" if r["overall_score"] >= 70 else "[FAIL]"
            md_content += f"""### {r['name']} ({r['attraction_id']}) {status}

| Data Type | Score | Status |
|-----------|-------|--------|
| Basic Info | {r['basic_info_score']} | {'OK' if r['basic_info_score'] >= 85 else 'WARN' if r['basic_info_score'] >= 70 else 'FAIL'} |
| Photo Spots | {r['photo_spots_score']} | {'OK' if r['photo_spots_score'] >= 85 else 'WARN' if r['photo_spots_score'] >= 70 else 'FAIL'} |
| Chinese Stories | {r['stories_zh_score']} | {'OK' if r['stories_zh_score'] >= 85 else 'WARN' if r['stories_zh_score'] >= 70 else 'FAIL'} |
| English Stories | {r['stories_en_score']} | {'OK' if r['stories_en_score'] >= 85 else 'WARN' if r['stories_en_score'] >= 70 else 'FAIL'} |
| **Total** | **{r['overall_score']}** | {status} |

"""
            
            if r['issues']:
                md_content += "**Issues:**\n\n"
                for issue in r['issues']:
                    icon = "[ERROR]" if issue["severity"] == "error" else "[WARN]" if issue["severity"] == "warning" else "[INFO]"
                    md_content += f"- {icon} [{issue['category']}] {issue['message']}\n"
                md_content += "\n"
            
            if r['recommendations']:
                md_content += "**Recommendations:**\n\n"
                for rec in r['recommendations']:
                    md_content += f"- {rec}\n"
                md_content += "\n"
        
        if report.recommendations:
            md_content += "## Overall Recommendations\n\n"
            for rec in report.recommendations:
                md_content += f"- {rec}\n"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        print(f"\nReport saved to: {output_path}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Data Quality Checker')
    parser.add_argument('--output', default=os.path.join(REPORTS_DIR, 'data-quality-report.md'), help='Output report path')
    
    args = parser.parse_args()
    
    checker = DataQualityChecker()
    report = checker.check_all_attractions()
    checker.save_report(report, args.output)
    
    print(f"\n{'='*60}")
    print("Data Quality Check Complete")
    print(f"{'='*60}")
    print(f"Sampled: {report.sampled_attractions}")
    print(f"Average Score: {report.average_score}")
    print(f"Excellent: {report.summary['excellent_count']}, Good: {report.summary['good_count']}, Poor: {report.summary['poor_count']}")


if __name__ == '__main__':
    main()