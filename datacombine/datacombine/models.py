from django.db import models
from django.core.exceptions import FieldError
import re


class PhoneField(models.Field):
    def __init__(self, phone_num):
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
                self.area_code = nums[0]
                self.number = nums[1]
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

class Contact(models.model):
    cell_phone = PhoneField()
    home_phone = PhoneField()
