# Chinese Comprehension Checker

Analyze Chinese text from your clipboard to gauge comprehension based on your known words.

## Features
- Analyzes Chinese text directly from clipboard
- **Uses pkuseg (Peking University) for superior word segmentation (96.88% F1 accuracy)**
- **Automatic proper noun detection using spaCy NER** - excludes names and places for accurate comprehension
- Uses dynamic programming for optimal word segmentation
- Calculates comprehension percentage based on known words
- Lists unknown words with pinyin and frequency
- Instant offline dictionary lookups via CC-CEDICT
- Supports optional `unknown.txt` file to exclude compound words from being counted as known
- Filters out punctuation, numbers, and English content automatically
- Verbose logging to track initialization and processing

## Requirements
* Python 3.9 or above
* [spacy-pkuseg](https://github.com/explosion/spacy-pkuseg) - Peking University's Chinese segmentation (96.88% F1 on MSRA)
* [spaCy](https://spacy.io/) - Industrial-strength NLP for proper noun detection
* pyperclip - Clipboard access
* pypinyin - Pinyin conversion

## Installation

### Step 1: Install Python
Download Python 3.9 or above from [python.org](https://www.python.org/downloads/)

### Step 2: Clone or Download
```bash
git clone https://github.com/chelsea6502/chinese-comprehension.git
cd chinese-comprehension
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

**Note:**
- On first run, the script will automatically download required models:
  - pkuseg 'mixed' model (~20MB) for word segmentation
  - spaCy Chinese model zh_core_web_sm (~50MB) for proper noun detection
- Both are one-time downloads that happen automatically when needed

## Usage

### Basic Usage
1. Copy Chinese text to your clipboard
2. Run the script:
```bash
python script.py
```

**First Run:** The script will automatically download required models (pkuseg and spaCy) on first use. This may take a few minutes but only happens once.

### Known Words File
By default, the script looks for `known.txt` in the same directory. To use a different file, modify the `DEFAULT_KNOWN_WORDS_PATH` constant in the script.

Create a `known.txt` file with one word per line:
```
是
你好
再见
有
五
```

### Unknown Words File (Optional)
Create an optional `unknown.txt` file to list compound words that should NOT be counted as known, even if all their individual characters are known. This prevents false positives where compound words are incorrectly counted as known.

Format (one word per line, comments with # are optional):
```
好吃	# hǎo chī
道理	# dào lǐ
行者	# xíng zhě
```

**Why use this?** If you know the characters 好 and 吃 individually, the script would normally count 好吃 as "known". But if you haven't learned 好吃 as a compound word, add it to `unknown.txt` to exclude it from your comprehension calculation.

**Note:** If a word appears in both `known.txt` and `unknown.txt`, it will be treated as known (explicit entries in `known.txt` take priority).

### Proper Noun Exclusion
The script automatically detects and excludes proper nouns (人名 person names, 地名 place names, 机构名 organizations) from comprehension calculations using spaCy's Named Entity Recognition. This provides more accurate comprehension measurements by focusing on vocabulary rather than memorized names.

**Why exclude proper nouns?**
- Recognizing "李明" (a person's name) doesn't mean you know the characters 李 or 明 in other contexts
- Place names like "北京" are often memorized without understanding the component characters
- Focusing on common vocabulary gives a truer picture of reading ability

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

### Proper Noun Detection
Uses **spaCy's zh_core_web_sm model** for Named Entity Recognition:
- Detects PERSON (人名), GPE (地名), ORG (机构), FAC (设施), LOC (位置)
- Trained on OntoNotes 5.0 Chinese corpus
- Excludes detected proper nouns from comprehension calculations by default
- Provides more accurate vocabulary assessment

### Word Segmentation
This tool uses **pkuseg** from Peking University, which provides:
- **96.88% F1 accuracy** on MSRA benchmark (news text)
- **79% error rate reduction** compared to jieba
- Pre-trained models optimized for different domains (mixed, news, web, medicine, tourism)
- Uses the 'mixed' model by default for best general-purpose accuracy

### Segmentation Strategy
1. **Priority 1:** Match against your `known.txt` words using dynamic programming
2. **Priority 2:** Match against `unknown.txt` for pre-defined difficult words
3. **Fallback:** Use pkuseg for remaining unknown segments

This hybrid approach maximizes accuracy for your specific vocabulary.

### Performance Benchmarks
Based on Peking University evaluations (2019):

| Package | MSRA F1 (News) | CTB8 F1 (Mixed) | Weibo F1 (Web) | Average |
|---------|----------------|-----------------|----------------|---------|
| **pkuseg** | **96.88%** | **94.21%** | **93.43%** | **91.29%** |
| THULAC | 95.71% | 92.87% | 86.65% | 88.08% |
| LTP | ~95% | ~92% | ~88% | 83-95% |
| jieba | 88.42% | 87.66% | 83.56% | 81.61% |

### Why pkuseg?
- **Highest accuracy** on general Chinese text (96.88% F1 on MSRA)
- **79% error reduction** vs jieba on standard benchmarks
- **Domain-specific models** available for specialized text
- **Stable and maintained** by Peking University NLP team
- **Easy installation** via pip with no build issues

## License

MIT License - feel free to use and modify as needed.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
