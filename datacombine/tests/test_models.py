from django.test import TestCase
from datacombine import models as dcmodels
from collections import namedtuple
from django.core.exceptions import FieldError
import re


Match = namedtuple("Match", ["object", "regex", "match"])


class PhoneTestCase(TestCase):
    def setUp(self):
        dcmodels.Phone.objects.create(area_code="407", number="5559999")
        dcmodels.Phone.objects.create(number="1234567")
        dcmodels.Phone.objects.create(number="3141592", extension="48")
        dcmodels.Phone.objects.create(
            area_code="904", number="3141592", extension="2"
        )

    def test_str(self):
        all_phone_nums = dcmodels.Phone.objects.all()
        matches = []
        for num in all_phone_nums:
            regex_str = ""
            if getattr(num, 'area_code', None):
                regex_str += "\([0-9]{3}\)\-"
            regex_str += "[0-9]{3}\-[0-9]{4}"
            if getattr(num, "extension", None):
                regex_str += " x [0-9]+"
            match = True if re.match(regex_str, str(num)) else False
            matches.append(Match(num, regex_str, match))
        ms = all([m.match for m in matches])
        if not ms:
            for m in matches:
                if not m.match:
                    print(f"Failure on {m.object} with {m.regex}")
        self.assertTrue(ms)

    def test_phone_create_from_str_1_block_7_digit(self):
        ph = dcmodels.Phone()
        ph.create_from_str("1234567")
        self.assertEqual(ph.number, "1234567")

    def test_phone_create_from_str_2_block_7_digit(self):
        ph = dcmodels.Phone()
        ph.create_from_str("123-4567")
        self.assertEqual(ph.number, "1234567")

    def test_phone_create_from_str_2_block_bad_7_digit(self):
        ph = dcmodels.Phone()
        ph.create_from_str("12-34567")
        self.assertEqual(ph.number, "1234567")

    def test_phone_create_from_str_3_block_bad_7_digit(self):
        ph = dcmodels.Phone()
        ph.create_from_str("(123)-45-67")
        self.assertEqual(ph.number, "1234567")

    def test_phone_create_from_average_str(self):
        ph = dcmodels.Phone()
        ph.create_from_str("(407)-666-9999")
        self.assertTrue(ph.area_code == "407" and ph.number == "6669999")

    def test_phone_create_from_average_str_with_ext(self):
        ph = dcmodels.Phone()
        ph.create_from_str("(407)-666-9999 x 49")
        self.assertTrue(ph.area_code == "407" and ph.number == "6669999"\
               and ph.extension == "49")

    def test_phone_create_from_str_too_few_numbers(self):
        ph = dcmodels.Phone()
        with self.assertRaises(FieldError):
            ph.create_from_str("1")

    def test_phone_create_from_str_null(self):
        ph = dcmodels.Phone()
        ph.create_from_str("")
        self.assertTrue(ph.area_code == ph.number == ph.extension == None)

    def test_null_phone_is_none(self):
        ph = dcmodels.Phone()
        ph.create_from_str("")
        self.assertTrue(ph == None)

    def tearDown(self):
        dcmodels.Phone.objects.all().delete()


class ContactTestCase(TestCase):
    def setUp(self):
        dcmodels.Phone.objects.create(area_code="407", number="5559999")
        dcmodels.Phone.objects.create(number="1234567")
        dcmodels.Phone.objects.create(number="3141592", extension="48")
        dcmodels.Phone.objects.create(
            area_code="904", number="3141592", extension="2"
        )
        dcmodels.EmailAddress.objects.create(
            confirm_status=dcmodels.NO_CONFIRMATION_REQUIRED,
            email_address='pastor@stnerp.org',
            cc_id='a09d1c20-6aac-11e3-8c26-982bcb740129',
            opt_in_date='2011-06-27T18:47:16.000Z',
            opt_in_source=dcmodels.ACTION_BY_OWNER,
            status=dcmodels.ACTIVE
        )

    def test_get_email_addresses(self):
        self.assertTrue(len(dcmodels.EmailAddress.objects.all()) == 1)
