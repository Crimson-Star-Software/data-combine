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
import os
import re


class TestDataCombine(TestCase):
    def setUp(self):
        self.dc = DataCombine(logfile='dcombine_test.log')
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

    def tearDown(self):
        if os.path.isfile(self.log_loc):
            os.remove(self.log_loc)

        ConstantContactList.objects.all().delete()
