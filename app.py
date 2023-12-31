"""Module principal """

import time
import json
import openai
import certifi
import os

from flask import Flask, request, jsonify
from pymongo import MongoClient, errors
from pymongo.server_api import ServerApi

from flask_cors import CORS
from jikanpy import Jikan
import config


app = Flask(__name__)
CORS(app)
jikan = Jikan()
openai.api_key = os.getenv("API_KEY")
# print(os.getenv("API_KEY"))

# client = MongoClient("mongodb://localhost:27017")
uri = os.getenv("MONGO_CONNECTION")
# print(uri)

client = MongoClient(uri, server_api=ServerApi("1"), tlsCAFile=certifi.where())

db = client["seriesSensei"]
collection = db["series"]


@app.route("/series/getall", methods=["GET"])
def get_all_series():
    """Function return all series"""
    series = collection.find()
    response = {}
    for series_object in series:
        for serie in series_object.keys():
            if serie != "_id":
                response[serie] = {
                    "sinopsis": series_object[serie].get("sinopsis", ""),
                    "genres": series_object[serie].get("genres", ""),
                    "url": series_object[serie].get("url", ""),
                    "genres_real": series_object[serie].get("genres_real", ""),
                    "duration": series_object[serie].get("duration", ""),
                    "episodes": series_object[serie].get("episodes", ""),
                    "score": series_object[serie].get("score", ""),
                    "synopsis": series_object[serie].get("synopsis", ""),
                    "year": series_object[serie].get("year", ""),
                }
    return response


@app.route("/series/extra-info", methods=["POST"])
def set_extra_info():
    """Function for set extra data"""
    series = collection.find()
    mongo_series = {}

    for series_object in series:
        mongo_series = series_object

    for serie in mongo_series.keys():
        if serie != "_id":
            if (
                "url" in mongo_series[serie]
                and "duration" in mongo_series[serie]
                and "episodes" in mongo_series[serie]
                and "genres_real" in mongo_series[serie]
                and "score" in mongo_series[serie]
                and "synopsis" in mongo_series[serie]
            ):
                continue
            print(f"search -> {serie}")
            time.sleep(max(1 / 60, 1 / 3))  # Sleep for the max of 1/60 and 1/3 seconds

            search_result = jikan.search("anime", serie)
            print(search_result["data"][0]["images"]["jpg"]["image_url"])
            url = search_result["data"][0]["images"]["jpg"]["image_url"]
            duration = search_result["data"][0]["duration"]
            episodes = search_result["data"][0]["episodes"]
            genres_real = search_result["data"][0]["genres"]
            score = search_result["data"][0]["score"]
            synopsis = search_result["data"][0]["synopsis"]

            collection.update_one(
                {
                    f"{serie}": {"$exists": True},
                },
                {
                    "$set": {
                        f"{serie}.url": url,
                        f"{serie}.duration": duration,
                        f"{serie}.episodes": episodes,
                        f"{serie}.genres_real": genres_real,
                        f"{serie}.score": score,
                        f"{serie}.synopsis": synopsis,
                    }
                },
            )
    return {}


