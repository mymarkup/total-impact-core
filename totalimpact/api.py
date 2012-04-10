from flask import Flask, jsonify, json, request, redirect, abort, make_response
from flask import render_template, flash
import os, json, time

from totalimpact.config import Configuration
from totalimpact import dao
from totalimpact.models import Item, Collection
from totalimpact.providers.provider import ProviderFactory, ProviderConfigurationError
from totalimpact.tilogging import logging

# set up logging
logger = logging.getLogger(__name__)

# setup the app
app = Flask(__name__)
config = Configuration()
providers = ProviderFactory.get_providers(config)
mydao = dao.Dao(config)


# adding a simple route to confirm working API
@app.route('/')
def hello():
    msg = {
        "hello": "world",
        "message": "Congratulations! You have found the Total Impact API.",
        "moreinfo": "http://total-impact.tumblr.com/",
        "version": config.version
    }
    resp = make_response( json.dumps(msg, sort_keys=True, indent=4), 200)        
    resp.mimetype = "application/json"
    return resp


'''
GET /tiid/:namespace/:id
404 if not found because not created yet
303 else list of tiids
'''
@app.route('/tiid/<ns>/<path:nid>', methods=['GET'])
def tiid(ns, nid):
    # Nothing in the database, so return error for everything now
    # FIXME needs to look things up
    abort(404)


'''
POST /item/:namespace/:id
201 location: {tiid}
500?  if fails to create
example /item/PMID/234234232
'''
@app.route('/item/<namespace>/<path:nid>', methods=['POST'])
def item_namespace_post(namespace, nid):
    now = time.time()
    item = Item(mydao)
    item.aliases = {}
    item.aliases[namespace] = nid
    item.created = now
    item.last_modified = 0

    ## FIXME
    ## Should look up this namespace and id and see if we already have a tiid
    ## If so, return its tiid with a 200.
    # right now this makes a new item every time, creating many dups

    # FIXME pull this from Aliases somehow?
    # check to make sure we know this namespace
    #known_namespace = namespace in Aliases().get_valid_namespaces() #implement
    known_namespaces = ["doi"]  # hack in the meantime
    if not namespace in known_namespaces:
        abort(501) # "Not Implemented"

    # otherwise, save the item
    item.save() 
    response_code = 201 # Created

    tiid = item.id

    if not tiid:
        abort(500)
    resp = make_response(json.dumps(tiid), response_code)        
    resp.mimetype = "application/json"
    return resp


'''
GET /item/:tiid
404 if no tiid else structured item

GET /items/:tiid,:tiid,...
returns a json list of item objects (100 max)
'''
@app.route('/item/<tiids>', methods=['GET'])
@app.route('/items/<tiids>', methods=['GET'])
def items(tiids):
    items = []
    for index,tiid in enumerate(tiids.split(',')):
        if index > 99: break    # weak
        try:
            item = Item(mydao, id=tiid)
            item.load()
            items.append( item.as_dict() )
        except LookupError:
            # TODO: is it worth setting this blank? or do nothing?
            # if do nothing, returned list will not match supplied list
            items.append( {} )

    if len(items) == 1 and not request.path.startswith('/items/') :
        items = items[0]

    if items:
        resp = make_response( json.dumps(items, sort_keys=True, indent=4) )
        resp.mimetype = "application/json"
        return resp
    else:
        abort(404)


'''
GET /provider/:provider/memberitems?query=:querystring[&type=:type]
returns member ids associated with the group in a json list of (key, value) pairs like [(namespace1, id1), (namespace2, id2)] 
of type :type (when this needs disambiguating)
if > 100 memberitems, return the first 100 with a response code that indicates the list has been truncated
errors:
over query limit
provider error with string value containing error returned by provider
ti errors
examples:
/provider/github/memberitems?query=jasonpriem&type=github_user
/provider/github/memberitems?query=bioperl&type=github_org
/provider/dryad/memberitems?query=Otto%2C%20Sarah%20P.&type=dryad_author

POST /provider/:provider/aliases
alias object as cargo, may or may not have a tiid in it
returns alias object 
errors:
over query limit
provider error
ti errors

POST /provider/:provider
alias object as cargo, may or may not have tiid in it
returns dictionary with metrics object and biblio object
'''

