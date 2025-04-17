from flask import Flask, render_template, request, jsonify, send_file
import os
import json
from datetime import datetime
from dotenv import load_dotenv
from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import HuggingFaceInferenceAPIEmbeddings
from langchain.vectorstores import Chroma
from openai import OpenAI

load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")
OR_TOKEN = os.getenv("OR_TOKEN")

app = Flask(__name__,template_folder='templates')
retriever = None
client = None
chat_history = []
def initialize_chatbot():
    global retriever, client
    pdf_path = "test.pdf"
    loader = PyPDFLoader(pdf_path)
    content = loader.load()
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
        separators=["\n\n", "\n", ".", " ", ""]
    )
    chunks = text_splitter.split_documents(content)
    embeddings = HuggingFaceInferenceAPIEmbeddings(
        api_key=HF_TOKEN,
        model_name="BAAI/bge-base-en-v1.5"
    )
    
    vectorstore = Chroma.from_documents(chunks, embeddings)
    retriever = vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 3, "fetch_k": 5}
    )
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OR_TOKEN,
    )
def generate_response(query):
    global retriever, client
    relevant_docs = retriever.get_relevant_documents(query)
    context_text = "\n\n".join([doc.page_content for doc in relevant_docs])
    prompt = f"""
You are a highly professional AI assistant, and your sole task is to extract exact, relevant, and structured information from the context provided.

CONTEXT:
{context_text}  # (This is where you provide the document content or context)

QUESTION:
{query}  # (This is where the user query goes)

GUIDELINES:
- Provide an answer **only** based on the provided context.
- **Do not add anything extra** that is not explicitly mentioned in the context.
- The answer should be **direct and to the point**, without filler or unnecessary explanations.
- If the information cannot be determined from the context, respond with: 
  "I don't have that information in the resume."
- Do **not** add any conversational tone or unrelated information.

OUTPUT:
"""

    try:
        completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "http://localhost:5000",
                "X-Title": "Resume-Chatbot",
            },
            model="nvidia/llama-3.1-nemotron-nano-8b-v1:free",
            messages=[{"role": "user", "content": prompt}]
        )
        response = completion.choices[0].message.content.strip()
        return response
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

@app.route('/')
def index():
    sample_questions = [
        "What are Kanha's technical skills?",
        "Tell me about Kanha's RAG projects",
        "What is Kanha's academic background?",
        "What leadership positions has Kanha held?"
    ]
    return render_template('index.html',sample_questions=sample_questions)

@app.route('/ask', methods=['POST'])
def ask():
    global chat_history
    
    data = request.json
    user_query = data.get('query', '').strip()
    
    if not user_query:
        return jsonify({'error': 'Please enter a question'}), 400
    chat_history.append({"role": "user", "content": user_query})
    response = generate_response(user_query)
    chat_history.append({"role": "assistant", "content": response})
    
    return jsonify({
        'response': response,
        'timestamp': datetime.now().strftime('%H:%M:%S')
    })

@app.route('/history')
def history():
    global chat_history
    return jsonify(chat_history)

@app.route('/clear_history', methods=['POST'])
def clear_history():
    global chat_history
    chat_history = []
    return jsonify({'status': 'success'})

@app.route('/download_chat')
def download_chat():
    global chat_history
    
    chat_export = {
        "title": "Chat with Kanha Khantaal's Resume",
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "messages": chat_history
    }
    filename = f"resume_chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(chat_export, f, indent=2)
    
    return send_file(filename, as_attachment=True)

if __name__ == '__main__':
    initialize_chatbot()
    app.run(debug=False)