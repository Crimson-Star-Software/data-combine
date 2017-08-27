from django.test import TestCase
from datacombine.data_combine import DataCombine
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

    def test_combine_cclist_json_into_db_already_in_db(self):
        self.dc.combine_cclist_json_into_db(self.yaya_orl_json)
        inlog = self.check_log_for(self.cclist_already_exists_re)
        self.assertTrue(inlog)

    def tearDown(self):
        if os.path.isfile(self.log_loc):
            os.remove(self.log_loc)

        ConstantContactList.objects.all().delete()
