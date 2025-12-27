import google.generativeai as genai
import os
import json

genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))

def generate_questions(text, mode, marks=None, num_questions=1):
    """
    Generates multiple exam-oriented questions with fallbacks.
    """
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        return {"questions": []}
        
    genai.configure(api_key=api_key)
    
    models_to_try = [
        'models/gemini-2.5-flash',
        'models/gemini-1.5-flash',
        'models/gemini-pro',
        'models/gemma-3-27b-it'
    ]
    
    for model_name in models_to_try:
        try:
            print(f"DEBUG: Trying model {model_name} for {num_questions} questions...")
            model = genai.GenerativeModel(model_name)
            
            prompt = f"""
            Generate EXACTLY {num_questions} {mode} questions based on the text.
            Marks per question: {marks if marks else 'N/A'}
            
            FOR SUBJECTIVE: You MUST include a concise answer for each question.
            FOR OBJECTIVE: Include 4 options and the correct answer.
            
            Return ONLY JSON:
            {{
              "questions": [
                {{
                  "type": "{mode}",
                  "marks": {marks if marks else 'null'},
                  "question": "<text>",
                  "options": ["A", "B", "C", "D"] (null for subjective),
                  "answer": "<correct answer or subjective explanation>"
                }}
              ]
            }}
            
            Text:
            {text[:15000]}
            """
            
            response = model.generate_content(prompt)
            result = response.text.strip()
            
            if '```json' in result:
                result = result.split('```json')[1].split('```')[0].strip()
            elif '```' in result:
                result = result.split('```')[1].split('```')[0].strip()
                
            return json.loads(result)
        except Exception as e:
            err_msg = str(e)
            print(f"DEBUG: Model {model_name} failed: {err_msg}")
            if "429" in err_msg:
                return {"questions": [{"question": "AI Limit Reached: Please wait 1 minute.", "type": "error", "answer": ""}]}
            continue
            
    return {"questions": []}
