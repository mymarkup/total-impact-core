import time, datetime
import threading
import simplejson
import copy
from totalimpact import default_settings
from totalimpact.models import Item, ItemFactory
from totalimpact.pidsupport import StoppableThread, ctxfilter
from totalimpact.providers.provider import ProviderFactory
import default_settings

from totalimpact.tilogging import logging
log = logging.getLogger("queue")


# some data useful for testing
# d = {"doi" : ["10.1371/journal.pcbi.1000361", "10.1016/j.meegid.2011.02.004"], "url" : ["http://cottagelabs.com"]}


class QueueMonitor(StoppableThread):
    """ Worker to watch couch for newly requested items, and place them
        onto the aliases queue. 
    """

    def __init__(self, dao):
        self.dao = dao
        StoppableThread.__init__(self)

    def run(self, runonce=False):
        """ runonce is for the test suite """
        ctxfilter.threadInit()
        ctxfilter.local.backend['thread'] = 'QueueMonitor'

        while not self.stopped():
            viewname = 'queues/requested'
            rows = self.dao.view(viewname)

            for row in rows["rows"]:
                item_doc = copy.deepcopy(row["value"])

                item = ItemFactory.get_item_object_from_item_doc(self.dao, 
                        item_doc)

                tiid = item.id
                ctxfilter.local.backend['item'] = tiid
                log.info("%20s detected on request queue: item %s" 
                    % ("QueueMonitor", tiid))
                # In case clocks are out between processes, use min to ensure queued >= requested
                item.last_queued = max(item.last_requested, datetime.datetime.now().isoformat()) 
                item_doc["last_queued"] = item.last_queued

                # now save back the updated last_queued information
                # do this before putting on queue, so that no one has changed it.
                log.info("%20s UPDATING last_queued date in db: item %s" 
                    % ("QueueMonitor", tiid))

                item_doc["id"] = item.id
                self.dao.save(item_doc)

                # Now add the item to the in-memory queue
                Queue.init_queue("aliases")
                Queue.enqueue("aliases", item)


                #item.save()
                log.info("%20s saving item %s to update last_queued information" 
                    % ("QueueMonitor", tiid))

            if runonce:
                break
            self._interruptable_sleep(0.5)
    
class Queue():
    # This is a FIFO queue, add new item ids to the end of this list
    # to queue, remove from the head
    queued_items = {}
    queue_lock = threading.Lock()
    

    def __init__(self, queue_name):
        self.queue_name = queue_name
        self.init_queue(queue_name)

    @classmethod
    def clear(cls):
        """ This is only used from the test suite, normally not needed """
        for queue_name in cls.queued_items.keys():
            cls.queued_items[queue_name] = []

    @classmethod
    def init_queue(cls, queue_name):
        if not cls.queued_items.has_key(queue_name):
            cls.queued_items[queue_name] = []

    @classmethod
    def queued_items_ids(cls, queue_name):
        return ([item.id for item in cls.queued_items[queue_name]])

    @classmethod
    def enqueue(cls, queue_name, item):
        log.info("%20s enqueuing item %s"
            % ("Queue " + queue_name, item.id))

        # Synchronised section
        cls.queue_lock.acquire()
        # Add to the end of the queue
        cls.queued_items[queue_name].append(copy.deepcopy(item))
        cls.queue_lock.release()

    def dequeue(self):
        # Synchronised section
        item = None
        self.queue_lock.acquire()
        if len(self.queued_items[self.queue_name]) > 0:
            # Take from the head of the queue
            item = copy.deepcopy(self.queued_items[self.queue_name][0])
            log.info("%20s dequeuing item %s" 
                % ("Queue " + self.queue_name, item.id))
            del self.queued_items[self.queue_name][0]
        self.queue_lock.release()
        return item

    @classmethod
    def add_to_metrics_queues(self, item):
        # Add the item to the metrics queue
        log.info("%20s adding item %s to all metrics queues" 
            % ("Queue", item.id))

        providers_config = default_settings.PROVIDERS
        providers = ProviderFactory.get_providers(providers_config)
        for provider in providers:
            if provider.provides_metrics:
                Queue.enqueue(provider.provider_name, item)

    @property
    def provider(self):
        return self.queue_name