# routes for providers (TI apps to get metrics from remote sources)
# external APIs should go to /item routes
# should return list of member ID {namespace:id} k/v pairs
# if > 100 memberitems, return 100 and response code indicates truncated
@app.route('/provider/<pid>/memberitems', methods=['GET'])
def provider_memberitems(pid):
    query = request.values.get('query','')
    qtype = request.values.get('type','')

    logger.debug("In provider_memberitems with " + query + " " + qtype)
    
    for prov in providers:
        if prov.id == pid:
            provider = prov
            break

    logger.debug("provider: " + prov.id)

    memberitems = provider.member_items(query, qtype)
    
    resp = make_response( json.dumps(memberitems, sort_keys=True, indent=4), 200 )
    resp.mimetype = "application/json"
    return resp

# For internal use only.  Useful for testing before end-to-end working
# Example: http://127.0.0.1:5000/provider/Dryad/aliases/10.5061%2Fdryad.7898
@app.route('/provider/<pid>/aliases/<id>', methods=['GET'] )
def provider_aliases(pid,id):

    for prov in providers:
        if prov.id == pid:
            provider = prov
            break

    aliases = provider.get_aliases_for_id(id.replace("%", "/"))

    resp = make_response( json.dumps(aliases, sort_keys=True, indent=4) )
    resp.mimetype = "application/json"
    return resp

# For internal use only.  Useful for testing before end-to-end working
# Example: http://127.0.0.1:5000/provider/Dryad/metrics/10.5061%2Fdryad.7898
@app.route('/provider/<pid>/metrics/<id>', methods=['GET'] )
def metric_snaps(pid,id):

    for prov in providers:
        if prov.id == pid:
            provider = prov
            break

    metrics = provider.get_metrics_for_id(id.replace("%", "/"))

    resp = make_response( json.dumps(metrics.data, sort_keys=True, indent=4) )
    resp.mimetype = "application/json"
    return resp

# For internal use only.  Useful for testing before end-to-end working
# Example: http://127.0.0.1:5000/provider/Dryad/biblio/10.5061%2Fdryad.7898
@app.route('/provider/<pid>/biblio/<id>', methods=['GET'] )
def provider_biblio(pid,id):

    for prov in providers:
        if prov.id == pid:
            provider = prov
            break

    biblio = provider.get_biblio_for_id(id.replace("%", "/"))

    resp = make_response( json.dumps(biblio.data, sort_keys=True, indent=4) )
    resp.mimetype = "application/json"
    return resp


'''
GET /collection/:collection_ID
returns a collection object 

POST /collection
creates new collection
post payload is a list of item IDs as [namespace, id]
returns collection_id

PUT /collection/:collection
payload is a collection object
overwrites whatever was there before.

DELETE /collection/:collection
returns success/failure
'''
@app.route('/collection', methods = ['POST'])
@app.route('/collection/<cid>', methods = ['GET','POST','PUT','DELETE'])
def collection(cid=''):
    try:
        coll = Collection(mydao, id=cid)
        coll.load()
    except:
        coll = False
    
    if request.method == "POST":
        if coll:
            abort(405)
        else:
            coll = Collection(mydao, seed = request.json )
            coll.save()

    elif request.method == "PUT" and cid:
        coll = Collection(mydao, seed = request.json )
        coll.save()

    elif request.method == "DELETE":
        if coll:
            coll.delete()
        abort(404)

    try:
        resp = make_response( json.dumps( coll.as_dict() ) )
        resp.mimetype = "application/json"
        return resp
    except:
        abort(404)


if __name__ == "__main__":

    try:
        if not mydao.db_exists(config.DB_NAME):
            mydao.create_db(config.DB_NAME)
        mydao.connect_db(config.DB_NAME)
    except LookupError:
        print "CANNOT CONNECT TO DATABASE, maybe doesn't exist?"
        raise LookupError

    # run it
    app.run(host='0.0.0.0', debug=True)



