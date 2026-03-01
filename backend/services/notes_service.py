import os
import google.generativeai as genai
import json

def generate_meeting_notes(text: str, language: str = "uz"):
    # API Keyni tekshirish
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return {
            "error": True,
            "message": "API kalit topilmadi. Iltimos, sozlamalarda Google API Key ni kiriting."
        }

    try:
        genai.configure(api_key=api_key)
        # Updated to available model
        model = genai.GenerativeModel('gemini-flash-latest')

        prompt = f"""
        Act as a professional AI assistant. Analyze the following transcript and generate concise "Meeting Notes" similar to Notion AI.
        
        Output Language: {language}
        Format: JSON
        
        Structure:
        {{
            "summary": "Short summary of the content (2-3 sentences)",
            "key_points": ["List of key takeaways..."],
            "action_items": ["List of tasks or action items mentioned (if any)..."],
            "sentiment": "Overall tone (Positive/Neutral/Serious/Fun)"
        }}

        Transcript:
        {text[:10000]} 
        """
        # Limit text length to avoid token limits if necessary, though 1.5 flash has large context.
        # Removing limit for now as 1.5 Flash handles 1M tokens.
        
        response = model.generate_content(prompt)
        
        # Clean markdown code blocks if present
        cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
        
        return json.loads(cleaned_text)

    except Exception as e:
        return {
            "error": True, 
            "message": f"AI xatosi: {str(e)}"
        }
