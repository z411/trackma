# This file is part of Trackma.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import re
from decimal import Decimal

NO_SUBBER = '###NO#SUBBER#HERE###'

BRACKET_PAIRS = [
    # to be inserted in regular expressions
    (r'\[', r'\]'),
    (r'\(', r'\)'),
    (r'\{', r'\}'),
]


class AnimeInfoExtractor:
    """
    Extracts lots of information about anime from filename alone
    @author: Tyris
    @author: Uriziel
    @note: Thanks for Tyris for providing easy way to extract data
    @note: Does more than what's needed, but that behaviour is well tested
    """

    def __init__(self, filename):
        self.originalFilename = filename
        self.resolution = ''
        self.hash = ''
        self.subberTag = ''
        self.videoType = []
        self.audioType = []
        self.releaseSource = []
        self.extension = ''
        self.episodeStart = None
        self.episodeEnd = None
        self.volumeStart = None
        self.volumeEnd = None
        self.version = 1
        self.name = ''
        self.pv = -1
        self.season = None
        self._processFilename()

    def getName(self):
        return self.name

    def getEpisodeNumbers(self, force_numbers=False):
        ep_start = self.episodeStart
        ep_end = self.episodeEnd
        if force_numbers:
            if ep_start is None:
                ep_start = 1
            if ep_end is None:
                ep_end = ep_start
            ep_start = int(ep_start)
            ep_end = int(ep_end)
        return ep_start, ep_end

    def getEpisode(self):
        ep = self.episodeStart if self.episodeEnd is None else self.episodeEnd
        ep = ep if ep is not None else 1

        return int(ep)

    def __extractExtension(self, filename):
        m = re.search(r"\.(\w{3})$", filename)
        if m:
            self.extension = m.group(1)
            filename = filename[:-4]
        return filename

    def __cleanUpSpaces(self, filename):
        characters = "_.-"
        for char in characters:
            if ' ' in filename:
                break
            filename = re.sub(r'([^{0}]){0}(?=[^{0}]|$)'.format(re.escape(char)), r'\1 ', filename)
        return filename

    def __extractSpecialTags(self, filename):
        tags = {'video': r'H\.?264|x264|AVC|XviD|DivX|H\.?265|HEVC|AV1',
                'audio': r'AC3|AAC|MP3|FLAC|E-?AC-?3|Opus|DTS(?:-HD)?|TrueHD|L?PCM',
                'source': r'TV|DVD|Blu-?Ray|BD|BDMV|www|WEB(?:-DL)?'}
        for k, tag_re in tags.items():
            m = re.search(r'[\(\[][^\)\]]*?\b(' + tag_re + r')\b',
                          filename,
                          flags=re.IGNORECASE)
            if m:
                if k == 'video':
                    self.videoType.append(m.group(1))
                elif k == 'audio':
                    self.audioType.append(m.group(1))
                elif k == 'source':
                    self.releaseSource.append(m.group(1))
                # remove the match
                filename = filename[:m.start(1)] + NO_SUBBER + filename[m.end(1):]
        return filename

    def __extractVideoProfile(self, filename):
        # Check for 8bit/10bit/Hi444PP
        h264_profiles = [
            (['H264', 'Hi10P'], ['Hi10P', 'Hi10', '10bit', '10 bit', '10-bit', 'YUV420P10']),
            (['H264', '8bit'], ['8bit', '8-bit']),
            (['H264', 'Hi444PP'], ['Hi444PP', 'YUV444P10']),
        ]
        for to_add, tags in h264_profiles:
            for tag in tags:
                if tag in filename:
                    self.videoType = to_add
                    # Don't replace Hi10 because it's a subber name
                    if tag != 'Hi10':
                        filename = filename.replace(tag, '')
                    return filename
        return filename

    def __extractResolution(self, filename):
        # Match 3 or 4 chars followed by p, i, or x and 3 or 4 more chars, surrounded by any non-alphanumeric chars
        m = re.search(r'\b(\d{3,4}(?:p|i|x\d{3,4}))\b', filename)
        if m:
            self.resolution = m.group(1)
            return filename[:m.start(1)] + filename[m.end(1):]
        # HD/SD in brackets or after an episode number
        m = re.search(r'(?:[\[\(]|\d{1,3})\s*([HS]D)(TV)?\b', filename)
        if m:
            self.resolution = m.group(1)
            if m.group(2):
                self.releaseSource.append(m.group(2))
            return filename[:m.start(1)] + filename[m.end():]
        # HD/SD at the end
        m = re.search(r'\b([HS]D)(TV)?$', filename)
        if m:
            self.resolution = m.group(1)
            if m.group(2):
                self.releaseSource.append(m.group(2))
            return filename[:m.start()] + filename[m.end():]

        return filename

    def __extractHash(self, filename):
        # Match anything in square or round brackets that is 8 hex digits
        m = re.search(r'[\(\[]([A-Fa-f0-9]{8})[\)\]]', filename)
        if m:
            self.hash = m.group(1)
            filename = filename[:m.start()] + filename[m.end():]
        return filename

    def __checkIfRemux(self, filename):
        m = re.search(r'[\(\[][^\)\]]*?(Remux)\b', filename, flags=re.IGNORECASE)
        return True if m else False

    def __cleanUpBrackets(self, filename):
        # Can get rid of the brackets that won't contain subber
        filename = re.sub(r'\([^\)]*?' + NO_SUBBER + r'.*?\)', '', filename)
        filename = re.sub(r'\[[^\]]*?' + NO_SUBBER + r'.*?\]', '', filename)
        # Strip any empty sets of brackets, unless they are at the beginning
        filename = re.sub(r'(?!^)\[\W*?\]|\(\W*?\)', '', filename)
        return filename

    def __extractSubber(self, filename, remux):
        # Extract the subber from square brackets (or round failing that)
        for opening, closing in BRACKET_PAIRS:
            m = re.search(r'{0}([^\. ].*?){1}'.format(opening, closing), filename)
            if m:
                self.subberTag = m.group(1)
                filename = filename[:m.start()] + filename[m.end():]
                break
        # Add the remux string if this was a remux and it's not found in the subber tag
        if remux and 'remux' not in self.subberTag.lower():
            # refind remux and remove it
            m = re.search(
                r'[\(\[][^\)\]]*?(Remux)\b', filename, flags=re.IGNORECASE)
            if m:
                filename = filename[:m.start(1)] + filename[m.end(1):]
            if self.subberTag:
                self.subberTag = self.subberTag + '-Remux'
            else:
                self.subberTag = 'Remux'
        return filename

    def __extractVersion(self, filename):
        # Extract the version number (limit at v7 since V8 is possible in a title...)
        m = re.search(r'(?:[^a-zA-Z])v([0-7])\b',
                      filename, flags=re.IGNORECASE)
        if m:
            self.version = int(m.group(1))
            filename = filename[:m.start(1) - 1] + filename[m.end(1):]
        return filename

    def __extractVolumeIfPack(self, filename, title_len):
        # Check if this is a volume pack - only relevant for no extension
        if not self.extension:
            m = re.search(
                r'\b(?:vol(?:ume)?\.? ?)(\d{1,3})(?: ?- ?(?:vol(?:ume)?\.? ?)?(\d{1,3}))?\b',
                filename,
                flags=re.IGNORECASE)
            if m:
                self.volumeStart = int(m.group(1))
                if m.group(2):
                    self.volumeEnd = int(m.group(2))
                filename = filename[:m.start()] + filename[m.end():]
                title_len = m.start()
        return filename, title_len

    def __extractPv(self, filename):
        # Check if this is a PV release (not relevant if it's a pack)
        m = re.search(r' PV ?(\d)?(?:[^a-zA-Z0-9]|$)', filename)
        if not self.volumeStart and m:
            self.pv = 0
            if m.group(1):
                self.pv = int(m.group(1))
            filename = filename[:m.start(0)]
        return filename

    def __extractEpisodeNumbers(self, filename):
        # First check for concurrent episodes (with a + or &)
        m = re.search(
            r'\b(?:S(?:\.|eason)?(\d+)\s*)?'
            r'(?:E\.?|Ep(?:i|isode)?s?[ .]?)?(\d{1,4})[\+\&](\d{1,4})\b',
            filename,
            flags=re.IGNORECASE,
        )
        if m:
            start = int(m.group(2))
            end = int(m.group(3))
            if end == start + 1:
                if m.group(1):
                    self.season = int(m.group(1))
                self.episodeStart = start
                self.episodeEnd = end
                return filename[:m.start()]

        # Check for multiple episodes (with a -)
        ep_search_string = (
            r'\b(?:S(?:\.|eason)?(\d+)\s*)?'
            r'(?:E\.?|Ep(?:i|isode)?[ .]?)?'
            r'((?:\d{1,3}|1[0-8]\d{2})(?:\.\d{1})?)'
            # Only allow spaces around the hyphen when we are likely to have a pack
            + (r'-' if self.extension else r' ?- ?')
            + r'(\d{1,4}(?:\.\d{1})?)\b'
        )
        m = re.search(ep_search_string, filename, flags=re.IGNORECASE)
        if m:
            if m.group(1):
                self.season = int(m.group(1))
            self.episodeStart = Decimal(m.group(2))
            self.episodeEnd = Decimal(m.group(3))
            return filename[:m.start()]

        # Check if there is an episode specifier
        m = re.search(
            r'\b(?:S(?:\.|eason)?(\d+)\s*)?(?:E\.?|Ep(?:i|isode)?[ .]?)(\d+(?:\.\d)?)(?:\b|v)',
            filename,
            flags=re.IGNORECASE
        )
        if m:
            if m.group(1):
                self.season = int(m.group(1))
            self.episodeStart = Decimal(m.group(2))
            return filename[:m.start()]

        # Check any remaining lonely numbers as episode (towards the end has priority)
        # First try outside brackets
        m = re.search(r'.*[^\.\[\(]\b((?:\d{1,3}|1[0-8]\d{2})(?:\.\d)?)(?:[\[({]|\s*$|\s+\W)',
                      filename)
        if m:
            self.episodeStart = Decimal(m.group(1))
            return filename[:m.start(1)]

        # then allow brackets
        m = re.search(r'.*[\[\(]((?:\d{1,3}|1[0-8]\d{2})(?:\.\d)?)(?:[\])}]|\s*$|\s+\W)', filename)
        if m:
            self.episodeStart = Decimal(m.group(1))
            return filename[:m.start(1)]
        return filename

    def __extractShowName(self, filename):
        # Unfortunately it's very hard to know if there should be brackets in the title.
        # We really should strip brackets, though, so sorry to anything with brackets in the title.
        # We don't strip years or the whole title, however.
        for opening, closing in BRACKET_PAIRS:
            m = re.search(r'{0}((?!\d{{4}}{1}).*?){1}'.format(opening, closing), filename)
            if m and m.end() - m.start() < len(filename):
                filename = filename[:m.start()] + filename[m.end():]
        filename = re.sub(r'  .*', '', filename)
        # Strip any unclosed brackets and anything after them
        for opening, closing in BRACKET_PAIRS:
            filename = re.sub(r'{}r[^{}].*$'.format(opening, closing), '', filename)
        self.name = re.sub(r'( - *)+$', '', filename.strip(' '))
        # If we have a subber but no title!? then it must have been a title...
        if self.name == '' and self.subberTag != '':
            self.name = self.subberTag
            self.subberTag = ''
        # Reappend season number
        if self.season and self.season > 1:
            self.name += " {}".format(self.season)

    def _processFilename(self):
        filename = self.originalFilename
        filename = self.__extractExtension(filename)
        filename = self.__cleanUpSpaces(filename)
        filename = self.__extractSpecialTags(filename)
        filename = self.__extractVideoProfile(filename)
        filename = self.__extractResolution(filename)
        filename = self.__extractHash(filename)
        remux = self.__checkIfRemux(filename)
        filename = self.__cleanUpBrackets(filename)
        filename = self.__extractSubber(filename, remux)
        filename = self.__extractVersion(filename)
        # Store the possible length of the title
        title_len = len(filename)
        filename, title_len = self.__extractVolumeIfPack(filename, title_len)
        filename = self.__extractPv(filename)
        if self.pv == -1:
            filename = self.__extractEpisodeNumbers(filename)
        # Truncate remainder to title length if needed (for where volume was found)
        filename = filename[:title_len]
        # Strip any trailing opening brackets
        filename = filename.rstrip('([{')
        self.__extractShowName(filename)
