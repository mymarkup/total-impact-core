from totalimpact.providers import provider
from totalimpact.providers.provider import Provider, ProviderContentMalformedError

import simplejson

import logging
logger = logging.getLogger('ti.providers.github')

class Github(Provider):  

    example_id = ("github", "egonw,cdk")

    url = "http://github.com"
    descr = "A social, online repository for open-source software."
    member_items_url_template = "https://api.github.com/users/%s/repos"
    biblio_url_template = "https://api.github.com/repos/%s"
    aliases_url_template = "https://api.github.com/repos/%s"
    metrics_url_template = "https://api.github.com/repos/%s"

    provenance_url_templates = {
        "github:watchers" : "https://github.com/%s/%s/watchers",
        "github:forks" : "https://github.com/%s/%s/network/members"
        }

    static_meta_dict = {
        "watchers": {
            "display_name": "watchers",
            "provider": "GitHub",
            "provider_url": "http://github.com",
            "description": "The number of people who are watching the GitHub repository",
            "icon": "https://github.com/fluidicon.png",
        },
        "forks": {
            "display_name": "forks",
            "provider": "GitHub",
            "provider_url": "http://github.com",
            "description": "The number of people who have forked the GitHub repository",
            "icon": "https://github.com/fluidicon.png",
            }
    }     

    def __init__(self):
        super(Github, self).__init__()


    def _get_github_id(self, aliases):
        matching_id = None
        for alias in aliases:
            if alias:
                (namespace, id) = alias
                if namespace == "github":
                    matching_id = id
        return matching_id

    def is_relevant_alias(self, alias):
        (namespace, nid) = alias
        return("github" == namespace)



    #override because need to break up id
    def _get_templated_url(self, template, id, method=None):
        id_with_slashes = id.replace(",", "/")
        url = template % id_with_slashes
        return(url)

    def _extract_members(self, page, query_string): 
        data = provider._load_json(page)
        hits = [hit["name"] for hit in data]
        members = [("github", (query_string, hit)) for hit in list(set(hits))]
        return(members)

    def _extract_biblio(self, page, id=None):
        dict_of_keylists = {
            'title' : ['name'],
            'description' : ['description'],
            'owner' : ['owner', 'login'],
            'url' : ['svn_url'],
            'last_push_date' : ['pushed_at'],
            'create_date' : ['created_at']
        }
        biblio_dict = provider._extract_from_json(page, dict_of_keylists)

        return biblio_dict    
       
    def _extract_aliases(self, page, id=None):
        dict_of_keylists = {"url": ["svn_url"], 
                            "title" : ["name"]}

        aliases_dict = provider._extract_from_json(page, dict_of_keylists)
        if aliases_dict:
            aliases_list = [(namespace, nid) for (namespace, nid) in aliases_dict.iteritems()]
        else:
            aliases_list = []
        return aliases_list


    def _extract_metrics(self, page, status_code=200, id=None):
        if status_code != 200:
            if status_code == 404:
                return {}
            else:
                raise(self._get_error(status_code))

        dict_of_keylists = {
            'github:watchers' : ['watchers'],
            'github:forks' : ['forks']
        }

        metrics_dict = provider._extract_from_json(page, dict_of_keylists)

        return metrics_dict


    # overriding default because different provenance url for each metric
    def provenance_url(self, metric_name, aliases):
        id = self.get_best_id(aliases)
        if not id:
            return None
        try:
            (user, repo) = id.split(",")
        except ValueError:
            return None

        # Returns a different provenance url for each metric
        provenance_url = self.provenance_url_templates[metric_name] % (user, repo)
        return provenance_url
