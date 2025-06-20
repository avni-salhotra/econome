# test_gemini.py
import google.generativeai as genai
import os

# === Step 1: Auth setup ===
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "gemini-credentials.json"

# === Step 2: Gemini model configuration ===
genai.configure()
model = genai.GenerativeModel("gemini-1.5-pro")

# === Step 3: Simple test prompt ===
prompt = "Summarize this: John will send the proposal by Friday afternoon."

# === Step 4: Run and print response ===
response = model.generate_content(prompt)
print("\n🔮 Gemini response:\n")
print(response.text)
