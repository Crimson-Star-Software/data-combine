import ciso8601
import datetime
from dateutil import parser
import json
import logging
import os

import requests
from cryptography.fernet import Fernet
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
    UserStatusOnCCList,
    RequiringRemediation
)
from profilestats import profile

from .settings import BASE_DIR
from .utils import updt

API_KEY = None
AUTH_KEY = None

# Optional load of secret_settings.py, if it is in package
try:
    from .secret_settings import API_KEY, AUTH_KEY
except ImportError:
    pass

BASE_URI = 'https://api.constantcontact.com'
HTTP_FAIL_THRESHOLD = 400
HERE = os.path.join(BASE_DIR, "datacombine")


class CombineException(BaseException):
    def __init__(self, message=""):
        super()
        self.message = message


class DataCombine():
    def __init__(self, api_key=API_KEY, auth_key=AUTH_KEY,
                 loglvl=logging.ERROR, logger_name=__name__,
                 logfile='dcombine.log'):
        """Manages relationship between the local DB and ConstantContact API

        Uses the optional file `secret_settings.py` to set the default API_KEY,
        AUTH_KEY. Some methods require the postgres password, which can also be
        in this file. The `secret_settings.py` is not maintained in the github
        repo, for obvious security reasons, and must be in the same package
        as `data_combine.py`.

        :param api_key: (str) ConstantContact developer API key
        :param auth_key: (str) ConstantContact account authorization key
        :param loglvl: (int, default: logging.ERROR == 40) Log level severity
            threshold
        :param logger_name: (str) Name of the logger used
        :param logfile: (str) Name of the logfile
        """
        self.api_key = api_key
        self.token = auth_key
        # Check for log directory
        logdir = os.path.join(HERE, "logs")
        if not os.path.isdir(logdir):
            os.mkdir(logdir)
        self._setup_logger(loglvl, logger_name, logfile)
        self.headers = {'Authorization': f'Bearer {self.token}'}
        self.contacts = []
        self.cclists = []
        self.highrise_contacts_json = dict()
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
        # Poop pants. Die.
        self.logger.error(
            f"Attempt to harvest encountered {r.status_code}: "
            f"{r.reason}: {r.content}"
        )
        return None

    def _harvest_contact_page(self, params, api_url):
        url = f"{BASE_URI}{api_url}"

        # Parameters should only be required on the initial GET request
        params = {
            'api_key': self.api_key
        } if api_url.__contains__('next') else params

        limit = params.get('limit')
        if limit:
            self._limit = limit

        # GET them contacts
        r = requests.get(url, params=params, headers=self.headers)
        self.logger.debug(f"Getting '{self._limit}' contacts from {url}.")

        # In case of UH-OH!
        if r.status_code >= HTTP_FAIL_THRESHOLD:
            return self._report_cc_api_request_fail(r)

        # Pick them tasty contacts
        rjson = r.json()
        self.contacts.extend(rjson['results'])

        # Get next_link or signal end
        if "next_link" in rjson['meta']['pagination']:
            next_link = rjson['meta']['pagination']['next_link']
            self.logger.debug(f"Found next link to harvest: '{next_link}'")
            return next_link
        else: # DONE!
            self.logger.debug("No more contacts to harvest.")
            return False

    def harvest_contacts(self, status='ALL', limit='500', modified_since=None,
                         api_uri='/v2/contacts', delete_contacts=True):
        """Downloads contacts from ConstantContact account

        :param status: (str): From one of UNCONFIRMED, ACTIVE, OPTOUT, REMOVED,
            NON_SUBSCRIBER or for all of the above, ALL. See:
            https://developer.constantcontact.com/docs/contacts-api/
                contacts-index.html
            for more informaton on these statuses.
        :param limit: (str / int) Number of contacts to download per page.
            Maximum value allowed by ConstantContact is 500.
        :param modified_since: (datetime) Only download contacts modified after
            this date and time
        :param api_uri: (str) The API endpoint for ConstantContact contacts
        :param delete_contacts: (bool) Delete any values currently in
            `self.contacts`
        :return: None, contacts are saved in json formatted list in
            `self.contacts`
        """
        if delete_contacts:
            self.contacts = []
        else:
            raise CombineException(
                "Contacts already exist and 'delete_contacts' parameter "
                "is False"
            )

        if limit and not type(limit) == str:
            limit = str(limit)

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
        """Downloads lists from ConstantContact account

        :param modified_since: (datetime) Only download lists modified after
            this date and time
        :param api_uri: (str) The API endpoint for ConstantContact lists
        :param delete_cclists: (bool) Delete any values current in
            `self.cclists`
        :return: None, lists are saved in json formatted list in `self.cclists`
        """
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

        # GET dem lists!
        r = requests.get(url, params=params, headers=self.headers)
        self.logger.debug(f"Making list request: {r}")

        # In case of UH-OH!
        if r.status_code >= HTTP_FAIL_THRESHOLD:
            return self._report_cc_api_request_fail(r)

        # GET'ten dem lists
        self.cclists = r.json()
        self.logger.debug(
            f"Successfully downloaded '{len(self.cclists)}' lists"
        )

    def _get_most_recent_datetime(self, cls_obj, param):
        # Order in decreasing order so first is now last, and last is now first
        by_most_recent = cls_obj.objects.order_by('-'+param)
        if not by_most_recent:
            return None
        mrdt = getattr(by_most_recent.first(), param)
        if mrdt:
            return mrdt.isoformat()
        else:
            return None

    def update_local_db_caches(self):
        """Finds the most recent lists and contacts, and downloads any new ones

        Works primarly through the `harvest` functions, and will delete any
        contacts or lists in their respective variables, and overwrite them
        with new lists and contacts.

        :return: None. Overwrites `self.contacts` and `self.cclists` with
            new contacts and lists, respectively.
        """
        most_recent_list_dt = self._get_most_recent_datetime(
            ConstantContactList, 'modified_date'
        )
        most_recent_contact_dt = self._get_most_recent_datetime(
            Contact, 'cc_modified_date'
        )

        # Begin the harvesting!!!
        self.harvest_lists(modified_since=most_recent_list_dt)
        self.harvest_contacts(modified_since=most_recent_contact_dt)

        self.logger.info(
            "Harvested Constant Contact lists from "
            f"{most_recent_list_dt} and harvested Constant Contact"
            f" Contacts from {most_recent_contact_dt}."
        )

    def combine_and_update_new_entries(self):
        """Updates local db caches and combines them into the db

        Note: "db caches" are defined as `self.cclists` and `self.contacts`

        :return: None
        """
        # Get all updated lists and contacts / HARVEST
        self.update_local_db_caches()

        # Update databases / COMBINE
        for cclist in self.cclists:
            self.combine_cclist_json_into_db(cclist)
        self.combine_contacts_into_db()

    def read_from_highrise_contact_stash(self, jfname="yaya.json"):
        """Reads HighRise contacts that have been converted to json

        :param jfname: (str) Filename of HighRise stash
        :return: Populates `self.highrise_contacts_json` with HighRise contacts
        """
        with open(jfname, 'r') as f:
            self.highrise_contacts_json = json.loads(f.read())

    def read_constantcontact_objects_from_json(
            self,
            jfname=os.path.join(HERE, "yaya_cc.json"),
            override_contacts=True,
            override_lists=True
    ):
        """Read previously collected ConstantContact objects from JSON file

        :param jfname: (str) Path to json file with ConstantContact data
        :param override_contacts: (bool) Replace `self.contact` with contacts
            in json file
        :param override_lists: (bool) Replace `self.cclist` with lists from
            json file
        :return: None
        """
        with open(jfname, 'r') as jf:
            data = json.loads(jf.read())
            if hasattr(self, 'contacts'):
                if override_contacts:
                    self.logger.debug("Overriding contacts...")
                    self.contacts = data['contacts']
                else:
                    self.logger.info(f"'{len(self.contacts)}' already found, "
                                     f"not overriding. Merging with contacts.")
                    self._update_ccobj("contacts", data['contacts'])
            if hasattr(self, 'cclists'):
                if override_lists:
                    self.logger.debug("Overriding lists...")
                    self.cclists = data['cclists']
                else:
                    self.logger.info(f"'{len(self.cclists)}' already found, "
                                     f"not overriding. Merging with lists.")
                    self._update_ccobj("cclists", data['cclists'])
            remed = data.get('to_remidate')
            if remed:
                self.bad_phone_nums = remed.get('bad_phone_nums')
                self.bad_m2m = remed.get('bad_m2m')

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

    def _update_ccobj(self, field, new_ccobj):
        obj_ids = [obj.get('id') for obj in getattr(self, field)]
        if hasattr(self, field):
            # Grab that field in the ccobj
            ccobj = getattr(self, field) #<- updates (adds to) this field
            for obj in new_ccobj:
                if obj.get('id') in obj_ids:
                    continue
                else:
                    ccobj.append(obj)

    def dump_constantcontact_objects_from_json(
            self,
            jfname=os.path.join(HERE, "yaya_cc.json"),
            override_json=True,
            encrypt=True
    ):
        """Dump ConstantContact objects into a JSON formatted file

        :param jfname: (str) Path to JSON file
        :param override_json: (bool) If file exists at `jfname`, delete?
        :return: None, but there should be data in the file at `jfname`
        """
        mode = 'w' if not override_json else 'w+'
        data = dict()
        with open(jfname, mode) as jf:
            if mode == 'w+': # Read and write
                try:
                    self.logger.debug("Preparing to dump objects...")
                    data = json.load(jf)
                    contacts, cclists = self._prep_objects_to_dump(data)
                except json.JSONDecodeError as jde:
                    fileinfo = os.stat(jfname)
                    if fileinfo.st_size == 0:
                        msg = f"File '{jfname}' is 0 bytes...writing to it"
                        if logging.INFO >= self.logger.level:
                            print(msg)
                        self.logger.info(msg)
                    else:
                        self.logger.exception(
                            f"Could not read JSON file {jfname}. "
                            f"No objects dumped"
                        )
                        raise jde
                    contacts, cclists = (dict(), dict())
                self._update_ccobj('contacts', contacts)
                self._update_ccobj('cclists', cclists)
            data = {
                'contacts': self.contacts,
                'cclists': self.cclists,
                'to_remidate': {
                    'bad_phone_numbers': dict(),
                    'bad_m2m': dict()
                }
            }
            if hasattr(self, 'bad_phone_numbers'):
                data['to_remidate']['bad_phone_nums'] = self.bad_phone_nums
            if hasattr(self, 'bad_m2m'):
                data['to_remidate']['bad_m2m'] = self.bad_m2m
            json.dump(data, jf)
            self.logger.debug("Objects dumped successfully")

    @classmethod
    def get_init_values_for_model(_, cls):
        """Returns all fields that are not relations or auto-incremented id's

        :param cls: The class model to get the fields of
        :return: (`list` of `str`) A list of the names of each non-relation and
            non-auto-incremented `django.db.models.fields`
        """
        return [f.name for f in cls._meta.get_fields() if not f.is_relation
                and f.name != 'id']

    @staticmethod
    def convert_choice_to_field(choice):
        """Makes choice a field by changing the text

        :param choice: Entry to make a field
        :return: (str) `choice` made uppercase and replacing spaces with '_'
        """
        return choice.upper().replace(' ', '_')



    @classmethod
    def _setup_model_object(_, cls, attrs):
        kwargs = {}
        for fld in cls._meta.get_fields():
            if fld.name == 'id' or fld.many_to_many:
                continue
            elif fld.name.startswith("cc_"):
                if fld.name == "cc_id":
                    # If object already exists in DB, return None
                    if cls.objects.filter(cc_id=attrs[fld.name[3:]]):
                        return
                kwargs[fld.name] = attrs[fld.name[3:]]
            elif hasattr(fld, 'choices') and fld.choices:
                # Map uppercase field names to DB 2-letter codes
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
        # Return a new model object
        return cls(**kwargs)

    @transaction.atomic
    def combine_cclist_json_into_db(self, cclist_json):
        """Creates a `model.ConstantContactList` and saves it to the local DB

        :param cclist_json: (dict) JSON with ConstantContact list information
        :return: None
        """
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
            # Set up fields for Contact
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
            # Initialize new Contact object
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
        """Initialize a `models.Phone` from a sting and save to local DB

        :param phone_num: (str) A sting representing a phone number
        :param newContact: (`models.Contact`) The new Contact to add the phone
            object to.
        :param phfld: (`django.db.models.fields.related.ManyToManyField`) The
            field (home_phone, cell_phone, work_phone, or fax) that the
            `phone_num` string will be added to in `newContact`
        :return: None, but a new Phone object should be added to the local DB
        """
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

    @transaction.atomic
    def save_for_remediation(self, contact, json_entry):
        """Make a new `models.RequiringRemediation` object and save to local DB

        :param contact: (`models.Contact`) Entry with bad field
        :param json_entry: (dict) Fields that are incorrect matched to bad data
        :return: None, local DB is updated
        """
        rr = RequiringRemediation(contact_pk=contact, fields=json_entry)
        rr.save()

    @staticmethod
    def check_for_contact_in_db(email=None, fname=None, lname=None):
        email_matches = []
        if email:
            email_matches = Contact.objects.filter(
                email_addresses__email_address=email
            )

        results = {}
        fname_objs = []
        lname_objs = []
        if fname or lname:
            if fname:
                fname_objs = Contact.objects.filter(first_name=fname.capitalize())

            if lname:
                lname_objs = Contact.objects.filter(last_name=lname.capitalize())

            for fn in fname_objs:
                if fn in lname_objs:
                    results[fn.id] = 50
                else:
                    results[fn.id] = 5

            for ln in lname_objs:
                if ln.id not in results:
                    results[ln.id] = 10

        for em in email_matches:
            if em.id in results:
                results[em.id] += 100
            else:
                results[em.id] = 100

        return results

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
    def combine_contacts_into_db(self, update_web_interface=False):
        """Adds all contacts and lists available to `self` to local DB

        This is the core of the "combining" process. After lists and contacts
        have been "harvested" (ie. downloaded or read from JSON file) from
        ConstantContact and added to `self.cclists` and `self.contacts`,
        respectively; this function will make the relevant Django ORM models
        and then save each to the local DB

        :param update_web_interface: (str) If true, this function will generate
            a dictonary object with 'processed' and 'total' keys, matched to
            the number of Contact iterations completed and the number of
            Contact objects yet to be added (there usually are far fewer lists
            than contacts, so these aren't included)

            If not true, calls `utils.updt` to fulfill the same purpose as
            updating the web interface, but to the console instead
        :return: None, but should update local DB
        """
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
                bad_m2m_entry = None
                bad_phone_entry = None
                updatingContact = False

                # Check if Contact is already in DB, and act appropriately
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

                # Setup and save connections from this contact to various lists
                # (ie. `models.UserStatusOnCCList` objects)
                self._save_ustat_objects(contact, newContact, updatingContact)

                # Setup and combine phone numbers for contact
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
                        bad_phone_entry = {phfld:contact.get(phfld)}

                # Setup and combine many to many fields for contact
                for cls_obj, m2m in non_phone_or_cclist_m2m:
                    for m2mattrs in contact.get(m2m):
                        try:
                            newContact = self._combine_m2m_field_into_db(
                                cls_obj, m2mattrs, newContact, m2m
                            )
                        except DataError:
                            bad_m2m_entry = {newContact.cc_id: m2mattrs}

                # Set up and save notes about contact
                self._combine_notes_into_db(contact.get('notes'), newContact)

                # Save new contact to database
                newContact.save()

                # Setup and save any entries which will need to be remediated
                # by a human operator
                if bad_m2m_entry:
                    self.bad_m2m.setdefault(newContact.cc_id, [])\
                        .append(bad_m2m_entry)
                    self.save_for_remediation(newContact, bad_m2m_entry)

                if bad_phone_entry:
                    self.bad_phone_nums.setdefault(newContact.cc_id, [])\
                        .append(bad_phone_entry)
                    self.save_for_remediation(newContact, bad_phone_entry)

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
            except: # Keep calm, fuck this, and carry on
                self.logger.exception(f"Exception on contact #{c_i}...skipping...")
            finally: # Update dem progress trackers
                if update_web_interface:
                    yield {'processed': processed, 'total': len(self.contacts)}
                    processed += 1
                else:
                    processed = self._continue_combine(processed)

        # Note time taken to complete, for log
        end_time = datetime.datetime.now()
        total_time = (end_time - begin_time).total_seconds()
        if update_web_interface:
            yield {'processed': len(self.contacts), 'total': len(self.contacts)}
        else:
            updt(len(self.contacts), len(self.contacts))
        self.logger.info(
            f"Combined time to process '{processed}' contacts: "
            f"{total_time // 60} minutes and {total_time % 60} seconds."
         )

    def publish_contact(self, contact, cclists, api_uri='/v2/contacts',
                        check_api=True, dont_update=True):
        params = dict(
            api_key=self.api_key
        )
        url = f"{BASE_URI}{api_uri}"

        if check_api:
            for email in contact.email_addresses.all():
                params['email'] = email.email_address
                r = requests.get(url, params=params, headers=self.headers)

                # In case of UH-OH!
                if r.status_code >= HTTP_FAIL_THRESHOLD:
                    return self._report_cc_api_request_fail(r)

                # Pick them tasty contacts
                rjson = r.json()
                if rjson.get('results') and dont_update:
                    self.logger.warning(
                        f"'dont_update' == {dont_update} and contact exists: "
                        f"{rjson.get('results')}, quitting."
                    )
                    return

        params["action_by"] = "ACTION_BY_OWNER"
        data = self.convert_contact_to_json(contact, cclists)
        r = requests.post(url, params=params,
                          data=json.dumps(data), headers=self.headers)

        # In case of UH-OH!
        if r.status_code >= HTTP_FAIL_THRESHOLD:
            return self._report_cc_api_request_fail(r)
        else:
            self.logger.info(f"{r.reason} ID#: {r.content.get('id')}")
        return

    @staticmethod
    def convert_contact_to_json(contact, cclists=None):
        address_type_map = {
            models.BUSINESS: "BUSINESS",
            models.PERSONAL: "PERSONAL"
        }
        cstatus_map = {
            models.CONFIRMED: "CONFIRMED",
            models.NO_CONFIRMATION_REQUIRED: "NO_CONFIRMATION_REQUIRED",
            models.UNCONFIRMED: "UNCONFIRMED"
        }
        action_map = {
            models.ACTION_BY_OWNER: "ACTION_BY_OWNER",
            models.ACTION_BY_VISITOR: "ACTION_BY_VISITOR"
        }
        status_map = {
            models.ACTIVE: "ACTIVE",
            models.UNCONFIRMED: "UNCONFIRMED",
            models.OPTOUT: "OPTOUT",
            models.REMOVED: "REMOVED",
            models.NON_SUBSCRIBER: "NON_SUBSCRIBER",
        }
        list_status_map = {
            models.ACTIVE: "ACTIVE",
            models.HIDDEN: "HIDDEN"
        }

        vals = {"cell_phone": "", "work_phone": "", "home_phone": "", "fax": ""}
        for val in vals.keys():
            rep = getattr(contact, val)
            if rep.first():
                vals[val] = rep.first().__str__()

        cclists = contact.cc_lists.all() if not cclists else cclists

        return {
            'addresses': [{
                'address_type': address_type_map[address.address_type],
                'city': address.city,
                'id': "" if not address.cc_id else address.cc_id,
                'line1': address.line1,
                'line2': address.line2,
                'line3': address.line3,
                'postal_code': address.postal_code,
                'state': address.state,
                'state_code': address.state_code,
                'sub_postal_code': address.sub_postal_code}
                for address in contact.addresses.all()
            ],
            'cell_phone': vals["cell_phone"],
            'work_phone': vals["work_phone"],
            'home_phone': vals["home_phone"],
            'company_name': contact.company_name,
            'confirmed': contact.confirmed,
            'created_date': contact.created_date.isoformat(),
            'email_addresses': [{
                'confirm_status': cstatus_map[em.confirm_status],
                'email_address': em.email_address,
                'id': "" if not em.cc_id else em.cc_id,
                'opt_in_date':
                    "" if not em.opt_in_date else em.opt_in_date.isoformat(),
                'opt_in_source':
                    "" if not em.opt_in_source else action_map[em.opt_in_source],
                'status': status_map[em.status]}
                for em in contact.email_addresses.all()
            ],
            'fax': vals["fax"],
            'first_name': contact.first_name,
            'last_name': contact.last_name,
            'job_title': contact.job_title,
            'lists': [{
                'id': l.id,
                'status': list_status_map[l.status]}
                for l in cclists
            ],
            'modified_date':
                "" if not contact.cc_modified_date else contact.cc_modified_date.isoformat(),
            'notes': [{
                'created_date': note.created_date.isoformat(),
                'id': '' if not note.cc_id else note.cc_id,
                'modified_date': note.modified_date.isoformat(),
                'note': note.note}
                for note in contact.notes.all()
            ],
            'prefix_name': contact.prefix_name,
            'source': contact.source,
            'source_details': "Crimson Star Software's Data Combine",
            'status':
                "ACTIVE" if not contact.status else status_map[contact.status]
        }



if __name__ == '__main__':
    dc = DataCombine()
    dc.read_constantcontact_objects_from_json()
    dc.combine_contacts_into_db()
