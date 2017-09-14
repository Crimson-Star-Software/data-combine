from django.db import models
from django.core.exceptions import FieldError
import re


UNCONFIRMED = "UN"
ACTIVE = "AC"
OPTOUT = "OP"
REMOVED = "RE"
NON_SUBSCRIBER = "NO"
HIDDEN = 'HI'
STATUS_CHOICES = (
    (UNCONFIRMED, "Unconfirmed"),
    (ACTIVE, "Active"),
    (OPTOUT, "Optout"),
    (REMOVED, "Removed"),
    (NON_SUBSCRIBER, "Non Subscriber")
)
CONFIRMED = "CO"
NO_CONFIRMATION_REQUIRED="NC"
CONFIRM_STATUS_CHOICES = (
    (CONFIRMED, "Confirmed"),
    (NO_CONFIRMATION_REQUIRED, "No Confirmation Required")
)
ACTION_BY_OWNER = "AO"
ACTION_BY_VISITOR = "AV"

OPT_IN_STATUS_CHOICES = (
    (ACTION_BY_OWNER, "Action by Owner"),
    (ACTION_BY_VISITOR, "Action by Visitor")
)

BUSINESS = "BU"
PERSONAL = "PE"
ADDRESS_TYPE_CHOICES = (
    (BUSINESS, "Business"),
    (PERSONAL, "Personal")
)
LIST_STATUS_CHOICES = (
    (ACTIVE, 'Active'),
    (HIDDEN, 'Hidden')
)


class Phone(models.Model):
    area_code = models.CharField(max_length=3, null=True)
    number = models.CharField(max_length=7)
    extension = models.CharField(max_length=7, null=True)

    def __str__(self):
        return "{0}{1}-{2}{3}".format(
            "(" + self.area_code + ")-" if self.area_code else "",
            self.number[:3],
            self.number[3:],
            " x "+self.extension if self.extension else ""
        )

    def __eq__(self, other):
        if other is None:
            other = Phone()
            other.create_from_str("")
        elif not hasattr(other, "area_code"):
            return False
        return self.extension == other.extension and\
               self.number == other.number and\
               self.area_code == other.area_code

    @classmethod
    def is_phone_in_db(cls, phobj):
        return cls.objects.filter(
            area_code=phobj.area_code,
            number=phobj.number,
            extension=phobj.extension
        )

    def create_from_str(self, phone_num):
        nums = re.findall("([0-9]+)", phone_num)
        if len(nums) == 0:
            self.area_code = self.number = self.extension = None
        elif len(nums) == 1:
            self.area_code, self.number, self.extension = self._parsenums(nums[0])
        elif len(nums) == 2:
            if len(nums[0]) != 3 or len(nums[1]) != 4:
                self.area_code, self.number, self.extension = self._parsenums(
                    nums[0] + nums[1]
                )
            else:
                self.number = nums[0] + nums[1]
        elif len(nums) == 3:
            if len(nums[0]) != 3 or len(nums[1]) != 3 or len(nums[2]) != 4:
                self.area_code, self.number, self.extension = self._parsenums(
                    nums[0] + nums[1] + nums[2]
                )
            else:
                self.area_code = nums[0]
                self.number = nums[1] + nums[2]
                self.extension = None
        elif len(nums) == 4:
            if len(nums[0]) != 3 or len(nums[1]) != 3 or len(nums[2]) != 4:
                self.area_code, self.number, self.extension = self._parsenums(
                    nums[0] + nums[1] + nums[2] + nums[3]
                )
            else:
                self.area_code = nums[0]
                self.number = nums[1] + nums[2]
                self.extension = nums[3]
        else:
            raise FieldError(
                "There is a problem with too many number groups in "
                f"{phone_num}...maybe there is more than 1 set of numbers"
            )

        for field in Phone._meta.get_fields():
            if field.name is 'id':
                continue
            num = getattr(self, field.name)
            if num and len(num) > field.max_length:
                raise FieldError(
                    f"'{field.name}' is too long; {len(num)} > "
                    f"{field.max_length}"
                )

    def _parsenums(self, nums):
        if len(nums) < 7 or 7 < len(nums) < 10:
            raise FieldError(
                f"Too few numbers to be a phone number for {nums}, "
                f"length={len(nums)}"
            )
        else:
            if len(nums) == 7:
                return (None, nums, None)
            else:
                return (nums[:3], nums[3:10], nums[10:])


