# Data Quality Report

> Generated: 2026-03-27T13:10:29.033845

## Overview

| Metric | Value |
|--------|-------|
| Sampled Attractions | 5 |
| Average Score | 83.2 |
| Excellent (>=90) | 0 |
| Good (70-89) | 5 |
| Poor (<70) | 0 |

## Category Average Scores

| Data Type | Average Score |
|-----------|---------------|
| Basic Info | 60.0 |
| Photo Spots | 92.0 |
| Chinese Stories | 90.0 |
| English Stories | 99.0 |

## Attraction Details

### Forbidden City (forbidden-city) [WARN]

| Data Type | Score | Status |
|-----------|-------|--------|
| Basic Info | 60 | FAIL |
| Photo Spots | 95 | OK |
| Chinese Stories | 90 | OK |
| English Stories | 100 | OK |
| **Total** | **84** | [WARN] |

**Issues:**

- [WARN] [basic_info] Missing opening hours
- [WARN] [basic_info] Missing ticket info
- [WARN] [basic_info] Missing visit duration
- [INFO] [photo_spots] Missing location details
- [WARN] [stories_zh] L2 words: 259 < 300
- [WARN] [stories_zh] L3 words: 594 < 800

**Recommendations:**

- Improve basic info with required fields

### Terracotta Army (terracotta-army) [WARN]

| Data Type | Score | Status |
|-----------|-------|--------|
| Basic Info | 60 | FAIL |
| Photo Spots | 95 | OK |
| Chinese Stories | 90 | OK |
| English Stories | 100 | OK |
| **Total** | **84** | [WARN] |

**Issues:**

- [WARN] [basic_info] Missing opening hours
- [WARN] [basic_info] Missing ticket info
- [WARN] [basic_info] Missing visit duration
- [INFO] [photo_spots] Missing location details
- [WARN] [stories_zh] L2 words: 197 < 300
- [WARN] [stories_zh] L3 words: 461 < 800

**Recommendations:**

- Improve basic info with required fields

### West Lake (west-lake) [WARN]

| Data Type | Score | Status |
|-----------|-------|--------|
| Basic Info | 60 | FAIL |
| Photo Spots | 90 | OK |
| Chinese Stories | 90 | OK |
| English Stories | 100 | OK |
| **Total** | **83** | [WARN] |

**Issues:**

- [WARN] [basic_info] Missing opening hours
- [WARN] [basic_info] Missing ticket info
- [WARN] [basic_info] Missing visit duration
- [INFO] [photo_spots] Missing location details
- [INFO] [photo_spots] Missing best time info
- [WARN] [stories_zh] L2 words: 143 < 300
- [WARN] [stories_zh] L3 words: 358 < 800

**Recommendations:**

- Improve basic info with required fields

### Yellow Mountain (yellow-mountain) [WARN]

| Data Type | Score | Status |
|-----------|-------|--------|
| Basic Info | 60 | FAIL |
| Photo Spots | 90 | OK |
| Chinese Stories | 90 | OK |
| English Stories | 100 | OK |
| **Total** | **83** | [WARN] |

**Issues:**

- [WARN] [basic_info] Missing opening hours
- [WARN] [basic_info] Missing ticket info
- [WARN] [basic_info] Missing visit duration
- [INFO] [photo_spots] Missing location details
- [INFO] [photo_spots] Missing best time info
- [WARN] [stories_zh] L2 words: 137 < 300
- [WARN] [stories_zh] L3 words: 316 < 800

**Recommendations:**

- Improve basic info with required fields

### Jiuzhaigou (jiuzhaigou) [WARN]

| Data Type | Score | Status |
|-----------|-------|--------|
| Basic Info | 60 | FAIL |
| Photo Spots | 90 | OK |
| Chinese Stories | 90 | OK |
| English Stories | 95 | OK |
| **Total** | **82** | [WARN] |

**Issues:**

- [WARN] [basic_info] Missing opening hours
- [WARN] [basic_info] Missing ticket info
- [WARN] [basic_info] Missing visit duration
- [INFO] [photo_spots] Missing location details
- [INFO] [photo_spots] Missing best time info
- [WARN] [stories_zh] L2 words: 119 < 300
- [WARN] [stories_zh] L3 words: 299 < 800
- [WARN] [stories_en] L3 words: 718 < 800

**Recommendations:**

- Improve basic info with required fields

## Overall Recommendations

- Overall basic info needs improvement
