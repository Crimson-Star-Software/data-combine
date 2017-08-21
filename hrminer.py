#!/usr/bin/env python
import json
import logging
import os
import re
import sys

from IPython import embed
import pandas as pd
import numpy as np

tagre = re.compile("Tags:\s+\n(\s+-\s+[0-9A-Za-z\s]+\n)+", re.MULTILINE)
idre = re.compile("- ID: ([0-9]+)", re.MULTILINE)
namere = re.compile(" Name: ([\s\w\&\.\-\\\/\(\)\'\"\!\,\;\#\@\+]+)\n", re.MULTILINE)
email_str = r"(^[-!#$%&'*+/=?^_`{}|~0-9A-Z]+(\.[-!#$%&'*+/=?^_`{}|~0-9A-Z]+)*"
r'|^"([\001-\010\013\014\016-\037!#-\[\]-\177]|\\[\001-\011\013\014\016-\177])*"'
r')@((?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)$)'  # domain
r'|\[(25[0-5]|2[0-4]\d|[0-1]?\d?\d)(\.(25[0-5]|2[0-4]\d|[0-1]?\d?\d)){3}\]$'
emailre = re.compile(r"\s+\- Email_addresses\s*\n\s+\-\s*\n\s+\-\s+([\w.-]+@[\w.-]+)\n",
                     re.IGNORECASE)
addressre = re.compile("\s+\- Addresses\s*\n\s+\-\s*\n\s+\-\s+\"([\,\t \w]+)\"")
phonenumre = re.compile("\s+\- Phone_numbers\s*\n\s+\-\s*\n\s+\-\s+([\(\)\t \w\-]+)\n")
#notesre = re.compile("\- Note (?P<note_id>[0-9]+):\s*\-\s+Author:(?P<author>[ \w\&\.\-\\\/\(\)\'\"\!\,\;\#\@\+]+)\s*\-\s+Written: \"([A-Za-z0-9\,\: ]+)\"\s*\-\s+About: (?P<about>[ \w\&\.\-\\\/\(\)\'\"\!\,\;\#\@\+]+)\s*\-\s+Body: (.*\n.*))")


