# Boost Software License - Version 1.0 - August 17th, 2003
#
# Permission is hereby granted, free of charge, to any person or organization
# obtaining a copy of the software and accompanying documentation covered by
# this license (the "Software") to use, reproduce, display, distribute,
# execute, and transmit the Software, and to prepare derivative works of the
# Software, and to permit third-parties to whom the Software is furnished to
# do so, all subject to the following:
#
# The copyright notices in the Software and this entire statement, including
# the above license grant, this restriction and the following disclaimer,
# must be included in all copies of the Software, in whole or in part, and
# all derivative works of the Software, unless such copies or derivative
# works are solely in the form of machine-executable object code generated by
# a source language processor.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE, TITLE AND NON-INFRINGEMENT. IN NO EVENT
# SHALL THE COPYRIGHT HOLDERS OR ANYONE DISTRIBUTING THE SOFTWARE BE LIABLE
# FOR ANY DAMAGES OR OTHER LIABILITY, WHETHER IN CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
import io
import os
from datetime import datetime
from itertools import groupby
from pprint import pformat

import pytz

from burpalyzer_constants import *
from burpalyzer_debugging import debug
from file_tools import read_json
# Formats seconds in twitch link URL format
from vote_parser import try_parse_vote


def offset_to_twitch_time(seconds):
    h, m, s = parse_offset(seconds)
    return "{:02d}h{:02d}m{:02d}s".format(h, m, s)


# Parses a string like "2021-05-28T21:01:12.495Z" into a datetime object
def parse_chat_timestamp(time_string):
    # Work around the fractional seconds being optional
    try:
        parsed = datetime.strptime(time_string, "%Y-%m-%dT%H:%M:%S.%fZ")  # FIXME: Actually parse the time zone
    except ValueError:
        parsed = datetime.strptime(time_string, "%Y-%m-%dT%H:%M:%SZ")  # FIXME: Actually parse the time zone
    return parsed


# Reduces "raw" input format of the twitch-chatlog module to what is necessary for analysis.
def raw_to_simple(raw):
    simple = []
    for message in raw:
        s = {
            KEY_VOD: message[u"content_id"],
            KEY_ID: message[u"_id"],
            KEY_TIME: parse_chat_timestamp(message[u"created_at"]),
            KEY_OFFSET: message[u"content_offset_seconds"],
            KEY_USER: message[u"commenter"][u"name"],
            KEY_TEXT: message[u"message"][u"body"]
        }
        simple.append(s)
    return simple


def read_folder_as_simple_group(dirname):
    simple_group = []
    for folder, subfolders, files in os.walk(dirname):
        for file in files:
            filePath = os.path.join(os.path.abspath(folder), file)
            debug("Reading " + filePath)
            data = read_json(filePath)
            simple = raw_to_simple(data)
            simple_group.append(simple)
    debug("Read {0} data files.".format(len(simple_group)))
    return simple_group


# Takes a list of chat logs in the "simple" format and extracts
# Only the burps detected by the burp bot
# FIXME: Version 1.2 multiburps not yet supported!!!
def simple_group_to_burp_data(simple_group, botname, fixup_list):
    # type: (List, str, str, List[Fixup]) -> list
    prefix1 = "Time's up! Final rating is: "
    prefix2 = "Time's up! Final rating: "
    burps = []
    for simple in simple_group:
        for message in simple:
            message_id = message[KEY_ID]
            text = message[KEY_TEXT]
            user = message[KEY_USER]
            excluded = any(x for x in fixup_list if x.fixup_type == FIXUP_TYPE_IGNORE and x.id == message_id)
            if not excluded and user == botname and (text.startswith(prefix1) or text.startswith(prefix2)):
                debug("Found rating: " + text)
                rating_text = text.replace(prefix1, "").replace(prefix2, "")
                (valid, ratings) = try_parse_vote(rating_text)
                if not valid:
                    raise RuntimeError("Can't parse rating text '" + rating_text + "'")
                # Treat all multivotes as separate votes for now
                if (len(ratings) > 1) and debug_enabled:
                    debug("Multivote (" + str(len(ratings)) + ") '" + rating_text + "' = " + pformat(ratings))
                for rating in ratings:
                    burp = {
                        KEY_ID: message_id,
                        KEY_VOD: message[KEY_VOD],
                        KEY_TIME: message[KEY_TIME],
                        KEY_OFFSET: message[KEY_OFFSET],
                        KEY_RATING: rating
                    }
                    burps.append(burp)
    debug("Found {0} ratings.".format(len(burps)))
    return burps


