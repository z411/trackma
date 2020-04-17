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

import socket
import json
import datetime
import ssl

from trackma.lib.lib import lib
from trackma import utils

class libvndb(lib):
    """
    API class to communicate with VNDB
    Implements protocol version 1.

    Website: https://www.vndb.org
    API documentation: https://vndb.org/d11
    Designed by: Yorhel <contact@vndb.org> (https://vndb.org/u2)

    """
    name = 'libvndb'

    api_info =  {
                  'name': 'VNDB',
                  'shortname': 'vndb',
                  'version': 2,
                  'merge': True,
                }

    default_mediatype = 'vnlist'
    pagesize_list = 100
    pagesize_details = 25

    mediatypes = dict()
    mediatypes['vnlist'] = {
        'has_progress': False,
        'can_score': True,
        'can_status': True,
        'can_add': True,
        'can_delete': True,
        'can_update': False,
        'can_play': False,
        'statuses':  [1, 2, 3, 4, 0],
        'statuses_dict': { 1: 'Playing', 2: 'Finished', 3: 'Stalled', 4: 'Dropped', 0: 'Unknown' },
        'score_max': 10,
        'score_step': 0.1,
        'statuses_start': [1],
        'statuses_finish': [2],
    }
    mediatypes['wishlist'] = {
        'has_progress': False,
        'can_score': True,
        'can_status': True,
        'can_add': True,
        'can_delete': True,
        'can_update': False,
        'can_play': False,
        'statuses':  [0, 1, 2, 3],
        'statuses_dict': { 0: 'High', 1: 'Medium', 2: 'Low', 3: 'Blacklist' },
        'score_max': 10,
        'score_step': 0.1,
        'statuses_start': [],
        'statuses_finish': [],
    }

    def __init__(self, messenger, account, userconfig):
        """Initializes the useragent through credentials."""
        super(libvndb, self).__init__(messenger, account, userconfig)

        self.hostname = "api.vndb.org"
        self.tls = 19535
        self.tcp = 19534
        self.username = account['username']
        self.password = account['password']
        self.logged_in = False

    def _connect(self):
        """Create TCP socket and connect"""

        self.context = ssl.create_default_context()
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.s = self.context.wrap_socket(s, server_hostname=self.hostname)
            self.s.connect((self.hostname, self.tls))
        except socket.error:
            raise utils.APIError("Connection error.")
        except ssl.CertificateError:
            raise utils.APIError("Insecure connection.")

    def _disconnect(self):
        """Shutdown and close the socket"""
        self.s.shutdown(socket.SHUT_RDWR)
        self.s.close()

    def _sendcmd(self, cmd, options=None):
        """Send a VNDB compatible command and return the response data"""
        msg = cmd
        if options:
            msg += " " + json.dumps(options, separators=(',',':'))
        msg = msg.encode('utf-8')
        msg += b"\x04" # EOT

        # Send message
        self.s.sendall(msg)

        # Construct response
        lines = []
        while True:
            line = self.s.recv(65536)
            if line.endswith(b"\x04"):
                line = line.strip(b"\x04")
                lines.append(line)
                response = b"".join(lines).decode('utf-8')
                break
            else:
                lines.append(line)

        # Separate into response name and JSON data
        _resp = response.split(' ', 1)
        name = _resp[0]
        try:
            data = json.loads(_resp[1])
        except IndexError:
            data = None

        # Treat error as an exception
        if name == 'error':
            raise utils.APIError(data['msg'])

        return (name, data)

    def check_credentials(self):
        """Checks if credentials are correct; returns True or False."""
        if self.logged_in:
            return True

        self.msg.info(self.name, 'Connecting...')
        self._connect()

        self.msg.info(self.name, 'Logging in...')
        (name, data) = self._sendcmd('login',
            {'protocol': 1,
             'client': 'Trackma',
             'clientver': self.api_info['version'],
             'username': self.username,
             'password': self.password,
             })

        if name == 'ok':
            self.logged_in = True
            self._set_userconfig('username', self.username)
            return True
        else:
            return False

    def fetch_list(self):
        """Queries the full list from the remote server.
        Returns the list if successful, False otherwise."""
        self.check_credentials()

        # Retrieve VNs per pages
        page = 1
        vns = dict()
        while True:
            self.msg.info(self.name, 'Downloading list... (%d)' % page)

            (name, data) = self._sendcmd('get %s basic (uid = 0)' % self.mediatype,
                {'page': page,
                'results': self.pagesize_list
                })

            # Something is wrong if we don't get a results response.
            if name != 'results':
                raise utils.APIFatal("Invalid response (%s)" % name)

            # Process list
            for item in data['items']:
                vnid = item['vn']
                vns[vnid] = utils.show()
                vns[vnid]['id']         = vnid
                vns[vnid]['url'] = self._get_url(vnid)
                vns[vnid]['my_status']  = item.get('status', item.get('priority'))

            if not data['more']:
                # No more VNs, finish
                break
            page += 1

        # Retrieve scores per pages
        page = 1
        while True:
            self.msg.info(self.name, 'Downloading votes... (%d)' % page)

            (name, data) = self._sendcmd('get votelist basic (uid = 0)',
                {'page': page,
                'results': self.pagesize_list
                })

            # Something is wrong if we don't get a results response.
            if name != 'results':
                raise utils.APIFatal("Invalid response (%s)" % name)

            for item in data['items']:
                vnid = item['vn']
                if vnid not in vns:
                    # Ghost vote; create entry for it.
                    vns[vnid] = utils.show()
                    vns[vnid]['id'] = vnid
                    vns[vnid]['url'] = self._get_url(vnid)
                    vns[vnid]['my_status'] = 0

                vns[vnid]['my_score'] = (item['vote'] / 10.0)
                vns[vnid]['my_finish_date'] = datetime.datetime.fromtimestamp(item['added'])

            if not data['more']:
                # No more VNs, finish
                break
            page += 1

        return vns

    def request_info(self, itemlist):
        self.check_credentials()

        start = 0
        infos = list()
        remaining = [ show['id'] for show in itemlist ]
        while True:
            self.msg.info(self.name, 'Requesting details...(%d)' % start)
            end = start + self.pagesize_details

            (name, data) = self._sendcmd('get vn basic,details (id = %s)' % repr(remaining[start:end]),
                {'page': 1,
                 'results': self.pagesize_details,
                })

            # Something is wrong if we don't get a results response.
            if name != 'results':
                raise utils.APIFatal("Invalid response (%s)" % name)

            # Process list
            for item in data['items']:
                infos.append(self._parse_info(item))

            start += self.pagesize_details
            if start >= len(itemlist):
                # We're going beyond the list, finish
                break

        self._emit_signal('show_info_changed', infos)
        return infos

    def add_show(self, item):
        # When we try to "update" a VN that isn't in the list, the
        # VNDB API automatically inserts it, so we can use the same
        # command.
        self.update_show(item)

    def update_show(self, item):
        self.check_credentials()

        # Update status with set vnlist
        if 'my_status' in item:
            self.msg.info(self.name, 'Updating VN %s (status)...' % item['title'])

            if self.mediatype == 'wishlist':
                values = {'priority': item['my_status']}
            else:
                values = {'status': item['my_status']}

            (name, data) = self._sendcmd('set %s %d' % (self.mediatype, item['id']), values)

            if name != 'ok':
                raise utils.APIError("Invalid response (%s)" % name)

        # Update vote with set votelist
        if 'my_score' in item:
            self.msg.info(self.name, 'Updating VN %s (vote)...' % item['title'])

            if item['my_score'] > 0:
                # Add or update vote
                values = {'vote': item['my_score'] * 10}
            else:
                # Delete vote if it's 0
                values = None

            (name, data) = self._sendcmd('set votelist %d' % item['id'], values)

            if name != 'ok':
                raise utils.APIError("Invalid response (%s)" % name)

    def delete_show(self, item):
        self.check_credentials()

        self.msg.info(self.name, 'Deleting VN %s...' % item['title'])

        (name, data) = self._sendcmd('set %s %d' % (self.mediatype, item['id']))

        if name != 'ok':
            raise utils.APIError("Invalid response (%s)" % name)

    def search(self, criteria, method):
        self.check_credentials()

        results = list()
        self.msg.info(self.name, 'Searching for %s...' % criteria)

        (name, data) = self._sendcmd('get vn basic,details (search ~ "%s")' % criteria,
            {'page': 1,
             'results': self.pagesize_details,
            })

        # Something is wrong if we don't get a results response.
        if name != 'results':
            raise utils.APIFatal("Invalid response (%s)" % name)

        # Process list
        for item in data['items']:
            results.append(self._parse_info(item))

        self._emit_signal('show_info_changed', results)

        if not results:
            raise utils.APIError('No results.')

        return results

    def logout(self):
        self.msg.info(self.name, 'Disconnecting...')
        self._disconnect()
        self.logged_in = False

    def merge(self, show, info):
        show['title'] = info['title']
        show['image'] = info.get('image')
        show['start_date'] = info.get('start_date')
        if show['start_date'] and show['start_date'] > datetime.datetime.now():
            show['status'] = utils.STATUS_NOTYET
        else:
            show['status'] = utils.STATUS_FINISHED

    def _parse_info(self, item):
        start_date = self._str2date(item['released'])

        info = utils.show()
        info.update({'id': item['id'],
                'title': item['title'],
                'image': item['image'],
                'url': self._get_url(item['id']),
                'start_date': self._str2date(item['released']),
                'extra': [
                    ('Original Name', item['original']),
                    ('Released',      item['released']),
                    ('Languages',     ','.join(item['languages'])),
                    ('Original Language', ','.join(item['orig_lang'])),
                    ('Platforms',     ','.join(item['platforms'])),
                    ('Aliases',       item['aliases']),
                    ('Length',        item['length']),
                    ('Description',   item['description']),
                    ('Links',         item['links']),
                ]
               })
        return info

    def _get_url(self, vnid):
        return "http://vndb.org/v%d" % vnid

    def _str2date(self, string):
        if string != '0000-00-00':
            try:
                return datetime.datetime.strptime(string, "%Y-%m-%d")
            except ValueError:
                return None # Ignore date if it's invalid
        else:
            return None


