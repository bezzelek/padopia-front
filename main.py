######################################################################################
# main.py
# Main Flask Controller for Padopia
######################################################################################

import re
import os
import json

from datetime import datetime
from pymongo import MongoClient
from bson.json_util import dumps
from bson.objectid import ObjectId
from werkzeug.exceptions import abort

from currency_converter import CurrencyConverter
from google.cloud import translate_v2 as translate
from flask_paginate import Pagination
from flask import Flask, render_template, request, jsonify


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


def convert_currency(property_id, source_amount, source_currency_symbol, currency_iso, currency_symbol):
    """Converting currency symbol to ISO format"""
    source_currency_iso = currency_symbol_to_iso(source_currency_symbol)

    if source_currency_iso is not None:
        """Converting price"""
        converter = CurrencyConverter()
        convert = converter.convert(int(source_amount), source_currency_iso, currency_iso)
        amount = round(convert)

        """Saving property price"""
        save_property_price(
            property_id, amount, currency_iso, currency_symbol,
            source_amount, source_currency_iso, source_currency_symbol
        )

        result = {
            'eur': {
                'amount': int(amount),
                'currency_iso': str(currency_iso),
                'currency_symbol': str(currency_symbol),
            },
            'source': {
                'amount': int(source_amount),
                'currency_iso': str(source_currency_iso),
                'currency_symbol': str(source_currency_symbol),
            },
            'price_last_update': datetime.utcnow(),
        }

        return result
    else:
        return None


def currency_symbol_to_iso(value):
    currency_to_iso = (
        'EUR' if value == '€'
        else 'USD' if value == '$'
        else 'BGN' if value == 'лв'
        else 'TRY' if value == '₺'
        else None
    )
    return currency_to_iso


def save_property_price(
        property_id, amount, currency_iso, currency_symbol, source_amount, source_currency_iso, source_currency_symbol
):
    """Updating property document"""
    db = get_db_connection()
    collection_property = db['property']

    date_time = datetime.utcnow()

    collection_property.update_one(
        {
            '_id': ObjectId(property_id)
        },
        {
            '$set':
                {
                    'property_price.eur.amount': int(amount),
                    'property_price.eur.currency_iso': str(currency_iso),
                    'property_price.eur.currency_symbol': str(currency_symbol),
                    'property_price.source.amount': int(source_amount),
                    'property_price.source.currency_iso': str(source_currency_iso),
                    'property_price.source.currency_symbol': str(source_currency_symbol),
                    'property_price.price_last_update': date_time,
                }
        }
    )


app = Flask(__name__)


@app.route("/")
def index():
    return render_template('index.html')


@app.route("/search", methods=['GET'])
def search():
    db = get_db_connection()
    collection_property = db['property']

    """Requested information"""
    q = request.args.get('country')

    """Query information"""
    if q is None:
        q = ''

    searched_properties = collection_property.find(
        {
            'property_address': re.compile(q, re.IGNORECASE),
         }
    ).sort('date_time', -1)

    """Current search page"""
    current_page = request.args.get('page', type=int, default=1)
    if current_page < 1:
        current_page = 1

    """Properties for current search page"""
    per_page = 25
    offset = (current_page - 1) * per_page
    current_page_properties = searched_properties.sort('date_time', -1).skip(offset).limit(per_page)

    """Pagination"""
    search_check = False  # if query == '' else True
    queried_properties_count = searched_properties.count()
    pagination = Pagination(
        bs_version=4, page=current_page, total=queried_properties_count,
        search=search_check, record_name='properties', per_page=per_page
    )

    """Dumping properties"""
    properties_result = json.loads(dumps(current_page_properties))
    properties_count = len(properties_result)

    return render_template(
        'search.html', properties=properties_result, pagination=pagination, query=q, search=search_check,
        count=queried_properties_count, start=offset + 1, end=offset + properties_count, per_page=per_page
    )


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

    """Converting currency"""
    currency_symbol = property_object['property_cost_currency']
    property_cost_amount = property_object['property_cost_integer']

    try:
        currency_check = property_object['property_price']['source']['currency_iso']
    except:
        currency_check = None

    if currency_check != 'EUR':
        property_price = convert_currency(property_id, property_cost_amount, currency_symbol, 'EUR', '€')
        property_object['property_price'] = property_price
    elif currency_check is None:
        property_price = convert_currency(property_id, property_cost_amount, currency_symbol, 'EUR', '€')
        property_object['property_price'] = property_price

    """Query agency if exist"""
    try:
        query_agency = collection_agencies.find_one({'agency_name': property_object['property_agency']})
        agency_object = json.loads(dumps(query_agency))
    except:
        agency_object = None

    return render_template('property.html', p=property_object, a=agency_object)


@app.route("/agency/<agency_id>")
def agency_item(agency_id):
    db = get_db_connection()
    collection_property = db['test_property']
    collection_agencies = db['test_agencies']

    query_agency = collection_agencies.find_one({'_id': ObjectId(agency_id)})
    agency_object = json.loads(dumps(query_agency))
    query_property = collection_property.find({'property_agency': agency_object['agency_name']}).sort('date_time', -1)
    property_object = json.loads(dumps(query_property))

    result = json.dumps(
        {
            'property_info': property_object,
            'agency_info': agency_object
        }
    )

    return result


@app.route("/autocomplete", methods=["GET", "POST"])
def autocomplete():
    db = get_db_connection()
    collection_property = db['property']

    """Query db for autocomplete"""
    autocomplete_query = request.form.get('text')

    autocomplete_locations = []
    if autocomplete_query is not None:
        autocomplete_result_cursor = collection_property.aggregate([
            {
                '$search': {
                    'index': 'default_one',
                    'text': {
                        'query': autocomplete_query,
                        'path': [
                            'property_address_detailed.country',
                        ],
                        "fuzzy": {
                            "maxEdits": 2,
                        },
                    }
                }
            },

            # Return only 'property_address_detailed.country' field value and groups duplications
            {
                '$group':
                    {
                        '_id': '$property_address_detailed.country',
                    }
            },

            # Return only 5 values
            {
                '$limit': 5
            }
        ])

        """Dumping autocomplete matches"""
        autocomplete_results = json.loads(dumps(autocomplete_result_cursor))

        """Extracting addresses from dump"""
        for item in autocomplete_results:
            element = item['_id']
            unit = {'address': element}
            autocomplete_locations.append(unit)

    result = jsonify(autocomplete_locations)

    return result


if __name__ == "__main__":
    app.run(host='0.0.0.0')
