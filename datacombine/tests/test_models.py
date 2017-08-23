from django.test import TestCase
from datacombine.models import Phone
from collections import namedtuple
from django.core.exceptions import FieldError
import re


Match = namedtuple("Match", ["object", "regex", "match"])


class PhoneTestCase(TestCase):
    def setUp(self):
        Phone.objects.create(area_code="407", number="5559999")
        Phone.objects.create(number="1234567")
        Phone.objects.create(number="3141592", extension="48")
        Phone.objects.create(area_code="904", number="3141592", extension="2")

    def test_str(self):
        all_phone_nums = Phone.objects.all()
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
        ph = Phone()
        ph.create_from_str("1234567")
        self.assertEqual(ph.number, "1234567")

    def test_phone_create_from_str_2_block_7_digit(self):
        ph = Phone()
        ph.create_from_str("123-4567")
        self.assertEqual(ph.number, "1234567")

    def test_phone_create_from_str_2_block_bad_7_digit(self):
        ph = Phone()
        ph.create_from_str("12-34567")
        self.assertEqual(ph.number, "1234567")

    def test_phone_create_from_str_3_block_bad_7_digit(self):
        ph = Phone()
        ph.create_from_str("(123)-45-67")
        self.assertEqual(ph.number, "1234567")

    def test_phone_create_from_average_str(self):
        ph = Phone()
        ph.create_from_str("(407)-666-9999")
        self.assertTrue(ph.area_code == "407" and ph.number == "6669999")

    def test_phone_create_from_average_str_with_ext(self):
        ph = Phone()
        ph.create_from_str("(407)-666-9999 x 49")
        self.assertTrue(ph.area_code == "407" and ph.number == "6669999"\
               and ph.extension == "49")

    def test_phone_create_from_str_too_few_numbers(self):
        ph = Phone()
        with self.assertRaises(FieldError):
            ph.create_from_str("1")

    def test_phone_create_from_str_null(self):
        ph = Phone()
        ph.create_from_str("")
        self.assertTrue(ph.area_code == ph.number == ph.extension == None)
