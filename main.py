######################################################################################
# main.py
# Main Flask Controller for Padopia
######################################################################################

from flask import Flask, render_template, request, url_for, flash, redirect
from werkzeug.exceptions import abort
from pymongo import MongoClient
from bson.objectid import ObjectId
from flask_paginate import Pagination, get_page_parameter
import re

DB_CONNECTION = "mongodb+srv://padopiadbuser:WZHZbvqLq5kf4gDyHkzG@padopiacluster.p0hcr.mongodb.net/<dbname>?retryWrites=true&w=majority"

def get_db_connection():
    connection = MongoClient(DB_CONNECTION)
    db = connection['padopiadata']
    return db


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
    #out = "<h1 style='color:blue'>Padopia</h1><ul>"
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

    offset = (page-1) * per_page
    count = searched_properties.count()
    properties = searched_properties.skip(offset).limit(per_page)

    search = False # if query == '' else True
    pagination = Pagination(bs_version=4, page=page, total=count, search=search, record_name='properties', per_page=per_page)

    #out += repr(properties)
    #out += '[[[' + repr(count)

    new_properties = []

    shown_count = 0
    for p in properties:
        p['id'] = str(p['_id'])
        new_properties.append(p)
        shown_count += 1
    #    out += repr(p)
    #    out += '<li><a href="/property/' + str(p['_id']) + '">' + p['property_address'] + '</a></li>'

    #return out
    return render_template('search.html', properties=new_properties, pagination=pagination, query=query_string, search=search, count=count, start=offset+1, end=offset+shown_count, per_page=per_page)

@app.route("/property/<id>")
def property(id):
    db = get_db_connection()
    collection_property = db['property']
    collection_agencies = db['agencies']

    p = collection_property.find_one({'_id': ObjectId(id)})

    #out = "<h1 style='color:blue'>Padopia</h1>"
    #out += '<h2 style="color:grey">' + p['property_address'] + '</h2>'
    #out += '<p>' + p['property_description'] + '</p>'
    # return out

    return render_template('property.html', p=p)

if __name__ == "__main__":
    app.run(host='0.0.0.0')