class Address(models.Model):
    address_type = models.CharField(max_length=2, choices=ADDRESS_TYPE_CHOICES)
    city = models.CharField(max_length=32, null=True)
    country_code = models.CharField(max_length=2, null=True)
    cc_id = models.CharField(max_length=36, unique=True)
    # TODO: Do we need three lines?
    line1 = models.CharField(max_length=100, null=True)
    line2 = models.CharField(max_length=100, null=True)
    line3 = models.CharField(max_length=100, null=True)
    postal_code = models.CharField(max_length=10, null=True)
    state = models.CharField(max_length=20, null=True)
    state_code = models.CharField(max_length=2, null=True)
    sub_postal_code = models.CharField(max_length=20, null=True)

    def __str__(self):
        lines = [self.line1, self.line2, self.line3]
        return "{0} {1}, {2}, {3}".format(
            ", ".join([line for line in lines if line]),
            self.city,
            self.state,
            self.country_code
        )


class EmailAddress(models.Model):
    confirm_status = models.CharField(max_length=3,
                                      choices=CONFIRM_STATUS_CHOICES)
    cc_id = models.CharField(max_length=36, unique=True)
    status = models.CharField(max_length=2, choices=STATUS_CHOICES)
    opt_in_date = models.DateTimeField(null=True)
    opt_out_date = models.DateTimeField(null=True)
    email_address = models.EmailField()
    opt_in_source = models.CharField(max_length=2,
                                     choices=OPT_IN_STATUS_CHOICES, null=True)

    def __str__(self):
        return self.email_address


class ConstantContactList(models.Model):
    cc_id = models.IntegerField(unique=True)
    status = models.CharField(max_length=2, choices=LIST_STATUS_CHOICES)
    name = models.CharField(max_length=48)
    created_date = models.DateTimeField()
    modified_date = models.DateTimeField()

    def __str__(self):
        return self.name

    def __eq__(self, other):
        return int(self.cc_id) == int(other.cc_id) and self.name == other.name

class UserStatusOnCCList(models.Model):
    cclist = models.ForeignKey('ConstantContactList')
    user = models.ForeignKey('Contact')
    status = models.CharField(max_length=2, choices=LIST_STATUS_CHOICES)


class Note(models.Model):
    created_date = models.DateTimeField()
    cc_id = models.CharField(max_length=36, unique=True)
    modified_date = models.DateTimeField()
    note = models.TextField()
    contact = models.ForeignKey(to='Contact', related_name="notes", null=True)

    def __str__(self):
        return "{0}: {1}".format(self.cc_id, self.note[:25])


class Contact(models.Model):
    cell_phone = models.ManyToManyField(Phone, related_name='+')
    home_phone = models.ManyToManyField(Phone, related_name='+')
    work_phone = models.ManyToManyField(Phone, related_name='+')
    confirmed = models.NullBooleanField(null=True)
    addresses = models.ManyToManyField(Address)
    company_name = models.CharField(max_length=100, null=True)
    created_date = models.DateTimeField()
    email_addresses = models.ManyToManyField(EmailAddress)
    fax = models.ManyToManyField(Phone, related_name='+')
    first_name = models.CharField(max_length=50, null=True)
    middle_name = models.CharField(max_length=50, null=True)
    last_name = models.CharField(max_length=50, null=True)
    cc_id = models.IntegerField(unique=True)
    cc_lists = models.ManyToManyField(ConstantContactList,
                                      through=UserStatusOnCCList)
    cc_modified_date = models.DateTimeField()
    prefix_name = models.CharField(max_length=10, null=True)
    job_title = models.CharField(max_length=50, null=True)
    source = models.CharField(max_length=50, null=True)
    status = models.CharField(max_length=2, choices=STATUS_CHOICES, null=True)

    def __str__(self):
        return "{0}{1}{2}".format(
            self.first_name,
            " " if not self.middle_name else " {} ".format(self.middle_name),
            self.last_name
        )

    @staticmethod
    def convert_status_str_to_code(statstr):
        for code, stat in STATUS_CHOICES:
            if not statstr:
                return ""
            if statstr.upper()[:2] == code:
                return code
