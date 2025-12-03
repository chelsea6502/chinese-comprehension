"""
Chinese Checker

Analyzes Chinese text from input files to calculate comprehension based on known words.
Uses dynamic programming for optimal word segmentation.
"""

import spacy_pkuseg as pkuseg
import spacy
import unicodedata
from collections import Counter, namedtuple
from pypinyin import pinyin, Style
from typing import List, Set, Dict
import os
import logging
import sys

# Configure logging - suppress all INFO messages
logging.basicConfig(
    level=logging.ERROR,
    format='%(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)
# Disable all INFO level logging
logging.getLogger().setLevel(logging.ERROR)

# Constants
MAX_WORD_LENGTH = 4
KNOWN_WORDS_DIR = "known"
UNKNOWN_WORDS_DIR = "unknown"
INPUT_DIR = "input"
MAX_UNKNOWN_WORDS_DISPLAY = 20
CEDICT_PATH = "definitions.txt"  # Path to CC-CEDICT dictionary file

# Initialize pkuseg segmenter (only once for efficiency)
# pkuseg provides superior accuracy (96.88% F1 on MSRA) from Peking University
# Uses pre-trained models optimized for web/news/mixed domains
pkuseg_segmenter = None

# Initialize spaCy NER model (only once for efficiency)
spacy_nlp = None

def get_pkuseg_segmenter():
    """Lazy load pkuseg segmenter to avoid slow startup"""
    global pkuseg_segmenter
    if pkuseg_segmenter is None:
        # Use 'mixed' model for best general-purpose accuracy
        # Other options: 'news', 'web', 'medicine', 'tourism'
        pkuseg_segmenter = pkuseg.pkuseg(model_name='mixed')
    return pkuseg_segmenter

def get_spacy_nlp():
    """Lazy load spaCy NER model to avoid slow startup"""
    global spacy_nlp
    if spacy_nlp is None:
        try:
            spacy_nlp = spacy.load("zh_core_web_sm")
        except OSError:
            logger.warning("spaCy Chinese model not found. Downloading zh_core_web_sm (~50MB)...")
            try:
                import subprocess
                subprocess.check_call([sys.executable, "-m", "spacy", "download", "zh_core_web_sm"])
                spacy_nlp = spacy.load("zh_core_web_sm")
            except Exception as e:
                logger.error(f"Failed to download spaCy model: {e}")
                raise RuntimeError(f"Could not download spaCy Chinese model: {e}")
    return spacy_nlp

# Comprehensive punctuation set
PUNCTUATION_CHARS = set(
    '✓\",.:()!@[]+/\\！?？｡。＂＃＄％＆＇（）＊＋，－／：；＜＝＞＠［＼］＾＿｀｛｜｝～'
    '｟｠｢｣､、〃《》「」『』【】〔〕〖〗〘〙〚〛〜〝〞〟〰〾〿–—''‛""„‟…‧﹏.?;﹔|.-·-*─\'\'\"\""'
    '★☆○●◎◇◆□■△▲▽▼※→←↑↓⇒⇐⇑⇓∴∵∈∋⊆⊇⊂⊃∪∩∧∨¬∀∃'  # Symbols
    '=≠≈≡≤≥<>±×÷∞∫∑∏√∂∇'  # Math symbols
    '""''‹›«»‚„'  # Additional quotation marks
)

# Named tuple for DP state
DPState = namedtuple('DPState', ['score', 'segmentation', 'unknown_start'])


def load_cedict(path: str) -> Dict[str, str]:
    """Load CC-CEDICT dictionary into memory for instant lookups.
    
    Returns a dictionary mapping Chinese words to their English definitions.
    """
    cedict = {}
    if not os.path.exists(path):
        logger.warning(f"CC-CEDICT not found, definitions unavailable")
        return cedict
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                
                # Parse CC-CEDICT format: 傳統 传统 [chuan2 tong3] /traditional/
                try:
                    # Split on first space to separate traditional/simplified from rest
                    parts = line.split(' ', 2)
                    if len(parts) < 3:
                        continue
                    
                    traditional = parts[0]
                    simplified = parts[1]
                    rest = parts[2]
                    
                    # Extract definition (between / characters)
                    if '/' in rest:
                        defs_start = rest.find('/')
                        defs_end = rest.rfind('/')
                        if defs_start < defs_end:
                            definitions = rest[defs_start+1:defs_end]
                            # Take first definition if multiple
                            first_def = definitions.split('/')[0]
                            # Store both traditional and simplified
                            cedict[simplified] = first_def
                            if traditional != simplified:
                                cedict[traditional] = first_def
                except Exception as e:
                    continue
    except Exception as e:
        logger.error(f"Error loading CC-CEDICT: {e}")
    
    return cedict


def comprehension_checker(text: str, known_words_dir: str = KNOWN_WORDS_DIR) -> str:
    """Check comprehension of Chinese text against known words.
    Automatically excludes proper nouns (names, places) for accurate comprehension measurement.
    
    Args:
        text: The Chinese text to analyze
        known_words_dir: Directory containing known words files
    
    Returns:
        Analysis report as a string
    """
    try:
        # Load CC-CEDICT dictionary for instant offline lookups
        cedict = load_cedict(CEDICT_PATH)
        
        # Load known words from all .txt files in known directory
        base_words = set()
        if os.path.exists(known_words_dir) and os.path.isdir(known_words_dir):
            txt_files = [f for f in os.listdir(known_words_dir) if f.endswith('.txt')]
            for txt_file in txt_files:
                file_path = os.path.join(known_words_dir, txt_file)
                with open(file_path, encoding="utf8") as f:
                    base_words.update(f.read().split())
        else:
            raise FileNotFoundError(f"Known words directory not found: '{known_words_dir}'")
        
        known_words = base_words.copy()
        
        # Load unknown words from all .txt files in unknown directory
        unknown_words_list = set()
        if os.path.exists(UNKNOWN_WORDS_DIR) and os.path.isdir(UNKNOWN_WORDS_DIR):
            txt_files = [f for f in os.listdir(UNKNOWN_WORDS_DIR) if f.endswith('.txt')]
            for txt_file in txt_files:
                file_path = os.path.join(UNKNOWN_WORDS_DIR, txt_file)
                with open(file_path, encoding="utf8") as f:
                    for line in f:
                        # Skip comments and empty lines
                        line = line.strip()
                        if line and not line.startswith('#'):
                            # Extract word (before any tab or comment)
                            word = line.split('\t')[0].split('#')[0].strip()
                            if word:
                                unknown_words_list.add(word)
        
        if not text:
            raise ValueError("No text provided")
        
        # Clean up: remove whitespace and diacritics
        normalized = unicodedata.normalize("NFKD", "".join(text.split()))
        cleaned = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
        
        if not cleaned:
            return "Error: No Chinese text found after filtering"
        
        # DP tokenization to maximize known word coverage
        n = len(cleaned)
        dp: List[DPState] = [DPState(0, [], -1)] + [DPState(float('-inf'), [], -1)] * n
        
        # Helper function to segment unknown text
        def segment_unknown(text: str) -> List[str]:
            """Segment unknown text by first checking unknown.txt, then using pkuseg"""
            result = []
            i = 0
            segmenter = get_pkuseg_segmenter()
            
            while i < len(text):
                # Try to match against unknown_words_list (longest match first)
                matched = False
                for length in range(min(MAX_WORD_LENGTH, len(text) - i), 0, -1):
                    candidate = text[i:i+length]
                    if candidate in unknown_words_list:
                        result.append(candidate)
                        i += length
                        matched = True
                        break
                
                if not matched:
                    # If no match in unknown.txt, use pkuseg for this segment
                    # Find the next unknown word boundary or end of text
                    j = i + 1
                    while j < len(text):
                        found_unknown = False
                        for length in range(min(MAX_WORD_LENGTH, len(text) - j), 0, -1):
                            if text[j:j+length] in unknown_words_list:
                                found_unknown = True
                                break
                        if found_unknown:
                            break
                        j += 1
                    
                    # Use pkuseg on this segment
                    # pkuseg.cut() returns a list of word strings
                    result.extend(segmenter.cut(text[i:j]))
                    i = j
            
            return result
        
        for i in range(1, n + 1):
            for j in range(max(0, i - MAX_WORD_LENGTH), i):
                word = cleaned[j:i]
                
                if word in known_words:
                    prev = dp[j]
                    new_seg = prev.segmentation.copy()
                    
                    if prev.unknown_start != -1:
                        new_seg.extend([(w, False) for w in segment_unknown(cleaned[prev.unknown_start:j])])
                    
                    new_seg.append((word, True))
                    new_score = prev.score + len(word)
                    
                    if new_score > dp[i].score:
                        dp[i] = DPState(new_score, new_seg, -1)
            
            if dp[i].score == float('-inf'):
                best_prev = max(range(i), key=lambda x: dp[x].score)
                prev = dp[best_prev]
                unknown_start = best_prev if prev.unknown_start == -1 else prev.unknown_start
                dp[i] = DPState(prev.score, prev.segmentation.copy(), unknown_start)
        
        final = dp[n]
        result = final.segmentation.copy()
        
        if final.unknown_start != -1:
            result.extend([(w, False) for w in segment_unknown(cleaned[final.unknown_start:n])])
        
        # Detect proper nouns using spaCy NER
        proper_nouns = set()
        try:
            nlp = get_spacy_nlp()
            # Process the cleaned text for NER
            doc = nlp(cleaned)
            # Extract proper nouns (PERSON, GPE=location, ORG, FAC=facility, LOC)
            for ent in doc.ents:
                if ent.label_ in ['PERSON', 'GPE', 'ORG', 'FAC', 'LOC']:
                    proper_nouns.add(ent.text)
        except Exception as e:
            logger.warning(f"NER detection failed: {e}. Continuing without proper noun exclusion.")
        
        # Filter to valid Chinese words only
        def is_valid(word: str) -> bool:
            if not word.strip() or word in proper_nouns:
                return False
            
            # Check if word contains at least one valid CJK character
            # CJK Unified Ideographs: U+4E00 to U+9FFF (most common Chinese characters)
            # CJK Extension A: U+3400 to U+4DBF
            # CJK Extension B-F: U+20000 to U+2EBEF
            has_chinese = any('\u4e00' <= c <= '\u9fff' or
                            '\u3400' <= c <= '\u4dbf' or
                            '\U00020000' <= c <= '\U0002ebef'
                            for c in word)
            
            if not has_chinese:
                return False
            
            # Reject if word is purely digits or contains ASCII letters/digits
            if word.isdigit() or any(c.isascii() and (c.isalpha() or c.isdigit()) for c in word):
                return False
            
            return True
        
        words = [word for word, _ in result if is_valid(word)]
        
        if not words:
            return "Error: No Chinese text found after filtering"
        
        # Calculate stats
        word_counts = Counter(words)
        # A word is known if:
        # 1. It's explicitly in base_words (known.txt) - always treated as known, even if in unknown.txt
        # 2. It's NOT in unknown_words_list (explicit unknown words take precedence)
        def is_known(w):
            # Explicit entries in known.txt are always known (even if in unknown.txt)
            if w in base_words:
                return True
            # Otherwise, it's unknown
            return False
        
        total_words = len(words)
        unique_words = len(word_counts)
        known_count = sum(count for word, count in word_counts.items() if is_known(word))
        unknown_words = sorted(
            [(w, c) for w, c in word_counts.items() if not is_known(w)],
            key=lambda x: x[1], reverse=True
        )
        comprehension_pct = known_count / total_words * 100
        
        
        # Determine difficulty assessment (accounting for ~3% pkuseg segmentation error)
        # Actual comprehension is likely 3% higher than shown due to over-segmentation
        def get_assessment(pct: float) -> str:
            if pct < 82:
                return "⛔ Too Difficult"
            elif pct < 87:
                return "🔴 Very Challenging"
            elif pct < 89:
                return "🟡 Challenging"
            elif pct < 92:
                return "🟢 Optimal (i+1)"
            elif pct < 95:
                return "🔵 Comfortable"
            else:
                return "⚪ Too Easy"
        
        assessment = get_assessment(comprehension_pct)
        
        # Format output
        lines = [
            f"\nWord Count: {total_words}",
            f"Total Unique Words: {unique_words}",
            f"Comprehension: {comprehension_pct:.1f}% - {assessment}",
            f"Unique Unknown Words: {len(unknown_words)}"
        ]
        
        if unknown_words:
            lines.append("\n=== Unknown Words (by frequency) ===")
            display_count = min(len(unknown_words), MAX_UNKNOWN_WORDS_DISPLAY)
            
            for idx, (word, count) in enumerate(unknown_words[:display_count]):
                word_pinyin = ' '.join(p[0] for p in pinyin(word, style=Style.TONE))
                
                # Fast offline definition lookup from CC-CEDICT
                definition = ""
                if cedict and word in cedict:
                    meaning = cedict[word]
                    if len(meaning) > 80:
                        meaning = meaning[:77] + "..."
                    definition = f" - {meaning}"
                
                lines.append(f"{word} ({word_pinyin}) : {count}{definition}")
            
            if len(unknown_words) > display_count:
                lines.append(f"... and {len(unknown_words) - display_count} more")
        
        return '\n'.join(lines)
        
    except FileNotFoundError as e:
        return f"Error: {str(e)}"
    except ValueError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error: An unexpected error occurred: {str(e)}"


def process_input_files(input_dir: str = INPUT_DIR) -> None:
    """Process all txt files in the input directory and generate reports.
    
    Args:
        input_dir: Directory containing input text files to analyze
    """
    if not os.path.exists(input_dir):
        logger.error(f"Input directory not found: '{input_dir}'")
        print(f"Error: Input directory '{input_dir}' does not exist.")
        print(f"Please create the directory and add .txt files to analyze.")
        return
    
    if not os.path.isdir(input_dir):
        logger.error(f"'{input_dir}' is not a directory")
        print(f"Error: '{input_dir}' is not a directory.")
        return
    
    # Get all txt files in the input directory
    txt_files = [f for f in os.listdir(input_dir) if f.endswith('.txt')]
    
    if not txt_files:
        logger.warning(f"No .txt files found in '{input_dir}'")
        print(f"No .txt files found in '{input_dir}' directory.")
        print(f"Please add .txt files containing Chinese text to analyze.")
        return
    
    print(f"📊 Processing {len(txt_files)} file(s)...\n")
    
    # Process each file
    for txt_file in txt_files:
        file_path = os.path.join(input_dir, txt_file)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
            
            if not text.strip():
                logger.warning(f"File '{txt_file}' is empty, skipping")
                print(f"\n[{txt_file}] - SKIPPED (empty file)")
                continue
            
            # Generate report
            print(f"\n{'='*60}")
            print(f"File: {txt_file}")
            print('='*60)
            result = comprehension_checker(text)
            print(result)
            
        except Exception as e:
            logger.error(f"Error processing '{txt_file}': {e}")
            print(f"\n[{txt_file}] - ERROR: {e}")


if __name__ == "__main__":
    process_input_files()
