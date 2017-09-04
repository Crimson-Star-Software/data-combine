from django.test import TestCase
from datacombine.data_combine import DataCombine
from django.db import IntegrityError
from datacombine.models import (
    Contact,
    Phone,
    EmailAddress,
    ConstantContactList,
    Note,
    Address,
    UserStatusOnCCList
)
import logging
import os
import re


HERE = os.path.join(os.getcwd(), "tests")
test_pth = os.path.join(HERE, "testobj.json")

class TestDataCombine(TestCase):
    def setUp(self):
        self.dc = DataCombine(loglvl=logging.DEBUG, logfile='dcombine_test.log')
        self.yaya_orl_json = dict(
            created_date='2013-08-04T23:38:45.000Z',
            cc_id='101',
            modified_date='2013-12-05T21:33:39.000Z',
            name='YAYA Florida - Orlando',
            status="HI"
        )
        self.yaya_co_json = dict(
            created_date='2013-08-04T01:07:24.000Z',
            id='50',
            modified_date='2013-11-19T14:39:32.000Z',
            name='YAYA Colorado',
            status="HI"
        )
        self.yaya_nc_json = dict(
            created_date='2013-08-04T02:59:05.000Z',
            id='71',
            modified_date='2013-11-19T14:39:32.000Z',
            name='YAYA North Carolina',
            status='HI'
        )
        self.yaya_sc_json = dict(
            created_date='2013-08-04T19:18:23.000Z',
            id='79',
            modified_date='2013-11-19T14:39:32.000Z',
            name='YAYA North Carolina',
            status='HI'
        )

        self.jop_de_ruyterzoon = dict(
            confirmed=False,
            company_name="Crimson Star Software Collective",
            first_name="Jop",
            middle_name="Peter",
            last_name="De Ruyterzoon",
            id='1983',
            modified_date="2015-03-16T17:41:31.000Z",
            created_date="2015-03-16T17:41:31.000Z",
            prefix_name="Dr",
            job_title="Commissar of Data",
            status="ACTIVE",
            source="Site Owner"
        )

        self.nathanial_conolly = dict(
            confirmed=False,
            company_name="Crimson Star Software Collective",
            first_name="Nathanial",
            middle_name="James",
            last_name="Conolly",
            id='1985',
            modified_date="2016-04-16T17:41:31.000Z",
            created_date="2016-04-16T17:41:31.000Z",
            prefix_name="Mr",
            job_title="Commissar of Cyber Security",
            status="ACTIVE",
            source="Site Owner"
        )

        self.yaya_orl_list = ConstantContactList(**self.yaya_orl_json)
        self.yaya_orl_list.save()

        # Make expected cclist json
        self.yaya_orl_json['id'] = self.yaya_orl_json['cc_id']
        del self.yaya_orl_json['cc_id']

        # Setup log stuff
        rf = self.dc.logger.handlers[0]
        self.log_loc = rf.baseFilename

        # Make regex for expected log entries
        self.cclist_already_exists_re = re.compile(
            "([0-9]{4}-[0-9]{2}-[0-9]{2})[\s\d\:\,]+- "
            "datacombine.data_combine - DEBUG - List named 'YAYA"
            " Florida - Orlando' already found in db skipping..."
        )

    def check_log_for(self, regex):
        with open(self.log_loc, 'r') as lf:
            for line in lf.readlines():
                if regex.search(line):
                    return True
        return False

    def test_combine_cclist_json_into_db(self):
        self.dc.combine_cclist_json_into_db(self.yaya_co_json)
        is_colorado_in_the_house = ConstantContactList.objects.filter(
            name="YAYA Colorado"
        )
        self.assertTrue(is_colorado_in_the_house)

    def test_combine_cclist_json_into_db_already_in_db(self):
        self.dc.combine_cclist_json_into_db(self.yaya_orl_json)
        inlog = self.check_log_for(self.cclist_already_exists_re)
        self.assertTrue(inlog)

    def test_combine_cclist_json_into_db_save_points(self):
        self.dc.combine_cclist_json_into_db(self.yaya_nc_json)
        try:
            # Next line should provoke IntegrityError
            self.yaya_sc_json['id'] = self.yaya_nc_json['id']
            self.dc.combine_cclist_json_into_db(self.yaya_sc_json)
        except IntegrityError:
            is_northcarolina_in_the_house = ConstantContactList.objects.filter(
                name="YAYA North Carolina"
            )
            self.assertTrue(is_northcarolina_in_the_house)

    def test_iso_8601_format_checking(self):
        bad_iso_json = dict(
            created_date='2013-08-04 19:18:23',
            id='-1',
            modified_date='2013-11-19',
            name='YAYA Bad Iso',
            status='HI'
        )
        self.assertRaises(
            TypeError,
            self.dc.combine_cclist_json_into_db(bad_iso_json)
        )

    def test_get_init_values_for_model_contacts(self):
        init_values = set(self.dc.get_init_values_for_model(Contact))
        expected_values = {
            "confirmed",
            "company_name",
            "created_date",
            "first_name",
            "middle_name",
            "last_name",
            "cc_id",
            "cc_modified_date",
            "prefix_name",
            "job_title",
            "source",
            "status"
        }
        self.assertEqual(init_values.difference(expected_values), set())

    def test_get_init_values_for_model_phone(self):
        init_values = set(self.dc.get_init_values_for_model(Phone))
        expected_values = {
            "area_code",
            "number",
            "extension"
        }
        self.assertEqual(init_values.difference(expected_values), set())

    def test_get_init_values_for_model_address(self):
        init_values = set(self.dc.get_init_values_for_model(Address))
        expected_values = {
            "address_type",
            "city",
            "country_code",
            "cc_id",
            "line1",
            "line2",
            "line3",
            "postal_code",
            "state",
            "state_code",
            "sub_postal_code"
        }
        self.assertEqual(init_values.difference(expected_values), set())

    def test_get_init_values_for_model_email_address(self):
        init_values = set(self.dc.get_init_values_for_model(EmailAddress))
        expected_values = {
            "confirm_status",
            "cc_id",
            "status",
            "opt_in_date",
            "opt_out_date",
            "email_address",
            "opt_in_source"
        }
        self.assertEqual(init_values.difference(expected_values), set())

    def test_get_init_values_for_model_constantcontactlist(self):
        init_values = set(
            self.dc.get_init_values_for_model(ConstantContactList)
        )
        expected_values = {
            "cc_id",
            "status",
            "name",
            "created_date",
            "modified_date"
        }
        self.assertEqual(init_values.difference(expected_values), set())

    def test_get_init_values_for_model_userstatusoncclist(self):
        init_values = set(
            self.dc.get_init_values_for_model(UserStatusOnCCList)
        )
        expected_values = {"status"}
        self.assertEqual(init_values.difference(expected_values), set())

    def test_get_init_values_for_model_notes(self):
        init_values = set(self.dc.get_init_values_for_model(Note))
        expected_values = {
            "created_date",
            "modified_date",
            "cc_id",
            "note"
        }
        self.assertEqual(init_values.difference(expected_values), set())

    def test__initial_contact_setup_from_json(self):
        jop = self.dc._initial_contact_setup_from_json(self.jop_de_ruyterzoon)
        self.assertTrue(Contact.objects.filter(first_name="Jop", cc_id=1983))

    def test_combine_phone_number_into_db(self):
        nate = self.dc._initial_contact_setup_from_json(self.nathanial_conolly)
        self.dc.combine_phone_number_into_db(
            "(904)-712-1983", nate, "work_phone"
        )
        nate_work_num = Phone.objects.filter(area_code="904", number="7121983")
        self.assertEqual(nate_work_num.first(), nate.work_phone.first())

        # Delete Nate
        nate.delete()

    def test_combine_phone_number_into_db_multiple(self):
        nate = self.dc._initial_contact_setup_from_json(self.nathanial_conolly)
        nates_home_num = ["(386)-101-2983x42", "(904)-111-3983"]
        for num in nates_home_num:
            self.dc.combine_phone_number_into_db(num, nate, "home_phone")
        hp1 = Phone.objects.filter(
            area_code="386", number="1012983", extension="42"
        ).first()
        hp2 = Phone.objects.filter(area_code="904", number="1113983").first()

        self.assertIn(hp1, nate.home_phone.all()) and\
            self.assertIn(hp2, nate.home_phone.all())

        # Delete Nate
        nate.delete()

    def test__combine_m2m_field_into_db_addresses(self):
        nate = self.dc._initial_contact_setup_from_json(self.nathanial_conolly)
        aid_1 = '83d1f0e0-611c-11e3-d3ad-782bcb740129'
        aid_2 = '99d17ce0-aaac-11e3-dead-cafecb740129'
        nate_addresses = [{
            'address_type': 'PERSONAL',
            'city': 'Denver',
            'country_code': 'us',
            'id': aid_1,
            'line1': '1917 Petrograd Dr.',
            'line2': '',
            'line3': '',
            'postal_code': '5643',
            'state': 'Denver',
            'state_code': 'CO',
            'sub_postal_code': ''
        },{
            'address_type': 'BUSINESS',
            'city': 'Denver',
            'country_code': 'us',
            'id': aid_2,
            'line1': '2017 Retrograde Rd.',
            'line2': '',
            'line3': '',
            'postal_code': '5622',
            'state': 'Denver',
            'state_code': 'CO',
            'sub_postal_code': ''
        }]
        for nate_address in nate_addresses:
            self.dc._combine_m2m_field_into_db(
                Address, nate_address, nate, "addresses"
            )
        nate_aids = [ad.cc_id for ad in nate.addresses.all()]
        self.assertIn(aid_1, nate_aids)
        self.assertIn(aid_2, nate_aids)

        # Delete Nate
        nate.delete()

    def test__combine_m2m_field_into_db_email_addresses(self):
        nate = self.dc._initial_contact_setup_from_json(self.nathanial_conolly)
        eid_1 = 'deadbeef-99d9-11e3-83e7-782aba740721'
        eid_2 = 'f13eff2f1-99d9-11e3-83e7-782bab73079'
        email_addresses = [{
            'confirm_status': 'NO_CONFIRMATION_REQUIRED',
            'email_address': 'nconolly@ira.org',
            'id': eid_1,
            'opt_in_date': '2011-06-24T19:32:49.000Z',
            'opt_in_source': 'ACTION_BY_OWNER',
            'status': 'ACTIVE'
        },{
            'confirm_status': 'CONFIRMED',
            'email_address': 'nconolly@ucf.edu',
            'id': eid_2,
            'opt_in_date': '2011-06-24T19:32:49.000Z',
            'opt_in_source': 'ACTION_BY_VISITOR',
            'status': 'ACTIVE'
        }]

        for email in email_addresses:
            self.dc._combine_m2m_field_into_db(
                EmailAddress, email, nate, "email_addresses"
            )

        nate_eids = [em.cc_id for em in nate.email_addresses.all()]
        self.assertIn(eid_1, nate_eids)
        self.assertIn(eid_2, nate_eids)

        # Delete Nate
        nate.delete()

    def test__combine_notes_into_db(self):
        nate = self.dc._initial_contact_setup_from_json(self.nathanial_conolly)
        nid_1 = '6f12eae0-6807-11e7-af14-d4ae529a826e'
        nid_2 = '6f12eae0-6807-11e7-dead-d4ae529a826e'
        notes = [{
            'created_date': '2017-07-13T20:11:19.000Z',
            'id': nid_1,
            'modified_date': '2017-07-13T20:11:19.000Z',
            'note': 'BLAH BLAH'
        },{
            'created_date': '2017-07-19T20:11:19.000Z',
            'id': nid_2,
            'modified_date': '2017-07-19T20:11:19.000Z',
            'note': 'Good point!'
        }]

        self.dc._combine_notes_into_db(notes, nate)

        nates_notes = [nt.cc_id for nt in nate.notes.all()]
        self.assertIn(nid_1, nates_notes)
        self.assertIn(nid_2, nates_notes)

        # Delete Nate
        nate.delete()

    def test_read_constantcontacts_from_json_nothing_in_dcobj(self):
        dcTT, dcTF, dcFT, dcFF = (DataCombine(), DataCombine(),
                                  DataCombine(), DataCombine())

        dcTT.read_constantcontact_objects_from_json(test_pth)
        dcTF.read_constantcontact_objects_from_json(test_pth, True, False)
        dcFT.read_constantcontact_objects_from_json(test_pth, False, True)
        dcFF.read_constantcontact_objects_from_json(test_pth, False, False)
        self.assertTrue(
            dcTT.contacts == dcTF.contacts == dcFT.contacts == dcFF.contacts
        )
        self.assertTrue(
            dcTT.cclists == dcTF.cclists == dcFT.cclists == dcFF.cclists
        )

    def test_read_constantcontacts_lists_from_json_merge(self):
        dc = DataCombine()
        dc2 = DataCombine()
        dc.cclists = [{
            "contact_count": 7,
            "created_date": "2014-10-10T16:33:14.000Z",
            "id": "1648",
            "modified_date": "2014-10-10T16:33:14.000Z",
            "name": "YAYA_Netherlands",
            "status": "HIDDEN"
        }]
        dc.read_constantcontact_objects_from_json(test_pth,
                                                  override_lists=False)
        dc2.read_constantcontact_objects_from_json(test_pth)
        self.assertListEqual(dc.cclists, dc2.cclists)

    def tearDown(self):
        if os.path.isfile(self.log_loc):
            os.remove(self.log_loc)

        ConstantContactList.objects.all().delete()
        Contact.objects.all().delete()
