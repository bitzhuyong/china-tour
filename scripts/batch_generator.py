#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
batch_generator.py - Batch Data Generator for ChinaTour Attractions

Generates attraction data files (basic info, photo spots, culture stories)
for new attractions.

Usage:
    python batch_generator.py --attraction-id forbidden-city
    python batch_generator.py --list data/new-attractions.json --dry-run
"""

import sys
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import json
import os
import re
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

# ============== Configuration ==============

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
REFERENCES_DIR = os.path.join(PROJECT_ROOT, 'references')

# Province name mapping (English -> Chinese + pinyin)
PROVINCE_MAP = {
    "北京": {"en": "beijing", "name": "北京"},
    "上海": {"en": "shanghai", "name": "上海"},
    "天津": {"en": "tianjin", "name": "天津"},
    "重庆": {"en": "chongqing", "name": "重庆"},
    "河北": {"en": "hebei", "name": "河北"},
    "山西": {"en": "shanxi", "name": "山西"},
    "辽宁": {"en": "liaoning", "name": "辽宁"},
    "吉林": {"en": "jilin", "name": "吉林"},
    "黑龙江": {"en": "heilongjiang", "name": "黑龙江"},
    "江苏": {"en": "jiangsu", "name": "江苏"},
    "浙江": {"en": "zhejiang", "name": "浙江"},
    "安徽": {"en": "anhui", "name": "安徽"},
    "福建": {"en": "fujian", "name": "福建"},
    "江西": {"en": "jiangxi", "name": "江西"},
    "山东": {"en": "shandong", "name": "山东"},
    "河南": {"en": "henan", "name": "河南"},
    "湖北": {"en": "hubei", "name": "湖北"},
    "湖南": {"en": "hunan", "name": "湖南"},
    "广东": {"en": "guangdong", "name": "广东"},
    "广西": {"en": "guangxi", "name": "广西"},
    "海南": {"en": "hainan", "name": "海南"},
    "四川": {"en": "sichuan", "name": "四川"},
    "贵州": {"en": "guizhou", "name": "贵州"},
    "云南": {"en": "yunnan", "name": "云南"},
    "西藏": {"en": "tibet", "name": "西藏"},
    "陕西": {"en": "shaanxi", "name": "陕西"},
    "甘肃": {"en": "gansu", "name": "甘肃"},
    "青海": {"en": "qinghai", "name": "青海"},
    "宁夏": {"en": "ningxia", "name": "宁夏"},
    "新疆": {"en": "xinjiang", "name": "新疆"},
    "内蒙古": {"en": "inner-mongolia", "name": "内蒙古"},
    "台湾": {"en": "taiwan", "name": "台湾"},
    "香港": {"en": "hongkong", "name": "香港"},
    "澳门": {"en": "macau", "name": "澳门"},
}

# Category templates
CATEGORY_TEMPLATES = {
    "历史文化": {
        "photo_keywords": ["建筑", "雕刻", "古迹", "文物", "庭院"],
        "story_themes": ["历史沿革", "文化内涵", "传说故事", "名人轶事"]
    },
    "自然风光": {
        "photo_keywords": ["山水", "日出", "日落", "云海", "季节"],
        "story_themes": ["地质形成", "自然生态", "民间传说", "文人题咏"]
    },
    "皇家园林": {
        "photo_keywords": ["亭台楼阁", "湖光山色", "古树名木", "石刻碑文"],
        "story_themes": ["皇家历史", "造园艺术", "轶闻趣事", "文化传承"]
    },
    "古典园林": {
        "photo_keywords": ["假山池沼", "花窗月洞", "曲径通幽", "四季景色"],
        "story_themes": ["园林艺术", "文人雅事", "历史变迁", "诗词歌赋"]
    },
    "海滨度假": {
        "photo_keywords": ["海滩", "日落", "水上活动", "椰林"],
        "story_themes": ["海洋文化", "当地民俗", "度假体验", "美食推荐"]
    },
    "主题乐园": {
        "photo_keywords": ["游乐设施", "主题区域", "表演秀", "夜景"],
        "story_themes": ["主题故事", "游玩攻略", "特色体验", "亲子推荐"]
    },
    "民族文化": {
        "photo_keywords": ["民族建筑", "服饰", "节庆活动", "手工艺"],
        "story_themes": ["民族历史", "传统文化", "节庆习俗", "民间艺术"]
    },
    "宗教文化": {
        "photo_keywords": ["寺庙建筑", "佛像", "石刻", "香火"],
        "story_themes": ["宗教历史", "建筑艺术", "传说故事", "朝圣指南"]
    },
    "文化艺术": {
        "photo_keywords": ["艺术装置", "展览", "建筑空间", "活动"],
        "story_themes": ["艺术历史", "代表作品", "文化影响", "参观指南"]
    }
}


# ============== Data Classes ==============

@dataclass
class AttractionInfo:
    """Attraction basic information"""
    id: str
    name: str
    name_en: str
    province: str
    city: str
    level: str
    category: str
    rating: float


# ============== Generator Class ==============

class AttractionDataGenerator:
    """
    景区数据生成器

    生成景区的基础信息、拍照机位、文化故事等数据文件
    """

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.generated_files: List[str] = []

    def get_province_dir(self, province: str) -> str:
        """Get province directory name"""
        if province in PROVINCE_MAP:
            return PROVINCE_MAP[province]["en"]
        # Fallback: convert to pinyin-like
        return province.lower().replace(" ", "-")

    def generate_basic_info(self, attraction: AttractionInfo) -> str:
        """Generate basic info Markdown template"""
        category_template = CATEGORY_TEMPLATES.get(attraction.category, CATEGORY_TEMPLATES["历史文化"])

        template = f'''# {attraction.name} ({attraction.name_en})

> **数据最后更新**: {datetime.now().strftime("%Y-%m")}
> **提示**: 节假日可能有特殊调整，建议出行前核实

## 基本信息

| 项目 | 详情 |
|------|------|
| 位置 | {attraction.province}{attraction.city} |
| 开放时间 | 待补充 |
| 建议游览时长 | 待补充 |
| 门票 | 待补充 |
| 最佳季节 | 待补充 |
| 预约 | 待补充 |
| 官网 | 待补充 |
| 咨询电话 | 待补充 |

---

## 主要景点列表

### 核心景点

| 序号 | 景点 | 建议停留 | 亮点 | 适合拍照 |
|------|------|----------|------|----------|
| 1 | 景点1 | 30分钟 | 亮点描述 | ⭐⭐⭐⭐ |
| 2 | 景点2 | 30分钟 | 亮点描述 | ⭐⭐⭐⭐ |
| 3 | 景点3 | 30分钟 | 亮点描述 | ⭐⭐⭐⭐ |

---

## 推荐路线

### 经典游览路线

```
入口 → 景点1 → 景点2 → 景点3 → 出口

特点：
• 游览时间：2-3小时
• 步行距离：约2km
• 难度：中等
• 适合：第一次游览
```

---

## 服务设施

### 休息区
- 主要景点附近

### 餐饮
- 景区内/外餐饮信息

### 交通
- 公共交通：待补充
- 自驾：待补充

---

## 拍照注意事项

✅ **允许拍照区域**：
- 全程可拍照

❌ **禁止拍照区域**：
- 特殊展区

💡 **拍照建议**：
- 最佳光线：待补充
- 最佳机位：待补充

---

## 季节性亮点

| 季节 | 亮点 | 推荐拍摄 |
|------|------|----------|
| 春 (3-5月) | 待补充 | 待补充 |
| 夏 (6-8月) | 待补充 | 待补充 |
| 秋 (9-11月) | 待补充 | 待补充 |
| 冬 (12-2月) | 待补充 | 待补充 |

---

## 冷门知识点

1. **知识1**: 待补充
2. **知识2**: 待补充
3. **知识3**: 待补充

---

## 扩展阅读

- 拍照机位：`references/photo-spots/{self.get_province_dir(attraction.province)}/{attraction.id}-spots.md`
- 文化讲解：`references/culture-stories/{self.get_province_dir(attraction.province)}/{attraction.id}-stories.md`
- 英文讲解：`references/culture-stories/{self.get_province_dir(attraction.province)}/{attraction.id}-stories-en.md`

---

**最后更新**: {datetime.now().strftime("%Y-%m-%d")}
**版本**: v1.0
'''
        return template

    def generate_photo_spots(self, attraction: AttractionInfo) -> str:
        """Generate photo spots Markdown template"""
        template = f'''# {attraction.name} - 拍照机位攻略

> **最后更新**: {datetime.now().strftime("%Y-%m")}

---

## 拍照机位列表

### 机位1: 待补充

**位置描述**
- 具体位置：待补充
- 最佳时间：待补充
- 建议设备：待补充

**拍摄参数参考**
- 光圈：f/8 - f/11
- 快门：1/125s - 1/250s
- ISO：100-400

**拍摄技巧**
- 构图建议：待补充
- 避开人流：待补充

---

### 机位2: 待补充

**位置描述**
- 具体位置：待补充
- 最佳时间：待补充
- 建议设备：待补充

**拍摄参数参考**
- 光圈：f/8 - f/11
- 快门：1/125s - 1/250s
- ISO：100-400

**拍摄技巧**
- 构图建议：待补充
- 避开人流：待补充

---

### 机位3: 待补充

**位置描述**
- 具体位置：待补充
- 最佳时间：待补充
- 建议设备：待补充

**拍摄参数参考**
- 光圈：f/8 - f/11
- 快门：1/125s - 1/250s
- ISO：100-400

**拍摄技巧**
- 构图建议：待补充
- 避开人流：待补充

---

### 机位4: 待补充

**位置描述**
- 具体位置：待补充
- 最佳时间：待补充
- 建议设备：待补充

**拍摄参数参考**
- 光圈：f/8 - f/11
- 快门：1/125s - 1/250s
- ISO：100-400

**拍摄技巧**
- 构图建议：待补充
- 避开人流：待补充

---

### 机位5: 待补充

**位置描述**
- 具体位置：待补充
- 最佳时间：待补充
- 建议设备：待补充

**拍摄参数参考**
- 光圈：f/8 - f/11
- 快门：1/125s - 1/250s
- ISO：100-400

**拍摄技巧**
- 构图建议：待补充
- 避开人流：待补充

---

## 拍摄路线推荐

```
入口 → 机位1 → 机位2 → 机位3 → 机位4 → 机位5 → 出口

总耗时：约2-3小时
最佳时段：上午9-11点 / 下午3-5点
```

---

## 季节拍摄建议

| 季节 | 最佳拍摄内容 | 推荐机位 |
|------|-------------|----------|
| 春季 | 待补充 | 待补充 |
| 夏季 | 待补充 | 待补充 |
| 秋季 | 待补充 | 待补充 |
| 冬季 | 待补充 | 待补充 |

---

**数据来源**: 小红书、马蜂窝、摄影社区
**最后更新**: {datetime.now().strftime("%Y-%m-%d")}
'''
        return template

    def generate_culture_story(self, attraction: AttractionInfo, lang: str = "zh") -> str:
        """Generate culture story Markdown template"""
        is_english = lang == "en"
        name = attraction.name_en if is_english else attraction.name

        if is_english:
            template = f'''# {name} - Culture Stories

> **Last Updated**: {datetime.now().strftime("%Y-%m")}

---

## L1: Brief Introduction (50-100 words)

{name} is a famous attraction in China. [Brief description to be filled]

**Highlights:**
- [Highlight 1]
- [Highlight 2]
- [Highlight 3]

---

## L2: Standard Guide (300-500 words)

### History and Background

[Historical background to be filled]

### What to See

[Main attractions and features to be filled]

### Cultural Significance

[Cultural significance to be filled]

### Practical Tips

- Best time to visit: [To be filled]
- Recommended duration: [To be filled]
- What to bring: [To be filled]

---

## L3: In-depth Exploration (800-1500 words)

### Detailed History

[Comprehensive historical account to be filled]

### Architectural Features

[Architectural details to be filled]

### Famous Figures and Events

[Notable figures and historical events to be filled]

### Legends and Stories

[Local legends and folklore to be filled]

### Conservation Efforts

[Preservation and conservation information to be filled]

### Modern Relevance

[Contemporary significance to be filled]

---

**Sources**: To be filled
**Last Updated**: {datetime.now().strftime("%Y-%m-%d")}
'''
        else:
            template = f'''# {name} - 文化故事

> **最后更新**: {datetime.now().strftime("%Y-%m")}

---

## L1: 简版介绍 (50-100字)

{name}是中国著名景区。[简短描述待补充]

**亮点：**
- [亮点1]
- [亮点2]
- [亮点3]

---

## L2: 标准讲解 (300-500字)

### 历史背景

[历史背景待补充]

### 主要看点

[主要景点和特色待补充]

### 文化内涵

[文化内涵待补充]

### 游览贴士

- 最佳游览时间：[待补充]
- 建议游览时长：[待补充]
- 注意事项：[待补充]

---

## L3: 深度讲解 (800-1500字)

### 详细历史

[详细历史待补充]

### 建筑特色

[建筑特色待补充]

### 名人与轶事

[历史名人和轶事待补充]

### 传说故事

[当地传说故事待补充]

### 保护与传承

[保护传承信息待补充]

### 现代意义

[当代价值待补充]

---

**资料来源**: 待补充
**最后更新**: {datetime.now().strftime("%Y-%m-%d")}
'''
        return template

    def generate_all_files(self, attraction: AttractionInfo) -> Dict[str, str]:
        """Generate all data files for an attraction"""
        province_dir = self.get_province_dir(attraction.province)

        files = {
            f"references/attractions/{province_dir}/{attraction.id}.md": self.generate_basic_info(attraction),
            f"references/photo-spots/{province_dir}/{attraction.id}-spots.md": self.generate_photo_spots(attraction),
            f"references/culture-stories/{province_dir}/{attraction.id}-stories.md": self.generate_culture_story(attraction, "zh"),
            f"references/culture-stories/{province_dir}/{attraction.id}-stories-en.md": self.generate_culture_story(attraction, "en"),
        }

        return files

    def save_files(self, files: Dict[str, str]) -> List[str]:
        """Save generated files to disk"""
        saved = []

        for rel_path, content in files.items():
            full_path = os.path.join(PROJECT_ROOT, rel_path)

            if self.dry_run:
                print(f"  [DRY RUN] Would create: {rel_path}")
                saved.append(rel_path)
                continue

            # Create directory if needed
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            # Check if file exists
            if os.path.exists(full_path):
                print(f"  [SKIP] File exists: {rel_path}")
                continue

            # Write file
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)

            print(f"  [CREATED] {rel_path}")
            saved.append(rel_path)

        self.generated_files.extend(saved)
        return saved

    def process_attraction(self, attraction_data: Dict) -> List[str]:
        """Process a single attraction"""
        attraction = AttractionInfo(
            id=attraction_data.get('id', ''),
            name=attraction_data.get('name', ''),
            name_en=attraction_data.get('name_en', ''),
            province=attraction_data.get('province', ''),
            city=attraction_data.get('city', ''),
            level=attraction_data.get('level', '5A'),
            category=attraction_data.get('category', '历史文化'),
            rating=attraction_data.get('rating', 4.5)
        )

        print(f"\nProcessing: {attraction.name} ({attraction.id})")
        print(f"  Province: {attraction.province}, City: {attraction.city}")
        print(f"  Category: {attraction.category}, Level: {attraction.level}")

        files = self.generate_all_files(attraction)
        return self.save_files(files)

    def process_list(self, list_path: str) -> Dict:
        """Process a list of attractions"""
        with open(list_path, 'r', encoding='utf-8') as f:
            attractions = json.load(f)

        print(f"\n{'='*60}")
        print(f"Processing {len(attractions)} attractions...")
        print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        print(f"{'='*60}")

        results = {
            "total": len(attractions),
            "processed": 0,
            "skipped": 0,
            "files_created": [],
            "errors": []
        }

        for i, attr in enumerate(attractions, 1):
            print(f"\n[{i}/{len(attractions)}]", end=" ")
            try:
                saved = self.process_attraction(attr)
                results["processed"] += 1
                results["files_created"].extend(saved)
            except Exception as e:
                print(f"  [ERROR] {str(e)}")
                results["errors"].append({
                    "attraction": attr.get('id', 'unknown'),
                    "error": str(e)
                })

        print(f"\n{'='*60}")
        print("Processing complete")
        print(f"{'='*60}")
        print(f"Total: {results['total']}")
        print(f"Processed: {results['processed']}")
        print(f"Files created: {len(results['files_created'])}")

        if results['errors']:
            print(f"Errors: {len(results['errors'])}")

        return results


# ============== CLI ==============

def main():
    import argparse

    parser = argparse.ArgumentParser(description='景区数据批量生成器')
    parser.add_argument('--attraction-id', help='Single attraction ID to process')
    parser.add_argument('--list', help='JSON file with list of attractions')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without creating files')
    parser.add_argument('--output-summary', help='Save summary to JSON file')

    args = parser.parse_args()

    generator = AttractionDataGenerator(dry_run=args.dry_run)

    if args.attraction_id:
        # Process single attraction
        # Load from 5A list or 4A list
        list_5a = os.path.join(DATA_DIR, '5a-attractions-list.json')
        list_4a = os.path.join(DATA_DIR, '4a-priority-list.json')

        attraction_data = None
        for list_file in [list_5a, list_4a]:
            if os.path.exists(list_file):
                with open(list_file, 'r', encoding='utf-8') as f:
                    attractions = json.load(f)
                    for a in attractions:
                        if a.get('id') == args.attraction_id:
                            attraction_data = a
                            break
            if attraction_data:
                break

        if not attraction_data:
            print(f"Attraction not found: {args.attraction_id}")
            return 1

        generator.process_attraction(attraction_data)

    elif args.list:
        # Process list
        results = generator.process_list(args.list)

        if args.output_summary:
            with open(args.output_summary, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"\nSummary saved to: {args.output_summary}")

    else:
        parser.print_help()
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())