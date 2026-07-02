import re

def normalize_whitespace(text: str) -> str:
    """Replaces all contiguous whitespace with a single space and strips."""
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()

def fuzzy_extract_after(full_text: str, sent_instruction: str) -> str:
    """
    Extracts everything in `full_text` that comes AFTER the `sent_instruction`.
    Tolerates whitespace and newline differences caused by UI rendering.
    """
    if not full_text:
        return ""
    if not sent_instruction:
        return full_text

    norm_full = normalize_whitespace(full_text)
    norm_sent = normalize_whitespace(sent_instruction)

    # Use the last 50 characters of the normalized sent instruction to find the split point.
    # The end of the instruction is much less likely to be truncated than the beginning.
    suffix = norm_sent[-50:] if len(norm_sent) > 50 else norm_sent
    
    # Find the suffix in the normalized full text
    idx = norm_full.rfind(suffix)
    if idx == -1:
        # Fallback: if we can't find it, we might be dealing with a huge truncation or bad read.
        # Just return the last two paragraphs as a safe guess.
        chunks = [c.strip() for c in full_text.split("\n\n") if c.strip()]
        return "\n\n".join(chunks[-2:]) if len(chunks) > 1 else full_text

    # We found the suffix at `idx` in the normalized text.
    # This means the instruction ends at `idx + len(suffix)` in `norm_full`.
    end_of_instruction_norm = idx + len(suffix)
    
    # We now need to map this back to the original `full_text`.
    # We will count non-whitespace characters to find the corresponding index in `full_text`.
    target_non_ws_count = len(re.sub(r'\s', '', norm_full[:end_of_instruction_norm]))
    
    current_non_ws_count = 0
    split_index = -1
    
    for i, char in enumerate(full_text):
        if not char.isspace():
            current_non_ws_count += 1
            if current_non_ws_count == target_non_ws_count:
                split_index = i
                break
                
    if split_index != -1:
        extracted = full_text[split_index + 1:].strip()
        return extracted
        
    return full_text
