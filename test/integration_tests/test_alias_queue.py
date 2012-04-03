import os, unittest, time
from nose.tools import nottest, assert_equals

from totalimpact.backend import TotalImpactBackend, ProviderMetricsThread, ProvidersAliasThread, StoppableThread, QueueConsumer
from totalimpact.config import Configuration
from totalimpact.providers.provider import Provider, ProviderFactory
from totalimpact.queue import Queue, AliasQueue, MetricsQueue
from totalimpact.util import slow
from totalimpact import dao, api
from totalimpact.tilogging import logging

TEST_DRYAD_DOI = "10.5061/dryad.7898"

class TestAliasQueue(unittest.TestCase):
        
    def test_alias_queue(self):
        config = Configuration() 
        providers = ProviderFactory.get_providers(config)

        # setup the database
        mydao = dao.Dao(config)
        mydao.create_new_db_and_connect('alias_queue_test')
        
        # put an item in there
        app = api.app
        app.testing = True
        app.config["DB_NAME"] = "alias_queue_test"
        client = app.test_client()

        response = client.post('/item/DOI/' + TEST_DRYAD_DOI.replace("/", "%25"))
        tiid = response.data
        print tiid
        print response
        assert False 

        # now get it back out
        tiid = tiid.replace('"', '')
        response = client.get('/item/' + tiid)
        print response
        print response.data
        assert_equals(response.status_code, 200)
        
        #assert_equals(json.loads(response.data).keys(), [u'created', u'last_requested', u'metrics', u'last_modified', u'biblio', u'id', u'aliases'])
        #assert_equals(response.mimetype, "application/json")


        '''
        my_alias_queue = AliasQueue(mydao)
        assert isinstance(my_alias_queue.queue, list)

        watcher = TotalImpactBackend(config)
        assert len(my_alias_queue.queue) > 1
        first = my_alias_queue.first()
        '''
        

        ### FIXME Need to make first return an Item so that can pass to save_and_unqueue

        #assert len(first["_id"]) > 1
        ## FIXME my_alias_queue.save_and_unqueue(first)

        # TODO: once queues actually work, this should succeed
        ## FIXME assert_equals(len(my_alias_queue.queue), 0)



