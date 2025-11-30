"""
Chinese Comprehension Checker

Analyzes Chinese text from clipboard to calculate comprehension based on known words.
Uses dynamic programming for optimal word segmentation.
"""

import spacy_pkuseg as pkuseg
import pyperclip
import unicodedata
from collections import Counter, namedtuple
from pypinyin import pinyin, Style
from typing import List, Set, Dict
import os
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Constants
MAX_WORD_LENGTH = 4
DEFAULT_KNOWN_WORDS_PATH = "known.txt"
UNKNOWN_WORDS_PATH = "unknown.txt"
MAX_UNKNOWN_WORDS_DISPLAY = 20
CEDICT_PATH = "cedict_1_0_ts_utf-8_mdbg.txt"  # Path to CC-CEDICT dictionary file

# Initialize pkuseg segmenter (only once for efficiency)
# pkuseg provides superior accuracy (96.88% F1 on MSRA) from Peking University
# Uses pre-trained models optimized for web/news/mixed domains
pkuseg_segmenter = None

def get_pkuseg_segmenter():
    """Lazy load pkuseg segmenter to avoid slow startup"""
    global pkuseg_segmenter
    if pkuseg_segmenter is None:
        logger.info("Initializing pkuseg segmenter (loading model)...")
        # Use 'mixed' model for best general-purpose accuracy
        # Other options: 'news', 'web', 'medicine', 'tourism'
        pkuseg_segmenter = pkuseg.pkuseg(model_name='mixed')
        logger.info("pkuseg initialized")
    return pkuseg_segmenter

# Comprehensive punctuation set
PUNCTUATION_CHARS = set(
    '✓\",.:()!@[]+/\\！?？｡。＂＃＄％＆＇（）＊＋，－／：；＜＝＞＠［＼］＾＿｀｛｜｝～'
    '｟｠｢｣､、〃《》「」『』【】〔〕〖〗〘〙〚〛〜〝〞〟〰〾〿–—''‛""„‟…‧﹏.?;﹔|.-·-*─\'\'\"\""'
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
    
    logger.info(f"Loaded {len(cedict)} definitions")
    return cedict


def comprehension_checker(known_words_path: str = DEFAULT_KNOWN_WORDS_PATH) -> str:
    """Check comprehension of Chinese text from clipboard against known words."""
    logger.info("Starting analysis...")
    
    try:
        # Load CC-CEDICT dictionary for instant offline lookups
        cedict = load_cedict(CEDICT_PATH)
        
        # Load known words (no character expansion)
        with open(known_words_path, encoding="utf8") as f:
            base_words = set(f.read().split())
        known_words = base_words.copy()
        logger.info(f"Loaded {len(base_words)} known words")
        
        # Load unknown words to exclude from known word counting
        unknown_words_list = set()
        try:
            with open(UNKNOWN_WORDS_PATH, encoding="utf8") as f:
                for line in f:
                    # Skip comments and empty lines
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Extract word (before any tab or comment)
                        word = line.split('\t')[0].split('#')[0].strip()
                        if word:
                            unknown_words_list.add(word)
        except FileNotFoundError:
            pass
        
        text = pyperclip.paste()
        if not text:
            raise ValueError("Clipboard is empty")
        
        # Clean up: remove whitespace and diacritics
        normalized = unicodedata.normalize("NFKD", "".join(text.split()))
        cleaned = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
        logger.info(f"Processing {len(cleaned)} characters...")
        
        if not cleaned:
            return "Error: No Chinese text found in clipboard after filtering"
        
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
        
        # Filter to valid Chinese words only
        def is_valid(word: str) -> bool:
            return (
                word.strip()
                and not word.isdigit()
                and not all(c in PUNCTUATION_CHARS for c in word)
                and not any(c.isascii() and (c.isalpha() or c.isdigit()) for c in word)
            )
        
        words = [word for word, _ in result if is_valid(word)]
        
        if not words:
            return "Error: No Chinese text found in clipboard after filtering"
        
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
        logger.info(f"Analysis complete: {comprehension_pct:.1f}% comprehension")
        
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
        
    except FileNotFoundError:
        return f"Error: Known words file not found at '{known_words_path}'"
    except ValueError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error: An unexpected error occurred: {str(e)}"


if __name__ == "__main__":
    logger.info("Script started")
    print(comprehension_checker())
    logger.info("Script finished")
