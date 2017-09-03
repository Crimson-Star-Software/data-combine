import ciso8601
import datetime
from dateutil import parser
import json
import logging
import os

import requests
from django.core.exceptions import FieldError
from django.db.utils import DataError
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
from profilestats import profile

from .settings import BASE_DIR
from .secret_settings import API_KEY, AUTH_KEY
from .utils import updt


BASE_URI = 'https://api.constantcontact.com'
HTTP_FAIL_THRESHOLD = 400
HERE = os.path.join(BASE_DIR, "datacombine")


class CombineException(BaseException):
    def __init__(self, message=""):
        super()
        self.message = message


class DataCombine():
    def __init__(self, api_key=API_KEY,auth_key=AUTH_KEY,
                 loglvl=logging.ERROR, logger=__name__,
                 logfile='dcombine.log'):
        self.api_key = api_key
        self.token = auth_key
        # Check for log directory
        logdir = os.path.join(HERE, "logs")
        if not os.path.isdir(logdir):
            os.mkdir(logdir)
        self._setup_logger(loglvl, logger, logfile)
        self.headers = {'Authorization': f'Bearer {self.token}'}
        self.contacts = []
        self.cclists = []
        self.bad_phone_nums = dict()
        self.bad_m2m = dict()

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

    def harvest_contacts(self, status='ALL', limit='500', modified_since=None,
                         api_uri='/v2/contacts', delete_contacts=True):
        if delete_contacts:
            self.contacts = []
        else:
            raise CombineException(
                "Contacts already exist and 'delete_contacts' parameter "
                "is False"
            )

        params = {
            'status': status,
            'limit': limit,
            'api_key': self.api_key,
        }
        if modified_since:
            if not self._check_for_iso_8601_format(modified_since):
                raise TypeError(f"'{modified_since}' is not in iso8601 format")
            else:
                params['modified_since'] = modified_since
        next_page = api_uri
        while next_page:
            next_page = self._harvest_contact_page(params, next_page)

    def _check_for_iso_8601_format(self, dt):
        return bool(ciso8601.parse_datetime(dt))

    def harvest_lists(self, modified_since=None,
                      api_uri='/v2/lists', delete_cclists=True):

        if delete_cclists:
            self.cclists = []
        else:
            raise CombineException(
                "cclists already exist and 'delete_cclists' parameter "
                "is False"
            )

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
        self.logger.debug(f"Making list request: {r}")

        if r.status_code >= HTTP_FAIL_THRESHOLD:
            return self._report_cc_api_request_fail(r)
        self.cclists = r.json()
        self.logger.debug(
            f"Successfully downloaded '{len(self.cclists)}' lists"
        )

    def _get_most_recent_datetime(self, cls_obj, param):
        by_most_recent = cls_obj.objects.order_by('-'+param)
        if not by_most_recent:
            return None
        mrdt = getattr(by_most_recent.first(), param)
        if mrdt:
            return mrdt.isoformat()
        else:
            return None

    def update_local_db_caches(self):
        most_recent_list_dt = self._get_most_recent_datetime(
            ConstantContactList, 'modified_date'
        )
        most_recent_contact_dt = self._get_most_recent_datetime(
            Contact, 'cc_modified_date'
        )
        self.harvest_lists(modified_since=most_recent_list_dt)
        self.harvest_contacts(modified_since=most_recent_contact_dt)
        self.logger.info(
            "Harvested Constant Contact lists from "
            f"{most_recent_list_dt} and harvested Constant Contact"
            f" Contacts from {most_recent_contact_dt}."
        )

    def combine_and_update_new_entries(self):
        # Get all updated lists and contacts
        self.update_local_db_caches()

        for cclist in self.cclists:
            self.combine_cclist_json_into_db(cclist)
        self.combine_contacts_into_db()

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
        try:
            cf = DataCombine.get_init_values_for_model(Contact)
            fields = dict()
            for x in cf:
                try:
                    if not x.startswith('cc_'):
                        fields[x] = contact.get(x)
                    else:
                        fields[x] = contact.get(x[3:])
                except KeyError as ke:
                    key = ke.args[0]
                    if Contact._meta.get_field(key).null:
                        fields[x] = ""
                    else:
                        raise ke
            newContact = Contact(**fields)
            newContact.status = Contact.convert_status_str_to_code(
                newContact.status
            )
            newContact.save()
            return newContact
        except KeyError as ke:
            key = ke.args[0]
            self.logger.error(
                f"Encountered a KeyError on setting "
                f"'_initial_contact_setup_from_json', there is no key "
                f"'{key}' in contact: {contact}"
            )
            raise

    @transaction.atomic
    def combine_phone_number_into_db(self, phone_num, newContact, phfld):
        if not phone_num:
            return
        ph = Phone()
        try:
            ph.create_from_str(phone_num)
        except FieldError:
            raise FieldError(phone_num, newContact, phfld)

        if ph == None:
            self.logger.info(f"phone_num='{phone_num}' produces None")
            return

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

    @transaction.atomic
    def _combine_m2m_field_into_db(self, cls_obj, m2mattrs, newContact, m2m):
        m2mobj = DataCombine._setup_model_object(
            cls_obj, m2mattrs
        )
        if m2mobj:
            try:
                m2mobj.save()
            except DataError as de:
                too_long = "value too long for type character varying"
                if de.args[0].__contains__(too_long):
                    for key, val in m2mattrs.items():
                        cf = cls_obj._meta.get_field(key)
                        if not val or not cf.max_length:
                            continue
                        if len(val) > cf.max_length:
                            de.args = (cls_obj, key, val)
                            raise de
            ncontact_m2mfield = getattr(newContact, m2m)
            ncontact_m2mfield.add(m2mobj)
        else:
            self.logger.debug(
                f"{m2m.capitalize()} {m2mobj} already in database"
                f"...skipping"
            )
        return newContact

    @transaction.atomic
    def _combine_notes_into_db(self, notes, newContact):
        for note in notes:
            newNote = DataCombine._setup_model_object(Note, note)
            if newNote:
                newNote.contact = newContact
                newNote.save()

    @transaction.atomic
    def _save_ustat_object(self, ustat_object):
        ustat_object.save()

    def _save_ustat_objects(self, contact, newContact, updating):
        for xcclist in contact.get('lists'):
            listobj = ConstantContactList.objects.filter(
                cc_id=xcclist['id']
            )
            liststat = "HI" if xcclist.get('status').startswith('H') \
                else "AC"
            ustat_obj = UserStatusOnCCList(
                cclist=listobj.first(), user=newContact, status=liststat
            )
            if updating:
                con = newContact.cc_lists.filter(cc_id=xcclist['id']).first()
                if con.status != liststat:
                    con.status = liststat
                    con.update()
                return
            self._save_ustat_object(ustat_obj)

    def _continue_combine(self, count):
        # Update progress bar
        updt(len(self.contacts), count)
        return count+1

    #@profile(print_stats=10, dump_stats=True, profile_filename="p3.out")
    def combine_contacts_into_db(self):
        begin_time = datetime.datetime.now()
        processed = 0
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
                newContact = None
                updatingContact = False
                contact_in_db = Contact.objects.filter(cc_id=contact.get("id"))
                if contact_in_db:
                    contact_in_db = contact_in_db.first()
                    contact_date = parser.parse(contact.get("modified_date"))
                    if contact_in_db.cc_modified_date == contact_date:
                        continue
                    else:
                        newContact = contact_in_db
                        del contact_in_db
                else:
                    newContact = self._initial_contact_setup_from_json(contact)

                non_phone_or_cclist_m2m = [
                    (Address, "addresses"),
                    (EmailAddress, "email_addresses"),
                ]

                self._save_ustat_objects(contact, newContact, updatingContact)

                phone_fields = [
                    'home_phone',
                    'work_phone',
                    'cell_phone',
                    'fax'
                ]
                for phfld in phone_fields:
                    try:
                        self.combine_phone_number_into_db(
                            contact.get(phfld), newContact, phfld
                        )
                    except FieldError as fe:
                        self.bad_phone_nums.setdefault(newContact.cc_id, [])\
                            .append({phfld:contact.get(phfld)})
                for cls_obj, m2m in non_phone_or_cclist_m2m:
                    for m2mattrs in contact.get(m2m):
                        try:
                            newContact = self._combine_m2m_field_into_db(
                                cls_obj, m2mattrs, newContact, m2m
                            )
                        except DataError:
                            self.bad_m2m.setdefault(newContact.cc_id, []).\
                                append({newContact.cc_id: m2mattrs})
                self._combine_notes_into_db(contact.get('notes'), newContact)

                newContact.save()

            except KeyboardInterrupt:
                self.logger.info("Interrupt signal received...quitting.")
                return
            except DataError as de:
                if len(de.args) == 3:
                    self.logger.error(
                        "For class object "
                        f"{de.args[0]}.{de.args[1]}={de.args[2]}. Is too long."
                    )
                else:
                    self.logger.error(
                        f"Data error on contact #{c_i} {de.args[0]}"
                    )
            except FieldError:
                self.logger.warning(
                    f"Field error on contact #{c_i} {contact} for {phfld}"
                    "...skipping..."
                )
            except:
                self.logger.exception(f"Exception on contact #{c_i}...skipping...")
            finally:
                processed = self._continue_combine(processed)
        end_time = datetime.datetime.now()
        total_time = (end_time - begin_time).total_seconds()
        updt(len(self.contacts), len(self.contacts))
        self.logger.info(
            f"Combined time to process '{processed}' contacts: "
            f"{total_time // 60} minutes and {total_time % 60} seconds."
         )

if __name__ == '__main__':
    dc = DataCombine()
    dc.read_constantcontact_objects_from_json()
    dc.combine_contacts_into_db()
