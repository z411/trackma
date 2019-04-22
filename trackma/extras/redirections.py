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


def parse_anime_relations(filename, api, mediatype, last=None):
    """
    Support for Taiga-style anime relations file.
    Thanks to erengy and all the contributors.
    Database under the public domain.

    https://github.com/erengy/anime-relations
    """

    apis = ['mal', 'kitsu', 'anilist']
    mediatypes = ['anime']

    if api not in apis or mediatype not in mediatypes:
        return None

    (src_grp, dst_grp) = (apis.index(api) + 1, apis.index(api) + 6)

    with open(filename) as f:
        import re

        relations = {'meta':{}}

        id_pattern = "(\d+|[\?~])\|(\d+|[\?~])\|(\d+|[\?~])"
        ep_pattern = "(\d+)-?(\d+|\?)?"
        full = r'- {0}:{1} -> {0}:{1}(!)?'.format(id_pattern, ep_pattern)
        _re = re.compile(full)

        mode = 0

        for line in f:
            line = line.strip()

            if not line:
                continue
            if line[0] == '#':
                continue

            if mode == 0 and line == "::meta":
                mode = 1
            elif mode == 1:
                if line[:16] == "- last_modified:":
                    last_modified = line[17:]

                    # TODO : Stop if the file hasn't changed
                    if last and last == last_modified:
                        return None

                    relations['meta']['last_modified'] = last_modified
                elif line == "::rules":
                    mode = 2
            elif mode == 2 and line[0] == '-':
                m = _re.match(line)
                if m:
                    # Source
                    src_id  = m.group(src_grp)
                    
                    # Handle unknown IDs
                    if src_id == '?':
                        continue
                    else:
                        src_id = int(src_id)

                    # Handle infinite ranges
                    if m.group(5) == '?':
                        src_eps = (int(m.group(4)), -1)
                    else:
                        src_eps = (int(m.group(4)), int(m.group(5) or m.group(4)))

                    # Destination
                    dst_id  = m.group(dst_grp)

                    # Handle ID repeaters
                    if dst_id == '~':
                        dst_id = src_id
                    else:
                        dst_id  = int(dst_id)

                    # Handle infinite ranges
                    if m.group(10) == '?':
                        dst_eps = (int(m.group(9)), -1)
                    else: 
                        dst_eps = (int(m.group(9)), int(m.group(10) or m.group(9)))

                    if not src_id in relations:
                        relations[src_id] = []
                    relations[src_id].append((src_eps, dst_id, dst_eps))
                else:
                    print("Not recognized. " + line)

        return relations


