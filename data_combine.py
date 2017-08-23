import json
import logging

import requests

from secret_settings import API_KEY, AUTH_KEY

BASE_URI = 'https://api.constantcontact.com'
HTTP_FAIL_THRESHOLD = 400


class DataCombine():
    def __init__(self, api_key=API_KEY,auth_key=AUTH_KEY,
                 loglvl=logging.DEBUG, logger=__name__):
        self.api_key = api_key
        self.token = auth_key
        self._setup_logger(loglvl, logger)
        self.contacts = []

    def _setup_logger(self, lvl, logger):
        self.logger = logging.getLogger(logger)
        self.logger.setLevel(lvl)
        ch = logging.StreamHandler()
        self.logger.addHandler(ch)

    def _harvest_contact_page(self, params, headers, api_url):
        url = f"{BASE_URI}{api_url}"
        params = {
            'api_key': self.api_key
        } if api_url.__contains__('next') else params
        limit = params.get('limit')
        if limit:
            self._limit = limit
        r = requests.get(url, params=params, headers=headers)
        self.logger.debug(f"Getting '{self._limit}' contacts from {url}.")

        if r.status_code >= HTTP_FAIL_THRESHOLD:
            self.logger.error(
                f"Attempt to harvest encountered {r.status_code}: "
                f"{r.reason}: {r.content}"
            )
            return None
        rjson = r.json()
        self.contacts.extend(rjson['results'])
        if "next_link" in rjson['meta']['pagination']:
            next_link = rjson['meta']['pagination']['next_link']
            self.logger.debug(f"Found next link to harvest: '{next_link}'")
            return next_link
        else:
            self.logger.debug("No more contacts to harvest.")
            return False

    def harvest_contacts(self, status='ALL', limit='500',
                         api_uri='/v2/contacts'):
        params = {
            'status': status,
            'limit': limit,
            'api_key': self.api_key,
        }
        headers = {'Authorization': f'Bearer {self.token}'}
        next_page = api_uri
        while next_page:
            next_page = self._harvest_contact_page(params, headers, next_page)


    def read_from_highrise_contact_stash(self, jfname="yaya.json"):
        with open(jfname, 'r') as f:
            self.highrise_contacts_json = json.loads(f.read())

    def read_constantcontact_contacts_from_json(self, jfname="yaya_cc.json",
                                                override_contacts=True):
        if self.contacts:
            if override_contacts:
                self.logger.debug("Overriding contacts...")
            else:
                self.logger.info(f"'{len(self.contacts)}' already found, "
                                 f"not overriding.")
                return

        with open(jfname, 'r') as jf:
            self.contacts = json.loads(jf.read())


if __name__ == '__main__':
    dc = DataCombine()
