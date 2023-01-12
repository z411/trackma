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
import os
import anitopy
from decimal import Decimal


class AnitopyWrapper():
    """
    Wrapper class around Anitopy, the anime filename parser.
    Exists mainly for compatibility reasons, but also to work around
    some edge cases that Anitopy cannot solve.
    """

    def __init__(self, msg, file_name):
        self.msg = msg.with_classname('Parser')
        self.original_file_name = file_name

        file_name = self.__preProcessFileName(file_name)
        file_name = self.__trimFileName(file_name)
        self.file_name = file_name

        try:
            data = anitopy.parse(file_name)
        except Exception:
            # If Anitopy crashes while parsing a filename, print the traceback
            # instead of crashing Trackma altogether.
            import traceback
            traceback.print_exc()
            data = {}
            return

        self.episode_number = self.__extractEpisodeNumber(data)
        self.anime_title = self.__extractAnimeTitle(data)

    def getName(self):
        # Returns the anime title
        return self.anime_title

    def getEpisode(self):
        # Returns the first/only episode number
        if self.episode_number is None:
            return 1

        if type(self.episode_number) is list:
            return int(self.episode_number[-1])
        else:
            return int(self.episode_number)

    def getEpisodeNumbers(self, force_numbers=False):
        # Returns the episode range as a tuple
        (ep_start, ep_end) = (None, None)

        if self.episode_number:
            try:
                if isinstance(self.episode_number, list):
                    ep_start = Decimal(self.episode_number[0])
                    ep_end = Decimal(self.episode_number[-1])
                else:
                    ep_start = Decimal(self.episode_number)
            except ArithmeticError:
                self.msg.warn("Unable to parse episode number '{}' of: {}"
                              .format(self.episode_number, self.original_file_name))

        if force_numbers:
            if ep_start is None:
                ep_start = 1
            if ep_end is None:
                ep_end = ep_start
            (ep_start, ep_end) = (int(ep_start), int(ep_end))

        return (ep_start, ep_end)

    @staticmethod
    def __preProcessFileName(file_name):
        # Make some adjustments to the file name to increase parsing accuracy

        # If full path is provided to Anitopy, all [brackets with contents]
        # adjacent to the path separators should be moved to the VERY beginning.
        # Or Anitopy won't be able to parse them out.
        file_name = os.path.sep + file_name
        for m in re.finditer(
                r'(?<={0})\[.*?\]|\[.*?\](?={0})'.format(os.path.sep),
                file_name):
            file_name = (m.group() + file_name[:m.start()]
                              + file_name[m.end():])

        # Remove all the path separators (except the last one, we'll need it later)
        *parts, last_part = file_name.split(os.path.sep)
        file_name = ' '.join(parts) + last_part

        # Anitopy can parse S01E01 properly, but not S01OVA01, S01S01, S01NCOP01 etc.
        # So we'll need to break things down for the parser.
        m = re.search(r'S(?P<season>[0-9]+)(?P<type>[A-Za-z]+)(?P<episode>[0-9]+)', file_name)
        if m:
            groups = m.groupdict()
            # 'S01E01' -> 'Season 01 - 01'
            if groups['type'] == 'E':
                groups['type'] = ''
            # 'S01S01' -> 'Season 01 Specials - 01'
            if groups['type'] == 'S':
                groups['type'] = 'Specials'
            # for all other cases:
            # 'S01{type}01' -> 'Season 01 {type} - 01'
            file_name = (
                file_name[:m.start()] + 'Season ' + groups['season']
                + ' ' + groups['type'] + ' - ' + groups['episode']
                + file_name[m.end():])

        return file_name

    @staticmethod
    def __trimFileName(file_name):
        # If the same title appears in the parent directory and the file name,
        # we might want to remove the duplicate one.
        # Otherwise, Anitopy would concatenate them together.
        try:
            # Temporarily replace all punctuations with spaces
            temp = re.sub(r'[^\w\s{0}\(\)\{{\}}\[\]]'.format(os.path.sep),
                          r' ', file_name, flags=re.ASCII)
            # Search and remove the longest duplicate
            m = max(
                [x for x in re.finditer(
                    r'(\b.{{3,}}\b)(?=.*?{0}.*?(?P<DUP>\1))'.format(os.path.sep),
                    temp, flags=re.IGNORECASE)],
                key = lambda y: y.end() - y.start()
            )
            if m:
                file_name = file_name[:m.start('DUP')] + ' ' + file_name[m.end('DUP'):]
        except ValueError:
            pass

        # Remove the remaining path separator(s)
        file_name = file_name.replace(os.path.sep, ' ')
        # Remove empty ( ) brackets
        file_name = re.sub(r'[\[\{\(][\s\._]*[\)\}\]]', r'', file_name)
        # Trim unnecessary     spaces
        file_name = re.sub(r'\s{2,}', r' ', file_name.strip())

        return file_name

    @staticmethod
    def __extractAnimeTitle(data):
        # Deal with anime title related stuff that Anitopy left out
        if 'anime_title' not in data:
            return None
        anime_title = data['anime_title']

        # Append anime season to the title (if needed)
        anime_season = data.get('anime_season')
        if anime_season:
            if not isinstance(anime_season, list):
                anime_season = anime_season[0]
            if int(anime_season) > 1:
                anime_title += ' Season ' + anime_season

        # Solve 'Season X Part Y' cases
        if 'episode_title' in data:
            m = re.search(r'^Part [2-9]\b', data['episode_title'], flags=re.IGNORECASE)
            if m:
                anime_title += ' ' + m.group(0)

        # Append anime type to the title (if needed)
        anitype_invalid = ('OP', 'NCOP', 'OPENING', 'ED', 'NCED', 'ENDING', 'PV', 'PREVIEW')
        anitype_specials = ('OAD', 'OAV', 'ONA', 'OVA', 'SPECIAL', 'SPECIALS')
        anime_type = data.get('anime_type')
        if anime_type:
            if not isinstance(anime_type, list):
                anitype = [anime_type]
            for t in anitype:
                # Ignore non-episodes such as openings, endings, previews etc.
                if t.upper() in anitype_invalid:
                    return None
                if t not in anime_title and t.upper() in anitype_specials:
                    anime_title += ' ' + t
        else:
            # Fix anime type being detected as episode title
            if 'episode_title' in data:
                for t in anitype_specials:
                    m = re.search(r'{0}\b'.format(re.escape(t)), data['episode_title'],
                                  flags=re.IGNORECASE)
                    if m:
                        anime_title += ' ' + m.group(0)

        # Append anime year to the title (if needed)
        anime_year = data.get('anime_year')
        if anime_year and anime_year not in anime_title:
            anime_title += ' (' + anime_year + ')'

        return anime_title

    @staticmethod
    def __extractEpisodeNumber(data):
        # Deal with episode related stuff that Anitopy left out
        if 'episode_number' not in data:
            return
        episode_number = data['episode_number']

        # Handle cases like: "[Judas] Naruto - S05E01 (186).mkv"
        # Anitopy should detect the consecutive episode number (186) properly.
        # Just set that as the original episode number, and remove the season value.
        if 'episode_number_alt' in data:
            episode_number = data['episode_number_alt']
            del data['episode_number_alt']
            if 'anime_season' in data:
                del data['anime_season']

        # Unfortunately, we can't have episode numbers like 1A, 1B, 1C etc.
        if isinstance(data['episode_number'], str):
            episode_number = re.sub(r'ABCabc', r'', episode_number)

        return episode_number
