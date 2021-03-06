from totalimpact.providers import provider
from totalimpact.providers.provider import Provider, ProviderContentMalformedError
import hashlib
import simplejson

import logging
logger = logging.getLogger('ti.providers.delicious')

class Delicious(Provider):  

    example_id = ("url", "http://total-impact.org")
    metrics_url_template = "http://feeds.delicious.com/v2/json/url/%s?count=100"
    provenance_url_template = "http://www.delicious.com/url/%s"
    url = "http://www.delicious.com"
    descr = "Online social bookmarking service"
    static_meta_dict = {
        "bookmarks": {
            "display_name": "bookmarks",
            "provider": "Delicious",
            "provider_url": "http://www.delicious.com/",
            "description": "The number of bookmarks to this artifact (maximum=100).",
            "icon": "http://www.delicious.com/favicon.ico",
        }
    }

    def __init__(self):
        super(Delicious, self).__init__()

    def is_relevant_alias(self, alias):
        (namespace, nid) = alias
        return("url" == namespace)

    # overriding default because delicious needs md5 of url in template
    def _get_templated_url(self, template, id, method=None):
        md5_of_url = hashlib.md5(id).hexdigest()
        url = template % md5_of_url
        return(url)

    def _extract_metrics(self, page, status_code=200, id=None):
        metrics_dict = {}
        if status_code != 200:
            if status_code == 404:
                return {}
            else:
                raise(self._get_error(status_code))

        data = provider._load_json(page)
        number_of_bookmarks = len(data)
        if number_of_bookmarks:
            metrics_dict = {
                'delicious:bookmarks' : number_of_bookmarks
            }

        return metrics_dict



