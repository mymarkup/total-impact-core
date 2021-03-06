from totalimpact.providers import provider
from totalimpact.providers.provider import Provider, ProviderContentMalformedError

import simplejson, urllib, os, itertools

import logging
logger = logging.getLogger('ti.providers.pubmed')

class Pubmed(Provider):  

    example_id = ("pmid", "22855908")

    url = "http://pubmed.gov"
    descr = "PubMed comprises more than 21 million citations for biomedical literature"
    provenance_url_pmc_citations_template = "http://www.ncbi.nlm.nih.gov/pubmed?linkname=pubmed_pubmed_citedin&from_uid=%s"
    provenance_url_pmc_citations_filtered_template = "http://www.ncbi.nlm.nih.gov/pubmed?term=%s&cmd=DetailsSearch"
    provenance_url_f1000_template = "http://f1000.com/pubmed/%s"

    metrics_url_template = None # have specific metrics urls instead
    metrics_pmc_citations_url_template = "http://www.pubmedcentral.nih.gov/utils/entrez2pmcciting.cgi?view=xml&id=%s&email=team@total-impact.org&tool=total-impact"
    metrics_pmc_filter_url_template = "http://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=(%s)&email=team@total-impact.org&tool=total-impact"
    metrics_f1000_url_template = "http://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi?dbfrom=pubmed&id=%s&cmd=llinks&email=team@total-impact.org&tool=total-impact"

    aliases_from_doi_url_template = "http://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?term=%s&email=team@total-impact.org&tool=total-impact" 
    aliases_from_pmid_url_template = "http://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=%s&retmode=xml&email=team@total-impact.org&tool=total-impact" 

    aliases_pubmed_url_template = "http://www.ncbi.nlm.nih.gov/pubmed/%s"

    biblio_url_template = "http://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=%s&retmode=xml&email=team@total-impact.org&tool=total-impact" 

    static_meta_dict = {
        "pmc_citations": {
            "display_name": "citations",
            "provider": "PubMed Central",
            "provider_url": "http://pubmed.gov",
            "description": "The number of citations by papers in PubMed Central",
            "icon": "http://www.ncbi.nlm.nih.gov/favicon.ico"
        }, 
        "pmc_citations_reviews": {
            "display_name": "citations: reviews",
            "provider": "PubMed Central",
            "provider_url": "http://pubmed.gov",
            "description": "The number of citations by review papers in PubMed Central",
            "icon": "http://www.ncbi.nlm.nih.gov/favicon.ico"
        }, 
        "pmc_citations_editorials": {
            "display_name": "citations: editorials",
            "provider": "PubMed Central",
            "provider_url": "http://pubmed.gov",
            "description": "The number of citations by editorials papers in PubMed Central",
            "icon": "http://www.ncbi.nlm.nih.gov/favicon.ico"
        },            
        "f1000": {
            "display_name": "reviewed",
            "provider": "F1000",
            "provider_url": "http://f1000.com",
            "description": "The article has been reviewed by F1000",
            "icon": "http://f1000.com/1344012469601/images/favicon.ico"
        }            
    }


    def __init__(self):
        super(Pubmed, self).__init__()

    def is_relevant_alias(self, alias):
        (namespace, nid) = alias
        relevant = (namespace=="pmid")
        return(relevant)

    # overriding default because overriding aliases method
    @property
    def provides_aliases(self):
        return True

    # overriding default because overriding aliases method
    @property
    def provides_metrics(self):
        return True

    def _extract_biblio(self, page, id=None):
        dict_of_keylists = {"year": ["PubmedArticleSet", "MedlineCitation", "Article", "Journal", "PubDate", "Year"], 
                            "title": ["PubmedArticleSet", "MedlineCitation", "Article", "ArticleTitle"],
                            "journal": ["PubmedArticleSet", "MedlineCitation", "Article", "Journal", "Title"],
                            }
        biblio_dict = provider._extract_from_xml(page, dict_of_keylists)
        dom_authors = provider._find_all_in_xml(page, "LastName")
        try:
            biblio_dict["authors"] = ", ".join([author.firstChild.data for author in dom_authors])
        except (AttributeError, TypeError):
            pass
        return biblio_dict  

    def _extract_aliases_from_doi(self, page, doi):
        dict_of_keylists = {"pmid": ["eSearchResult", "IdList", "Id"], 
                            "QueryTranslation": ["eSearchResult", "QueryTranslation"]}

        aliases_dict = provider._extract_from_xml(page, dict_of_keylists)
        aliases_list = []
        if aliases_dict:
            if aliases_dict["QueryTranslation"] == (doi + "[All Fields]"):
                aliases_list = [("pmid", str(aliases_dict["pmid"]))]
        return aliases_list


    def _extract_aliases_from_pmid(self, page, pmid):
        dict_of_keylists = {"doi": ["PubmedData", "ArticleIdList"]}

        (doc, lookup_function) = provider._get_doc_from_xml(page)
        doi = None
        try:
            articleidlist = doc.getElementsByTagName("ArticleIdList")[0]
            for articleid in articleidlist.getElementsByTagName("ArticleId"):
                if (articleid.getAttribute("IdType") == u"doi"):
                    doi = articleid.firstChild.data
        except (IndexError, TypeError):
            pass

        #sometimes no doi, or PMID has a doi-fragment in the doi field:
        aliases_list = []
        if doi:
            if "10." in doi:  
                aliases_list = [("doi", doi)]
        return aliases_list

    def _get_eutils_page(self, id, url, cache_enabled=True):
        logger.debug("%20s getting eutils page for %s" % (self.provider_name, id))

        response = self.http_get(url, cache_enabled=cache_enabled)
        if response.status_code != 200:
            logger.warning("%20s WARNING, status_code=%i getting %s" 
                % (self.provider_name, response.status_code, url))            
            if response.status_code == 404:
                return ""
            if response.status_code == 414:  #Request-URI Too Large
                return ""
            else:
                self._get_error(response.status_code, response)
        return response.text

    # overriding so can look up in both directions
    def aliases(self, 
            aliases, 
            provider_url_template=None,
            cache_enabled=True):            

        new_aliases = []
        for alias in aliases:
            (namespace, nid) = alias
            if (namespace == "doi"):
                aliases_from_doi_url = self.aliases_from_doi_url_template %nid
                page = self._get_eutils_page(nid, aliases_from_doi_url, cache_enabled)
                if page:
                    new_aliases += self._extract_aliases_from_doi(page, nid)
            if (namespace == "pmid"):
                # look up doi and other things on pubmed page
                aliases_from_pmid_url = self.aliases_from_pmid_url_template %nid
                page = self._get_eutils_page(nid, aliases_from_pmid_url, cache_enabled)
                if page:
                    new_aliases += self._extract_aliases_from_pmid(page, nid)
                    biblio = self._extract_biblio(page, nid)
                    if biblio:
                        new_aliases += [("biblio", biblio)]
                # also, add link to paper on pubmed
                new_aliases += [("url", self.aliases_pubmed_url_template %nid)] 

        # get uniques for things that are unhashable
        new_aliases_unique = [k for k,v in itertools.groupby(sorted(new_aliases))]

        return new_aliases_unique

    def _filter(self, id, citing_pmcids, filter_ptype):
        pmcids_string = " OR ".join(["PMC"+pmcid for pmcid in citing_pmcids])
        query_string = filter_ptype + "[ptyp] AND (" + pmcids_string + ")"
        pmcid_filter_url = self.metrics_pmc_filter_url_template %query_string
        page = self._get_eutils_page(id, pmcid_filter_url)
        (doc, lookup_function) = provider._get_doc_from_xml(page)  
        try:    
            id_docs = doc.getElementsByTagName("Id")
            pmids = [id_doc.firstChild.data for id_doc in id_docs]
        except TypeError:
            logger.warning("%20s no Id xml tags for %s" % (self.provider_name, id))
            pmids = []
        return pmids

    def _check_reviewed_by_f1000(self, id, cache_enabled):
        metrics_f1000_url = self.metrics_f1000_url_template %id
        page = self._get_eutils_page(id, metrics_f1000_url)
        f1000_url = "http://f1000.com/pubmed/%s" %id
        if (f1000_url in page):
            reviewed_by_f1000 = "Yes"
        else:
            reviewed_by_f1000 = 0
        return reviewed_by_f1000

    # override because multiple pages to get
    def get_metrics_for_id(self, 
            id, 
            provider_url_template=None, 
            cache_enabled=True):

        logger.debug("%20s getting metrics for %s" % (self.provider_name, id))
        metrics_dict = {}

        reviewed_by_f1000 = self._check_reviewed_by_f1000(id, cache_enabled)
        if reviewed_by_f1000:
            metrics_dict["pubmed:f1000"] = reviewed_by_f1000

        citing_pmcids = self._get_citing_pmcids(id, cache_enabled)
        if (citing_pmcids):
            metrics_dict["pubmed:pmc_citations"] = len(citing_pmcids)
    
            number_review_pmids = len(self._filter(id, citing_pmcids, "review"))
            if number_review_pmids:
                metrics_dict["pubmed:pmc_citations_reviews"] = number_review_pmids
    
            number_editorial_pmids = len(self._filter(id, citing_pmcids, "editorial"))
            if number_editorial_pmids:
                metrics_dict["pubmed:pmc_citations_editorials"] = number_editorial_pmids
        # check for f1000

        return metrics_dict

    def _extract_citing_pmcids(self, page):
        if (not "PubMedToPMCcitingformSET" in page):
            raise ProviderContentMalformedError()
        dict_of_keylists = {"pubmed:pmc_citations": ["PubMedToPMCcitingformSET", "REFORM"]}
        (doc, lookup_function) = provider._get_doc_from_xml(page)
        try:
            pmcid_doms = doc.getElementsByTagName("PMCID")
            pmcids = [pmcid_dom.firstChild.data for pmcid_dom in pmcid_doms]
        except TypeError:
            logger.warning("%20s no PMCID xml tags for %s" % (self.provider_name, id))            
            pmcids = []
        return pmcids

    # documentation for pubmedtopmcciting: http://www.pubmedcentral.nih.gov/utils/entrez2pmcciting.cgi
    # could take multiple PMC IDs
    def _get_citing_pmcids(self, id, cache_enabled=True):
        pmc_citations_url = self.metrics_pmc_citations_url_template %id
        page = self._get_eutils_page(id, pmc_citations_url, cache_enabled)
        pmcids = self._extract_citing_pmcids(page)
        return pmcids

    def provenance_url(self, metric_name, aliases):

        id = self.get_best_id(aliases)     
        if not id:
            # not relevant to Pubmed
            return None

        url = None
        if (metric_name == "pubmed:pmc_citations"):
            url = self._get_templated_url(self.provenance_url_pmc_citations_template, id, "provenance")

        elif (metric_name == "pubmed:f1000"):
            url = self._get_templated_url(self.provenance_url_f1000_template, id, "provenance")

        elif (metric_name == "pubmed:pmc_citations_reviews"):
            citing_pmcids = self._get_citing_pmcids(id)
            filtered_pmids = self._filter(id, citing_pmcids, "review")
            pmids_string = " OR ".join([pmid for pmid in filtered_pmids])
            url = self._get_templated_url(self.provenance_url_pmc_citations_filtered_template, 
                    urllib.quote(pmids_string), "provenance")

        elif (metric_name == "pubmed:pmc_citations_editorials"):
            citing_pmcids = self._get_citing_pmcids(id)
            filtered_pmids = self._filter(id,citing_pmcids, "editorial")
            pmids_string = " OR ".join([pmid for pmid in filtered_pmids])
            url = self._get_templated_url(self.provenance_url_pmc_citations_filtered_template, 
                    urllib.quote(pmids_string), "provenance")

        return url



