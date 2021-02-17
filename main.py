######################################################################################
# main.py
# Main Flask Controller for Padopia
######################################################################################

import re
import os
import json

from pymongo import MongoClient
from bson.json_util import dumps
from bson.objectid import ObjectId
from werkzeug.exceptions import abort

from google.cloud import translate_v2 as translate
from flask_paginate import Pagination
from flask import Flask, render_template, request

DB_CONNECTION = "mongodb+srv://padopiadbuser:WZHZbvqLq5kf4gDyHkzG@padopiacluster.p0hcr.mongodb.net/<dbname>?retryWrites=true&w=majority"


def get_db_connection():
    connection = MongoClient(DB_CONNECTION)
    db = connection['padopiadata']
    return db


def translate_text(text, property_id):

    """Connections"""
    db = get_db_connection()
    collection_property = db['property']

    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'resonant-forge-294511-25f7c1fc6d0f.json'
    client = translate.Client()

    """Translation"""
    translate_request = client.translate(
        values=text,
        target_language='en',
        format_='html',
    )
    translate_result = translate_request['translatedText']

    """Updating database record"""
    collection_property.update_one(
        {
            '_id': ObjectId(property_id)
        },
        {
            '$set':
                {
                    'property_description': translate_result,
                }
        }
    )

    return translate_result


app = Flask(__name__)


@app.route("/")
def index():
    return render_template('index.html')


@app.route("/search", methods=['GET'])
def search():
    db = get_db_connection()
    collection_property = db['property']
    collection_agencies = db['agencies']

    countries = ['Ireland', 'Spain', 'Bulgaria', 'Malta']
    # out = "<h1 style='color:blue'>Padopia</h1><ul>"
    query = {}
    q = request.args.get('q', '').strip()
    country = request.args.get('country', '').strip()
    query_string = ''
    if q != '':
        query_re = re.compile(q, re.IGNORECASE)
        query['property_address'] = query_re
        query_string += ' matching "' + q + '"'
    if country in countries:
        query['property_website_country'] = country
        query_string += ' in ' + country

    searched_properties = collection_property.find(query)

    per_page = 25
    page = request.args.get('page', type=int, default=1)
    if page < 1:
        page = 1

    offset = (page - 1) * per_page
    count = searched_properties.count()
    properties = searched_properties.skip(offset).limit(per_page)

    search = False  # if query == '' else True
    pagination = Pagination(bs_version=4, page=page, total=count, search=search, record_name='properties',
                            per_page=per_page)

    # out += repr(properties)
    # out += '[[[' + repr(count)

    new_properties = []

    shown_count = 0
    for p in properties:
        p['id'] = str(p['_id'])
        new_properties.append(p)
        shown_count += 1
    #    out += repr(p)
    #    out += '<li><a href="/property/' + str(p['_id']) + '">' + p['property_address'] + '</a></li>'

    # return out
    return render_template('search.html', properties=new_properties, pagination=pagination, query=query_string,
                           search=search, count=count, start=offset + 1, end=offset + shown_count, per_page=per_page)


@app.route("/property/<property_id>")
def property_item(property_id):
    db = get_db_connection()
    collection_property = db['property']
    collection_agencies = db['agencies']

    """Query property"""
    query_property = collection_property.find_one({'_id': ObjectId(property_id)})
    property_object = json.loads(dumps(query_property))

    """Checking if translate exists"""
    try:
        description_check = property_object['property_description']
    except:
        description_check = None

    """Translating description"""
    if description_check is None:
        translated_description = translate_text(property_object['property_description_source'], property_id)
        property_object['property_description'] = translated_description
    else:
        property_object['property_description'] = None

    return render_template('property.html', p=property_object)


if __name__ == "__main__":
    app.run(host='0.0.0.0')