# Reduces the "simple" format to something humans can read in a text editor.
# Not recommend for further processing!
def simple_to_human_readable(simple):
    lines = []
    for message in simple:
        readable_time = datetime_to_local_iso(message[KEY_TIME])
        readable_offset = offset_to_twitch_time(message[KEY_OFFSET])
        line = u"{0} ({1}) - {2}: {3}".format(readable_time, readable_offset, message[KEY_USER], message[KEY_TEXT])
        lines.append(line)
    return lines


def parse_offset(seconds):
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return h, m, s


# Formats seconds as HH:MM:SS, e.g. 72.564 => "00:01:12"
def offset_to_hh_mm_ss(seconds):
    h, m, s = parse_offset(seconds)
    return "{:02d}:{:02d}:{:02d}".format(h, m, s)


def utc_datetime_to_local_datetime(utc_datetime, local_tz=None):
    return utc_datetime.replace(tzinfo=pytz.utc).astimezone(tz=local_tz)


def datetime_to_human_readable(utc_datetime):
    return utc_datetime_to_local_datetime(utc_datetime).strftime("%Y-%m-%d %H:%M:%S%z")


def datetime_to_local_iso(utc_datetime, local_tz=None):
    return utc_datetime_to_local_datetime(utc_datetime, local_tz).isoformat()


def output_burp_list(burp_data, outputter):
    if not debug_enabled:
        return
    for num, burp in enumerate(burp_data):
        # Link to 30 seconds before the rating
        link_seconds = max(0.0, (burp[KEY_OFFSET] - 30.0))
        link_time = offset_to_twitch_time(link_seconds)
        line = "#{rank} {rating:4.1f} https://www.twitch.tv/videos/{vod}?t={link_time} {time} {id}".format(
            rank=str(num + 1).ljust(2),
            id=burp[KEY_ID],
            time=burp[KEY_TIME],
            rating=burp[KEY_RATING],
            vod=burp[KEY_VOD],
            link_time=link_time
        )
        outputter(line)


def group_by_month_and_year(burp_data):
    sorted_burp_data = sorted(burp_data, key=lambda burp: burp[KEY_TIME])
    return groupby(sorted_burp_data, lambda burp: (burp[KEY_TIME].month, burp[KEY_TIME].year))


FIXUP_TYPE_IGNORE = "IGNORE"
FIXUP_TYPE_OFFSET = "OFFSET"
FIXUP_TYPE_CLIP = "CLIP"


class Fixup:
    def __init__(self, fixup_type, *args):
        self.fixup_type = fixup_type
        if fixup_type == FIXUP_TYPE_IGNORE:
            self.id = args[0]
        elif fixup_type == FIXUP_TYPE_OFFSET:
            self.id = args[0]
            self.offset = args[1]
        elif fixup_type == FIXUP_TYPE_CLIP:
            self.id = args[0]
            self.url = args[1]


def read_fixup_list(filename):
    fixups = []
    with io.open(filename, 'r', encoding="utf-8") as fixup_file:
        lines = fixup_file.readlines()
        for line in lines:
            parts = line.split()
            if len(parts) > 0:
                fixup_type = parts[0]
                if fixup_type == FIXUP_TYPE_IGNORE:
                    if not len(parts) >= 2:
                        raise RuntimeError(fixup_type + " needs at least one argument: UUID")
                    else:
                        message_id = parts[1]
                        debug("Found excluded id: " + message_id)
                        fixups.append(Fixup(fixup_type, message_id))
                elif fixup_type == FIXUP_TYPE_OFFSET:
                    if not len(parts) >= 3:
                        raise RuntimeError(fixup_type + " needs at least two arguments: Offset, UUID")
                    else:
                        raise NotImplementedError("TODO: Implement offset fixups")
                elif fixup_type == FIXUP_TYPE_CLIP:
                    if not len(parts) >= 3:
                        raise RuntimeError(fixup_type + " needs at least two argument: UUID, URL")
                    else:
                        message_id = parts[1]
                        url = parts[2]
                        debug("Found CLIP: " + message_id + " => " + url)
                        fixups.append(Fixup(fixup_type, message_id, url))
                else:
                    raise RuntimeError("Unknown fixup type '" + fixup_type + "'")

    return fixups