@app.route("/series/set_all_data_anime", methods=["POST"])
def set_all_data_anime():
    """Function for set extra data"""
    serie = request.args.get("serie", default=None)
    print(f"serie: {serie}")

    doc = collection.find_one({serie: {"$exists": True}})

    # # JIKAN DATA
    search_result = jikan.search("anime", serie)
    index = None
    for i, item in enumerate(search_result["data"]):
        if item.get("type") == "TV":
            index = i
            break
    url = search_result["data"][index]["images"]["jpg"]["image_url"]
    duration = search_result["data"][index]["duration"]
    episodes = search_result["data"][index]["episodes"]
    genres_real = search_result["data"][index]["genres"]
    score = search_result["data"][index]["score"]
    synopsis = search_result["data"][index]["synopsis"]
    year = search_result["data"][index]["year"]

    # CHATGPT
    prompt = f"""
    Eres un experto crítico de anime. Conociendo el "Análisis de la historia y los personajes" y una "sinopsis" del anime de {serie}.

    Ten en cuenta la siguiente lista de generos de anime que te muestro entre triple comilla.
    \"\"\"
    {config.GENRES}
    \"\"\"

    usando los resultados que obtuviste de "Análisis de la historia y los personajes" y una "sinopsis"  Proporciona una descomposición de los géneros (lista de generos) del anime  {serie} y asigna porcentajes para cada género en función de su relevancia.
    Debes presentar todos los generos de la "lista de generos".

    Como respuesta debes entregar un JSON que cumpla con el siguiente formato que te muestro dentro de los triple comilla:

    \"\"\"
    {config.FORMAT}
    \"\"\"

    retorna solamente un objeto vacío si es que vas a responder algo genérico
    """
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000,
    )

    print(response.choices[0].message["content"])
    print(response.usage)

    response_content = response.choices[0].message["content"]
    response_json = json.loads(response_content)  # Convierte la cadena a un objeto JSON

    data = {
        "url": url,
        "duration": duration,
        "episodes": episodes,
        "genres_real": genres_real,
        "score": score,
        "synopsis": synopsis,
        "genres": response_json,
        "year": year,
    }
    if doc is None:
        new_doc = {serie: data}
        # Insertar el nuevo documento en la colección
        collection.insert_one(new_doc)
    else:
        collection.update_one(
            {
                f"{serie}": {"$exists": True},
            },
            {
                "$set": {
                    f"{serie}.url": url,
                    f"{serie}.duration": duration,
                    f"{serie}.episodes": episodes,
                    f"{serie}.genres_real": genres_real,
                    f"{serie}.score": score,
                    f"{serie}.synopsis": synopsis,
                    f"{serie}.genres": response_json,
                    f"{serie}.year": year,
                }
            },
        )

    return {}


@app.route("/series/get-chatgpt-data", methods=["GET"])
def get_chatgpt_data():
    """Function for get data from chatgpt"""

    anime = request.args.get("anime", default=None)
    if not anime:
        return jsonify({"error": "Parámetro 'anime' no proporcionado"}), 400

    response = {}
    anime = request.args.get("anime", default=None)

    prompt = f"""
    Eres un experto crítico de anime. Conociendo el "Análisis de la historia y los personajes" y una "sinopsis" del anime de {anime}.

    Ten en cuenta la siguiente lista de generos de anime que te muestro entre triple comilla.
    \"\"\"
    {config.GENRES}
    \"\"\"

    usando los resultados que obtuviste de "Análisis de la historia y los personajes" y una "sinopsis"  Proporciona una descomposición de los géneros (lista de generos) del anime  {anime} y asigna porcentajes para cada género en función de su relevancia.
    Debes presentar todos los generos de la "lista de generos".

    Como respuesta debes entregar un JSON que cumpla con el siguiente formato que te muestro dentro de los triple comilla:

    \"\"\"
    {config.FORMAT}
    \"\"\"

    retorna solamente un objeto vacío si es que vas a responder algo genérico
    """
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000,
    )

    print(response.choices[0].message["content"])
    print(response.usage)

    response_content = response.choices[0].message["content"]
    response_json = json.loads(response_content)  # Convierte la cadena a un objeto JSON

    series = collection.find()
    mongo_series = {}

    for series_object in series:
        mongo_series = series_object

    for serie in mongo_series.keys():
        if serie != anime:
            continue
        print(f"search -> {serie}")
        try:
            collection.update_one(
                {
                    f"{anime}": {"$exists": True},
                },
                {"$set": {f"{anime}.genres": response_json}},
            )
        except errors.PyMongoError as mongo_exception:
            return (
                jsonify(
                    {"error": f"Error al actualizar MongoDB: {str(mongo_exception)}"}
                ),
                500,
            )
    return jsonify({"message": "Actualización exitosa"}), 200


@app.route("/series/delete-serie", methods=["DELETE"])
def delete_serie():
    serie = request.args.get(
        "serie"
    )  # Se recibe el nombre de la serie a eliminar como parámetro en la URL
    if serie:
        collection.delete_one({f"{serie}": {"$exists": True}})
        # collection.update_one({}, {"$unset": {f"{serie}": 1}})
        return {"message": f"Serie '{serie}' eliminada."}, 200
    else:
        return {"message": "No se proporcionó el nombre de la serie."}, 400


@app.route("/series/get_jikan_anime", methods=["GET"])
def get_jikan_anime():
    """Function for set extra data"""
    serie = request.args.get("serie", default=None)
    print(f"serie: {serie}")

    # # JIKAN DATA
    search_result = jikan.search("anime", serie)
    index = None
    for i, item in enumerate(search_result["data"]):
        if item.get("type") == "TV":
            index = i
            break

    return search_result["data"][index]
