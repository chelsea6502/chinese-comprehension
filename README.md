# Chinese Comprehension Checker

Analyze Chinese text from your clipboard to gauge comprehension based on your known words.

## Features
- Clipboard text analysis with comprehension percentage
- pkuseg word segmentation (96.88% F1 accuracy)
- Automatic proper noun detection (excludes names/places)
- Unknown words listed with pinyin, frequency, and definitions
- Optional `unknown.txt` to exclude compound words

## Requirements
Python 3.9+ and dependencies in `requirements.txt` (pkuseg, spaCy, pyperclip, pypinyin)

## Installation

```bash
git clone https://github.com/chelsea6502/chinese-comprehension.git
cd chinese-comprehension
pip install -r requirements.txt
```

Models (pkuseg + spaCy zh_core_web_sm) download automatically on first run.

## Usage

1. Copy Chinese text to clipboard
2. Run: `python script.py`

### Known Words File
Create `known.txt` with one word per line:
```
是
你好
再见
有
五
```

### Unknown Words File (Optional)
List compound words that shouldn't count as known even if individual characters are known:
```
好吃	# hǎo chī
道理	# dào lǐ
行者	# xíng zhě
```

Entries in `known.txt` take priority over `unknown.txt`.

## Example Output

```
Word Count: 1523
Total Unique Words: 487
Comprehension: 92.3%
Unique Unknown Words: 23

=== Unknown Words (by frequency) ===
道 (dào) : 15 - way, path, principle
行者 (xíng zhě) : 8 - traveler, pilgrim
裏 (lǐ) : 6 - inside, interior
與 (yǔ) : 5 - and, with, to give
...
```

## Technical Details

**Segmentation Strategy:**
1. Match against `known.txt` (dynamic programming)
2. Match against `unknown.txt`
3. Fallback to pkuseg for remaining text

**Proper Noun Detection:** spaCy NER excludes PERSON, GPE, ORG, FAC, LOC entities from calculations.

## License

MIT
