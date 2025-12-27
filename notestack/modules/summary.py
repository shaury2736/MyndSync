import google.generativeai as genai
import os
import json

genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))

def generate_summary(text):
    """
    Generates academic summary with fallbacks.
    Returns: JSON { "short_summary": "...", "detailed_summary": ["...", "..."] }
    """
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        return {"short_summary": "API Key missing.", "detailed_summary": []}
        
    genai.configure(api_key=api_key)
    
    # Try multiple models - prioritized for Free Tier
    # Try multiple models - verified models/gemini-2.5-flash works for this API key
    models_to_try = [
        'models/gemini-2.5-flash',
        'models/gemini-1.5-flash',
        'models/gemini-pro',
        'models/gemma-3-27b-it'
    ]
    
    last_error = ""
    for model_name in models_to_try:
        try:
            print(f"DEBUG: Trying model {model_name}...")
            model = genai.GenerativeModel(model_name)
            
            prompt = f"""
            Summarize the following academic notes. Return ONLY JSON.
            {{
              "short_summary": "3-5 lines",
              "detailed_summary": ["bullet", "point"]
            }}
            
            Text:
            {text[:15000]}
            """
            
            response = model.generate_content(prompt)
            result = response.text.strip()
            
            # Extract JSON from markdown if necessary
            if '```json' in result:
                result = result.split('```json')[1].split('```')[0].strip()
            elif '```' in result:
                result = result.split('```')[1].split('```')[0].strip()
            
            return json.loads(result)
        except Exception as e:
            err_msg = str(e)
            print(f"DEBUG: Model {model_name} failed: {err_msg}")
            if "429" in err_msg:
                return {"short_summary": "AI Limit Reached: You've hit Google's free tier limit. Please wait 1 minute before trying again.", "detailed_summary": []}
            last_error = err_msg
            continue
            
    return {"short_summary": f"Generation failed. Error: {last_error}", "detailed_summary": []}
