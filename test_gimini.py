import google.generativeai as genai

GEMINI_API_KEY = "AIzaSyAs1JV2C1hVXZbQAyrCPi3PMY2NNIAWylA"
genai.configure(api_key=GEMINI_API_KEY)

try:
    model = genai.GenerativeModel('gemini-flash-latest')
    prompt = "Analyse ce commentaire de transport public: \"je n'aime plus ce voyage\""
    response = model.generate_content(prompt)
    print("Success:")
    print(response.text)
except Exception as e:
    print(f"Error: {e}")