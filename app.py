"""
Chinese Checker - Streamlit Web Application

A web interface for analyzing Chinese text comprehension based on known words.
"""

import streamlit as st
import tempfile
import os
from script import KNOWN_WORDS_DIR, UNKNOWN_WORDS_DIR, MAX_WORD_LENGTH, PUNCTUATION_CHARS, DPState
from script import load_cedict, get_pkuseg_segmenter, get_spacy_nlp, CEDICT_PATH, MAX_UNKNOWN_WORDS_DISPLAY
import unicodedata
from collections import Counter
from pypinyin import pinyin, Style
from typing import List, Set

# Page configuration
st.set_page_config(
    page_title="Chinese Checker",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .result-box {
        background-color: #f0f2f6;
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
    }
</style>
""", unsafe_allow_html=True)

def load_word_list_from_file(filepath: str) -> List[str]:
    """Load words from a single file."""
    words = []
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    word = line.split('\t')[0].split('#')[0].strip()
                    if word:
                        words.append(word)
    return words

def get_available_wordlists(directory: str) -> List[str]:
    """Get list of available HSK word list files."""
    if not os.path.exists(directory):
        return []
    files = [f for f in os.listdir(directory) if f.endswith('.txt')]
    # Sort HSK files in order
    hsk_order = ['HSK1.txt', 'HSK2.txt', 'HSK3.txt', 'HSK4.txt', 'HSK5.txt', 'HSK6.txt',
                 'HSKBand1.txt', 'HSKBand2.txt', 'HSKBand3.txt', 'HSKBand4.txt',
                 'HSKBand5.txt', 'HSKBand6.txt', 'HSKBand7-9.txt']
    sorted_files = []
    other_files = []
    
    for hsk_file in hsk_order:
        if hsk_file in files:
            sorted_files.append(hsk_file)
    
    # Add any other files not in the HSK list (like custom.txt) at the end
    for f in sorted(files):
        if f not in sorted_files:
            other_files.append(f)
    
    return sorted_files + other_files

def comprehension_checker_with_selection(text: str, selected_known: List[str], selected_unknown: List[str], all_files: List[tuple], custom_words: str = "") -> str:
    """Check comprehension with selected word lists and custom words."""
    try:
        # Load CC-CEDICT dictionary
        cedict = load_cedict(CEDICT_PATH)
        
        # Load selected known words
        base_words = set()
        for filename in selected_known:
            # Find the file in all_files to get its directory
            for fname, directory in all_files:
                if fname == filename:
                    filepath = os.path.join(directory, filename)
                    base_words.update(load_word_list_from_file(filepath))
                    break
        
        # Add custom words
        if custom_words:
            custom_word_list = [w.strip() for w in custom_words.split('\n') if w.strip()]
            base_words.update(custom_word_list)
        
        known_words = base_words.copy()
        
        # Load selected unknown words
        unknown_words_list = set()
        for filename in selected_unknown:
            # Find the file in all_files to get its directory
            for fname, directory in all_files:
                if fname == filename:
                    filepath = os.path.join(directory, filename)
                    unknown_words_list.update(load_word_list_from_file(filepath))
                    break
        
        if not text:
            raise ValueError("No text provided")
        
        # Clean up text
        normalized = unicodedata.normalize("NFKD", "".join(text.split()))
        cleaned = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
        
        if not cleaned:
            return "Error: No Chinese text found after filtering"
        
        # DP tokenization
        n = len(cleaned)
        dp: List[DPState] = [DPState(0, [], -1)] + [DPState(float('-inf'), [], -1)] * n
        
        def segment_unknown(text: str) -> List[str]:
            result = []
            i = 0
            segmenter = get_pkuseg_segmenter()
            
            while i < len(text):
                matched = False
                for length in range(min(MAX_WORD_LENGTH, len(text) - i), 0, -1):
                    candidate = text[i:i+length]
                    if candidate in unknown_words_list:
                        result.append(candidate)
                        i += length
                        matched = True
                        break
                
                if not matched:
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
        
        # Detect proper nouns
        proper_nouns = set()
        try:
            nlp = get_spacy_nlp()
            doc = nlp(cleaned)
            for ent in doc.ents:
                if ent.label_ in ['PERSON', 'GPE', 'ORG', 'FAC', 'LOC']:
                    proper_nouns.add(ent.text)
        except Exception:
            pass
        
        # Filter valid words
        def is_valid(word: str) -> bool:
            return (
                word.strip()
                and not word.isdigit()
                and not all(c in PUNCTUATION_CHARS for c in word)
                and not any(c.isascii() and (c.isalpha() or c.isdigit()) for c in word)
                and word not in proper_nouns
            )
        
        words = [word for word, _ in result if is_valid(word)]
        
        if not words:
            return "Error: No Chinese text found after filtering"
        
        # Calculate stats
        word_counts = Counter(words)
        
        def is_known(w):
            if w in base_words:
                return True
            return False
        
        total_words = len(words)
        unique_words = len(word_counts)
        known_count = sum(count for word, count in word_counts.items() if is_known(word))
        unknown_words = sorted(
            [(w, c) for w, c in word_counts.items() if not is_known(w)],
            key=lambda x: x[1], reverse=True
        )
        comprehension_pct = known_count / total_words * 100
        
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
        
    except Exception as e:
        return f"Error: An unexpected error occurred: {str(e)}"

def main():
    # Header
    st.markdown('<div class="main-header">📚 Chinese Checker</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Analyze Chinese text comprehension based on your known words</div>', unsafe_allow_html=True)
    
    # Get all word lists from both directories (needed for analysis)
    known_files = get_available_wordlists(KNOWN_WORDS_DIR)
    unknown_files = get_available_wordlists(UNKNOWN_WORDS_DIR)
    
    # Define HSK order
    hsk_order = ['HSK1.txt', 'HSK2.txt', 'HSK3.txt', 'HSK4.txt', 'HSK5.txt', 'HSK6.txt',
                 'HSKBand1.txt', 'HSKBand2.txt', 'HSKBand3.txt', 'HSKBand4.txt',
                 'HSKBand5.txt', 'HSKBand6.txt', 'HSKBand7-9.txt']
    
    all_files = []
    custom_files = []
    
    # Add HSK files in order from both directories
    for hsk_file in hsk_order:
        if hsk_file in known_files:
            all_files.append((hsk_file, KNOWN_WORDS_DIR))
        elif hsk_file in unknown_files:
            all_files.append((hsk_file, UNKNOWN_WORDS_DIR))
    
    # Don't include custom.txt files in the sidebar
    # Users will add custom words via the Custom Words tab
    
    # Sidebar for word list selection
    with st.sidebar:
        st.header("📚 HSK Word Lists")
        
        # Initialize session state with known files checked by default
        if 'selected_wordlists' not in st.session_state:
            st.session_state.selected_wordlists = set(known_files)
        
        # Separate HSK 2.0 and HSK 3.0 files
        hsk_2_files = []
        hsk_3_files = []
        
        for filename, directory in all_files:
            if 'HSKBand' in filename:
                hsk_3_files.append((filename, directory))
            else:
                hsk_2_files.append((filename, directory))
        
        # Display HSK 2.0 section
        if hsk_2_files:
            st.markdown("### HSK 2.0")
            for filename, directory in hsk_2_files:
                filepath = os.path.join(directory, filename)
                word_count = len(load_word_list_from_file(filepath))
                
                display_name = filename.replace('.txt', '')
                label = f"{display_name} ({word_count:,} words)"
                checked = st.checkbox(
                    label,
                    value=filename in st.session_state.selected_wordlists,
                    key=f"wordlist_{filename}"
                )
                
                if checked:
                    st.session_state.selected_wordlists.add(filename)
                else:
                    st.session_state.selected_wordlists.discard(filename)
        
        # Display HSK 3.0 section
        if hsk_3_files:
            st.markdown("### HSK 3.0")
            for filename, directory in hsk_3_files:
                filepath = os.path.join(directory, filename)
                word_count = len(load_word_list_from_file(filepath))
                
                display_name = filename.replace('.txt', '').replace('HSKBand', 'Band ')
                label = f"{display_name} ({word_count:,} words)"
                checked = st.checkbox(
                    label,
                    value=filename in st.session_state.selected_wordlists,
                    key=f"wordlist_{filename}"
                )
                
                if checked:
                    st.session_state.selected_wordlists.add(filename)
                else:
                    st.session_state.selected_wordlists.discard(filename)
        
    
    # Main content area with tabs
    tab1, tab2 = st.tabs(["📝 Analyze Text", "✏️ Custom Words"])
    
    with tab1:
        st.markdown("### Paste Chinese Text to Analyze")
        text_input = st.text_area(
            "Enter Chinese text to analyze:",
            height=300,
            placeholder="粘贴中文文本在这里...",
            label_visibility="collapsed"
        )
        
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            analyze_button = st.button("🔍 Analyze Text", type="primary", use_container_width=True, key="analyze_text")
        with col2:
            if st.button("🗑️ Clear", use_container_width=True, key="clear_text"):
                st.rerun()
        
        if analyze_button and text_input.strip():
            with st.spinner("Analyzing text..."):
                # Separate checked (known) and unchecked (unknown) lists
                selected_known = []
                selected_unknown = []
                
                for filename, directory in all_files:
                    if filename in st.session_state.selected_wordlists:
                        selected_known.append(filename)
                    else:
                        selected_unknown.append(filename)
                
                # Get custom words from session state
                custom_words = st.session_state.get('custom_words', '')
                
                result = comprehension_checker_with_selection(
                    text_input,
                    selected_known,
                    selected_unknown,
                    all_files,
                    custom_words
                )
                
                st.markdown("### 📊 Analysis Results")
                st.markdown('<div class="result-box">', unsafe_allow_html=True)
                st.code(result, language=None)
                st.markdown('</div>', unsafe_allow_html=True)
        elif analyze_button:
            st.warning("⚠️ Please enter some Chinese text to analyze.")
    
    with tab2:
        st.markdown("### Add Your Custom Words")
        st.markdown("Enter words you know (one per line):")
        
        # Initialize custom words in session state
        if 'custom_words' not in st.session_state:
            st.session_state.custom_words = ''
        
        custom_input = st.text_area(
            "Custom Words",
            value=st.session_state.custom_words,
            height=400,
            placeholder="你好\n再见\n谢谢",
            label_visibility="collapsed",
            key="custom_words_input"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Save Custom Words", use_container_width=True, key="save_custom"):
                st.session_state.custom_words = custom_input
                word_count = len([w for w in custom_input.split('\n') if w.strip()])
                st.success(f"✅ Saved {word_count} custom words!")
        with col2:
            if st.button("🗑️ Clear Custom Words", use_container_width=True, key="clear_custom"):
                st.session_state.custom_words = ''
                st.rerun()
    
    # Footer
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Comprehension Levels:**")
        st.markdown("""
        - ⛔ <82%: Too Difficult
        - 🔴 82-87%: Very Challenging
        - 🟡 87-89%: Challenging
        """)
    with col2:
        st.markdown("**Optimal Range:**")
        st.markdown("""
        - 🟢 89-92%: Optimal (i+1)
        - 🔵 92-95%: Comfortable
        - ⚪ >95%: Too Easy
        """)
    with col3:
        st.markdown("**Tips:**")
        st.markdown("""
        - Add HSK words to Known Words
        - Target 89-92% for best learning
        - Proper nouns are auto-excluded
        """)

if __name__ == "__main__":
    # Ensure directories exist
    os.makedirs(KNOWN_WORDS_DIR, exist_ok=True)
    os.makedirs(UNKNOWN_WORDS_DIR, exist_ok=True)
    
    main()