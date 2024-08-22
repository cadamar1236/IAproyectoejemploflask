from flask import Flask, render_template, request, jsonify
from exani import generate_questions_exani, check_answer_exani, generate_new_questions_exani
from baccaulareat import generate_solutions_bac, retrieve_documents_bac, extract_relevant_context_bac
from langchain_community.chat_models import ChatDeepInfra
import os
import logging
from elasticsearch import Elasticsearch
from langchain.prompts import ChatPromptTemplate

app = Flask(__name__)

# Configuración de logging
logging.basicConfig(level=logging.INFO)

# Token de API
os.environ["DEEPINFRA_API_TOKEN"] = "gtnKXw1ytDsD7DmCSsv2vwdXSW7IBJ5H"

# Ruta inicial: Página principal para seleccionar el tipo de examen
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Dependiendo de la selección del usuario, se maneja el examen correspondiente
        return redirect('/select_exam')
    return render_template('index.html')

@app.route('/select_exam', methods=['POST'])
def select_exam():
    exam_type = request.form['exam_type']
    # Enviar el tipo de examen a la siguiente plantilla
    return render_template('speciality.html', exam_type=exam_type)

def format_solutions(solutions_text):
    solutions_raw = solutions_text.split("\n\n")
    formatted_solutions = []

    for raw_solution in solutions_raw:
        title_match = re.search(r'^\*\*(.*?)\*\*', raw_solution)
        title = title_match.group(1) if title_match else "Solución"
        text = re.sub(r'^\*\*(.*?)\*\*', '', raw_solution).strip()

        formatted_solutions.append({
            "title": title,
            "text": text,
            "note": None
        })

    return formatted_solutions

@app.route('/generate_exam', methods=['POST'])
def generate_exam():
    exam_type = request.form['exam_type']
    num_items = int(request.form['num_items'])
    chat = ChatDeepInfra(model="meta-llama/Meta-Llama-3-8B-Instruct", max_tokens=4000)

    if exam_type == "exani_ii":
        segmento = request.form['segmento']
        asignatura = request.form['asignatura']
        # Lógica para generar preguntas de EXANI-II
        questions = generate_questions_exani(chat, num_items, segmento, asignatura)
        return render_template('quiz.html', questions=questions)

    elif exam_type == "baccalaureat":
        speciality = request.form['speciality']
        # Lógica para generar soluciones de Baccalauréat
        es = Elasticsearch(
    cloud_id="d6ad8b393b364990a49e2dd896c25d44:dXMtY2VudHJhbDEuZ2NwLmNsb3VkLmVzLmlvJDEwNGY0NzdmMzJjNTQ3MmU4NDY5NmVlYTMwZDI0YzMzJDk2NTU5M2I5NGUxZDRhMjU5MDVlMTc5MmY0YzczZGI4",
    basic_auth=("elastic", "eUqFwSxXebwNHSEH1Bjq1zbM"))
        relevant_docs = retrieve_documents_bac(es, "general_texts", 20, speciality)
        context = extract_relevant_context_bac(relevant_docs)
        solutions = generate_solutions_bac(chat, context, num_items)
        solutions_as_items = [{'question': solution, 'choices': None} for solution in solutions.split('\n\n')]
        return render_template('solutions.html', solutions = solutions)



# Ruta para manejar las solicitudes del chat
@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json['message']
    chat = ChatDeepInfra(model="meta-llama/Meta-Llama-3-8B-Instruct", max_tokens=4000)
    system_text = "Eres un asistente de examen que proporciona respuestas generales a preguntas relacionadas con el examen."
    human_text = user_message
    prompt = ChatPromptTemplate.from_messages([("system", system_text), ("human", human_text)])
    
    response = prompt | chat
    response_msg = response.invoke({})
    response_text = response_msg.content
    
    return jsonify({"response": response_text})

@app.route('/check', methods=['POST'])
@app.route('/check', methods=['POST'])
def check():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No se recibieron datos"}), 400
    
    questions = data.get('questions')
    user_answers = data.get('answers')

    if not questions or not user_answers:
        return jsonify({"error": "Faltan preguntas o respuestas"}), 400

    chat = ChatDeepInfra(model="meta-llama/Meta-Llama-3-8B-Instruct", max_tokens=4000)
    results = []

    for i, question in enumerate(questions):
        user_answer = user_answers.get(f'question_{i + 1}')
        if not user_answer:
            results.append({
                'question': question,
                'selected_option': None,
                'correct': "incorrect",
                'explanation': "No se proporcionó ninguna respuesta"
            })
            continue

        correctness, explanation = check_answer_exani(question, user_answer, chat)
        results.append({
            'question': question,
            'selected_option': user_answer,
            'correct': correctness,
            'explanation': explanation
        })

    return jsonify(results)


if __name__ == '__main__':
    app.run(debug=True)