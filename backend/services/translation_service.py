from deep_translator import GoogleTranslator
import time

def translate_text(text: str, target_lang: str = 'uz'):
    """
    Translates a single string to the target language.
    """
    try:
        translator = GoogleTranslator(source='auto', target=target_lang)
        return translator.translate(text)
    except Exception as e:
        print(f"Error translating text: {e}")
        return text # Return original on failure

def translate_segments(segments: list, target_lang: str = 'uz'):
    """
    Iterates through Whisper segments and translates the 'text' field.
    Returns a new list of segments with an added 'translated_text' field.
    """
    translated_segments = []
    
    print(f"Translating {len(segments)} segments to {target_lang}...")
    
    # Initialize translator once
    translator = GoogleTranslator(source='auto', target=target_lang)

    for segment in segments:
        new_segment = segment.copy()
        original_text = segment.get('text', '')
        
        if original_text.strip():
            try:
                # deep_translator handles requests well, but we catch errors just in case
                translated = translator.translate(original_text)
                new_segment['translated_text'] = translated
            except Exception as e:
                print(f"Error translating segment {segment.get('id')}: {e}")
                new_segment['translated_text'] = original_text
        else:
            new_segment['translated_text'] = ""
            
        translated_segments.append(new_segment)
    
    print("Translation completed.")
    return translated_segments
