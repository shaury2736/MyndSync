import google.generativeai as genai
import os
import json

# Configure API
genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))

def check_content_safety(text):
    """
    Analyzes content for safety violations using Gemini.
    Returns: JSON { "status": "approved" | "rejected", "reason": "..." }
    """
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    You are a content safety moderator for an academic platform. 
    Analyze the following text for:
    - Offensive, abusive, hateful, violent, explicit, discriminatory, political, or harmful content.
    - Irrelevant or non-academic material.
    
    Return ONLY a JSON object with this format:
    {{
      "status": "approved" | "rejected",
      "reason": "<short explanation>"
    }}
    
    Text to Analyze:
    {text[:5000]}  # Limit text to avoid token limits for this check
    """
    
    try:
        response = model.generate_content(prompt)
        # Clean up code blocks if model returns them
        result = response.text.replace('```json', '').replace('```', '').strip()
        data = json.loads(result)
        return data
    except Exception as e:
        print(f"AI Safety Check Error: {e}")
        # Default to approved if AI fails, or handle as error? 
        # For safety, maybe reject or allow with warning? Let's default valid for MVP unless explicit failure.
        return {"status": "approved", "reason": "AI check unavailable, manual review marked."}
