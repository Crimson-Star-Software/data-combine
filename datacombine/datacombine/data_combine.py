import ciso8601
import json
import logging
import os

import requests
from django.core.exceptions import FieldError
from django.db import transaction, IntegrityError
from .models import (
    Contact,
    Phone,
    EmailAddress,
    ConstantContactList,
    Note,
    Address,
    UserStatusOnCCList
)

from .settings import BASE_DIR
from .secret_settings import API_KEY, AUTH_KEY

BASE_URI = 'https://api.constantcontact.com'
HTTP_FAIL_THRESHOLD = 400
HERE = os.path.join(BASE_DIR, "datacombine")

class DataCombine():
    def __init__(self, api_key=API_KEY,auth_key=AUTH_KEY,
                 loglvl=logging.DEBUG, logger=__name__,
                 logfile='dcombine.log'):
        self.api_key = api_key
        self.token = auth_key
        self._setup_logger(loglvl, logger, logfile)
        self.headers = {'Authorization': f'Bearer {self.token}'}
        self.contacts = []
        self.cclists = []

    def _setup_logger(self, lvl, logger, logfile="dcombine.log",
                      max_bytes=1000000, backup_count=5):
        self.logger = logging.getLogger(logger)
        self.logger.setLevel(lvl)
        path_to_logfile = os.path.join(HERE, "logs", logfile)
        rtfh = logging.handlers.RotatingFileHandler(
            path_to_logfile,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        rtfh.setFormatter(formatter)
        self.logger.addHandler(rtfh)

    def _report_cc_api_request_fail(self, r):
        self.logger.error(
            f"Attempt to harvest encountered {r.status_code}: "
            f"{r.reason}: {r.content}"
        )
        return None

    def _harvest_contact_page(self, params, api_url):
        url = f"{BASE_URI}{api_url}"
        params = {
            'api_key': self.api_key
        } if api_url.__contains__('next') else params
        limit = params.get('limit')
        if limit:
            self._limit = limit
        r = requests.get(url, params=params, headers=self.headers)
        self.logger.debug(f"Getting '{self._limit}' contacts from {url}.")

        if r.status_code >= HTTP_FAIL_THRESHOLD:
            return self._report_cc_api_request_fail(r)

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
        next_page = api_uri
        while next_page:
            next_page = self._harvest_contact_page(params, next_page)

    def _check_for_iso_8601_format(self, dt):
        return bool(ciso8601.parse_datetime(dt))

    def harvest_lists(self, modified_since=None, api_uri='/v2/lists'):
        params = {
            'api_key': self.api_key,
        }
        url = f"{BASE_URI}{api_uri}"
        if modified_since:
            if not self._check_for_iso_8601_format(modified_since):
                raise TypeError(f"'{modified_since}' is not in iso8601 format")
            else:
                params['modified_since'] = modified_since
        r = requests.get(url, params=params, headers=self.headers)

        if r.status_code >= HTTP_FAIL_THRESHOLD:
            return self._report_cc_api_request_fail(r)
        self.cclists = r.json()
        self.logger.debug(
            f"Successfully downloaded '{len(self.cclists)}' lists"
        )

    def read_from_highrise_contact_stash(self, jfname="yaya.json"):
        with open(jfname, 'r') as f:
            self.highrise_contacts_json = json.loads(f.read())

    def read_constantcontact_objects_from_json(
            self,
            jfname=os.path.join(HERE, "yaya_cc.json"),
            override_contacts=True
    ):
        if self.contacts:
            if override_contacts:
                self.logger.debug("Overriding contacts...")
            else:
                self.logger.info(f"'{len(self.contacts)}' already found, "
                                 f"not overriding.")
                return

        with open(jfname, 'r') as jf:
            data = json.loads(jf.read())
            self.contacts = data['contacts']
            self.cclists = data['cclists']

    def _prep_objects_to_dump(self, data):
        add_contacts = []
        add_lists = []
        fields = [
            (add_contacts, 'contacts'),
            (add_lists, 'cclists'),
        ]
        # Check if record exists in contacts and cclists
        # If so, don't re-add it
        for dumps, field in fields:
            for self_field in getattr(self, field):
                if any([x['id'] == self_field.get('id')\
                        for x in data.get(field)]):
                    continue
                else:
                    dumps.append(self_field)
        return (add_contacts, add_lists)

    def dump_constantcontact_objects_from_json(
            self,
            jfname=os.path.join(HERE, "yaya_cc.json"),
            override_json=True
    ):
        mode = 'w' if os.path.isfile(jfname) and not override_json else 'w+'
        with open(jfname, mode) as jf:
            if mode == 'w+':
                data = json.load(jf)
                self.logger.debug("Preparing to dump objects...")
                contacts, cclists = self._prep_objects_to_dump(data)
                json.dump({'contacts': contacts, 'cclists': cclists}, jf)
            else:
                json.dump(
                    {'contacts': self.contacts, 'cclists': self.cclists}, jf
                )
            self.logger.debug("Objects dumped successfully")

    @classmethod
    def get_init_values_for_model(_, cls):
        return [f.name for f in cls._meta.get_fields() if not f.is_relation
                and f.name != 'id']

    @staticmethod
    def convert_choice_to_field(choice):
        return choice.upper().replace(' ', '_')

    @classmethod
    def _setup_model_object(_, cls, attrs):
        kwargs = {}
        for fld in cls._meta.get_fields():
            if fld.name == 'id' or fld.many_to_many:
                continue
            elif fld.name.startswith("cc_"):
                if fld.name == "cc_id":
                    if cls.objects.filter(cc_id=attrs[fld.name[3:]]):
                        return
                kwargs[fld.name] = attrs[fld.name[3:]]
            elif hasattr(fld, 'choices') and fld.choices:
                chmap = {
                    DataCombine.convert_choice_to_field(ch[1]): ch[0]\
                    for ch in fld.choices
                }
                try:
                    kwargs[fld.name] = chmap[attrs[fld.name]]
                except KeyError:
                    kwargs[fld.name] = None
            else:
                try:
                    kwargs[fld.name] = attrs[fld.name]
                except KeyError:
                    kwargs[fld.name] = None
        return cls(**kwargs)

    @transaction.atomic
    def combine_cclist_json_into_db(self, cclist_json):
        md = cclist_json.get('modified_date')
        cd = cclist_json.get('created_date')
        if not self._check_for_iso_8601_format(md):
            raise TypeError("Modified date is not in ISO-8601 format")
        if not self._check_for_iso_8601_format(cd):
            raise TypeError("Created date is not in ISO-8601 format")
        ccid = cclist_json.get('id')
        id_in_db = ConstantContactList.objects.filter(cc_id=ccid)

        ccl = ConstantContactList(
            cc_id=ccid,
            status="AC" if cclist_json.get('status').startswith('A')\
                        else "HI",
            name=cclist_json.get('name'),
            created_date=cd,
            modified_date=md
        )
        if id_in_db:
            l = id_in_db.first()
            if ccl == l:
                self.logger.debug(
                    f"List named '{l.name}' already found in db skipping..."
                )
                return
            else:
                raise IntegrityError(
                    f"Lists with same ID do not match: {ccl.name} and {l.name}"
                    f", {ccl.cc_id} and {l.cc_id}."
                )
        ccl.save()
        return None

    @transaction.atomic
    def _initial_contact_setup_from_json(self, contact):
        cf = DataCombine.get_init_values_for_model(Contact)
        newContact = Contact(**{
            x: contact[x if not x.startswith('cc_') else x[3:]] for x in cf
        })
        newContact.status = Contact.convert_status_str_to_code(
            newContact.status
        )
        newContact.save()

    def combine_contacts_into_db(self):
        if not hasattr(self, 'contacts'):
            raise AttributeError("No contacts found")
        elif not hasattr(self, 'cclists'):
            raise AttributeError("No constant contact list found")
        # These are all the UserStatusOnCCList objects which
        # Need to be saved when the user has been entered into the database
        ustat_objects = []
        for cclist in self.cclists:
            self.combine_cclist_json_into_db(cclist)
        for c_i, contact in enumerate(self.contacts):
            try:
                cf = DataCombine.get_init_values_for_model(Contact)
                newContact = Contact(**{
                    x:contact[x if not x.startswith('cc_') else x[3:]] for x in cf
                })
                newContact.status = Contact.convert_status_str_to_code(
                    newContact.status
                )
                newContact.save()
                non_phone_or_cclist_m2m = [
                    (Address, "addresses"),
                    (EmailAddress, "email_addresses"),
                ]
                for xcclist in contact.get('lists'):
                    listobj = ConstantContactList.objects.first()
                    liststat = "HI" if xcclist.get('status').startswith('H') else "AC"
                    ustat_obj = UserStatusOnCCList(
                        cclist=listobj, user=newContact, status=liststat
                    )
                    ustat_objects.append(ustat_obj)
                phone_fields = ['home_phone', 'work_phone', 'cell_phone', 'fax']
                for phfld in phone_fields:
                    try:
                        phone_num = contact.get(phfld)
                        if not phone_num:
                            continue
                        ph = Phone()
                        ph.create_from_str(phone_num)
                        ph_in_db = Phone.is_phone_in_db(ph)
                        phobj = getattr(newContact, phfld)
                        if ph_in_db:
                            self.logger.debug(
                                f"Phone number '{ph}' is already in database"
                            )
                            phobj.add(ph_in_db.first())
                        else:
                            ph.save()
                            phobj.add(ph)
                    except FieldError:
                        continue
                for cls_obj, m2m in non_phone_or_cclist_m2m:
                    for m2mattrs in contact.get(m2m):
                        m2mobj = DataCombine._setup_model_object(
                            cls_obj, m2mattrs
                        )
                        if m2mobj:
                            m2mobj.save()
                            ncontact_m2mfield = getattr(newContact, m2m)
                            try:
                                ncontact_m2mfield.add(m2mobj)
                            except:
                                from IPython import embed
                                embed()
                        else:
                            self.logger.debug(
                                f"{m2m.capitalize()} {m2mobj} already in database"
                                f"...skipping"
                            )
                for note in contact.get('notes'):
                    note_obj = DataCombine._setup_model_object(
                        Note, note
                    )
                    note_obj.save()
                for ustat_obj in ustat_objects:
                    ustat_obj.save()
                newContact.save()

                # Update progress bar
                updt(len(self.contacts), c_i)
            except KeyboardInterrupt:
                self.logger.info("Interrupt signal received...quitting.")
                return
            except:
                self.logger.exception(f"Exception on contact #{c_i}...skipping...")


if __name__ == '__main__':
    dc = DataCombine()
    dc.read_constantcontact_objects_from_json()
    dc.combine_contacts_into_db()