class HighRiseDataMiner():
    def __init__(self, pwdir):
        self.pwdir = pwdir
        self.tags = None
        self.tagdf = None
        self.df = None
        self.logger = logging.getLogger(__name__)
        self.notere = re.compile("\- (?P<note_type>Note|Comment|"
                                 "Task recording|Email) (?P<note_id>[0-9]+):")
        self.fieldre = re.compile("\- (\w+):")
        self.subfieldre = re.compile(
            "(?P<field>[ \t\w\-]+):"
            "(?P<field_data>[\s\w\&\.\-\\\/\(\)\'\"\!\,\;\#\@\+]+)"
        )

    def get_txt_files(self):
        for finame in os.listdir(self.pwdir):
            pth = os.path.join(self.pwdir, finame)
            with open(pth, 'r') as fi:
                yield (finame, fi)

    def get_tag_index(self, tag):
        tagind = hrminer.tags[hrminer.tags.str.find(tag) > -1]
        if len(tagind) > 0:
            return hrminer.tags[hrminer.tags.str.find(tag) > -1].index[0]
        else:
            return -1

    def mine_directory(self, target_dir=None):
        if target_dir:
            self.pwdir = target_dir
        results = {}
        for finame, fi in self.get_txt_files():
            results.update({finame : self.mine_file(fi, finame)})
        return results

    def _get_id_n_name_field(self, sre, field, data, finame):
        if sre:
            data[field] = sre.group(1)
        else:
            self.logger.warning(f"Could not find '{field}' for '{finame}'!")
        return data

    @staticmethod
    def _readnextline(f):
        fpos = f.tell()
        return fpos, f.readline()

    @staticmethod
    def clean_field(s):
        return s.group(1).strip()

    def _mine_tags(self, f, finame):
        tags = []
        fpos, txt = self._readnextline(f)
        if txt.startswith("  Tags:"):
            fpos, txt = self._readnextline(f)
            while not txt.startswith("-") and len(txt) > 0:
                tags.append(txt[4:])
                fpos, txt = self._readnextline(f)
            f.seek(fpos)
            return tags
        else:
            f.seek(fpos)
            return tags

    def mine_file(self, fi, finame):
        data = {}
        fieldre = re.compile("\-+ +(?P<field>\w+): ")
        with open(os.path.join(self.pwdir, finame)) as f:
            f.readline()
            sre_id = idre.search(f.readline())
            sre_name = namere.search(f.readline())
            data.update(self._get_id_n_name_field(sre_id, 'pid', data, finame))
            data.update(
                self._get_id_n_name_field(sre_name, 'name', data, finame)
            )
            tags = self._mine_tags(f, finame)
            data.update({'tags': tags})
            for field in self._mine_file_body(f, finame):
                data.update(field)

        return data

    def _mine_file_body(self, f, finame):
        data = {}
        txt = " "
        while len(txt) > 0:
            fpos, txt = self._readnextline(f)
            s = self.notere.search(txt)
            if s:
                id = s.groupdict().get("note_id").strip()
                note_type = s.groupdict().get("note_type").strip()
                data[f'note_{id}'] = {'type': note_type}
                self.logger.debug(f"Found a note section in file: '{finame}'")
                data[f'note_{id}'].update(self._mine_note(f, finame))
                yield data
            elif txt.startswith("- Contact: "):
                self.logger.debug(f"Mining contact for: '{finame}'")
                data["contact"] = self._mine_contact(f, finame)
                yield data
            elif txt.startswith("- Background:"):
                data['background'] = ""
                while len(txt) > 0:
                    fpos, txt = self._readnextline(f)
                    if txt.startswith("-"):
                        break
                    data['background'] += txt
                f.seek(fpos)
            else:
                s = self.fieldre.search(txt)
                if s:
                    field = self.clean_field(s)
                    fpos, txt = self._readnextline(f)
                    self.logger.info(f"Mining field: '{field} 'in '{finame}'")
                    data[field] = {}
                    f.seek(fpos)
                    while len(txt) > 0:
                        fpos, txt = self._readnextline(f)
                        if txt.startswith("-"):
                            break
                        s = self.subfieldre.search(txt)
                        if s:
                            subfield = s.groupdict().get("field").strip()
                            subdata = s.groupdict().get("field_data").strip()
                            self.logger.info(
                                f"Mining field '{field}', "
                                f"subfield '{subfield}', "
                                f"with '{subdata}'; in '{finame}'"
                            )
                            data[field].update({subfield: subdata})
                        else:
                            self.logger.warning(
                                f"!Not sure what to do with '{txt}', "
                                f"in '{field}' in file' {finame}'!"
                            )
                    f.seek(fpos)
                else:
                    if not (txt.isspace() or len(txt) == 0):
                        self.logger.warning(f"!Not sure what to do with "
                                            f"'{txt}' in file' {finame}'!")
                yield data

    def _mine_note(self, f, finame):
        data = {}
        self._readnextline(f) # Skip line
        fpos, txt = self._readnextline(f)
        data['author'] = txt[12:]

        self._readnextline(f) # Skip line
        fpos, txt = self._readnextline(f)
        data['written_on'] = txt[13:]

        self._readnextline(f) # Skip line
        fpos, txt = self._readnextline(f)
        data['about'] = txt[11:]

        self._readnextline(f)  # Skip line
        data["body"] = txt[10:]

        fpos, txt = self._readnextline(f)
        while not txt.startswith("-") and len(txt) > 0:
            data['body'] += txt
            fpos, txt = self._readnextline(f)
        f.seek(fpos)
        return data

    def _mine_contact(self, f, finame):
        data = {}
        fpos, txt = self._readnextline(f)
        infield = None
        fieldre = re.compile("    - (\w+)")
        datafieldre = re.compile("^\s+\- ([ A-Za-z0-9@\"\,\-\.\(\)]+)$")
        while not txt.startswith("-") and len(txt) > 0:
            fpos, txt = self._readnextline(f)
            if not infield:
                s = fieldre.search(txt)
                if s:
                    infield = self.clean_field(s)
                    self.logger.debug(f"Setting field to '{infield}'"
                                      f" for '{finame}'")
                    data[infield] = []
            else:
                if txt.startswith("  -"):
                    self.logger.debug(f"Leaving field '{infield}' in "
                                      f"contacts of '{finame}'")
                    infield = None
                else:
                    s = datafieldre.search(txt)
                    if s:
                        field = self.clean_field(s)
                        self.logger.debug(f"Adding '{field}' "
                                          f"to '{infield}' "
                                          f"in contacts of '{finame}'")
                        data[infield].append(field)
        f.seek(fpos)
        return data


if __name__ == '__main__':
    logging.basicConfig(filename='hrminer.log', level=logging.WARNING)
    pth = os.getcwd() if len(sys.argv) == 1 else sys.argv[1]
    ofname = 'yaya.json'
    hrminer = HighRiseDataMiner(pth)
    data = hrminer.mine_directory()
    with open(os.path.join(pth, '..', ofname), 'w') as f:
        json.dump(data, f)
