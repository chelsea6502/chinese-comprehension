# Chinese Checker

Analyze Chinese text from your clipboard to gauge comprehension based on your known words.

## Acknowledgments

This project is based on [Destaq/chinese-comprehension](https://github.com/Destaq/chinese-comprehension) as the starting point.

## Features
- Clipboard text analysis with comprehension percentage
- pkuseg word segmentation (~97% accuracy)
- Automatic proper noun detection (excludes names/places)
- Unknown words listed with pinyin, frequency, and definitions
- Organize known/unknown words across multiple `.txt` files

## Requirements
Python 3.9+ and dependencies in `requirements.txt` (pkuseg, spaCy, pyperclip, pypinyin)

## Installation

```bash
git clone https://github.com/chelsea6502/chinese-checker.git
cd chinese-checker
pip install -r requirements.txt
```

Models (pkuseg + spaCy zh_core_web_sm) download automatically on first run.

## Usage

1. Copy Chinese text to clipboard
2. Run: `python script.py`

### Known Words Directory
Create `.txt` files in the `known/` directory with one word per line. You can organize words across multiple files:

**known/hsk1.txt:**
```
是
你好
再见
```

**known/hsk2.txt:**
```
有
五
```

### Unknown Words Directory (Optional)
Create `.txt` files in the `unknown/` directory to list compound words that shouldn't count as known even if individual characters are known:

**unknown/compounds.txt:**
```
好吃	# hǎo chī
道理	# dào lǐ
行者	# xíng zhě
```

Entries in `known/` files take priority over `unknown/` files.

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
1. Match against all `.txt` files in `known/` directory (dynamic programming)
2. Match against all `.txt` files in `unknown/` directory
3. Fallback to pkuseg for remaining text

**Proper Noun Detection:** spaCy NER excludes PERSON, GPE, ORG, FAC, LOC entities from calculations.

## License

MIT
