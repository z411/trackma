import utils
import tracker

import cPickle
import difflib
import urllib
import xml.etree.ElementTree as ET

class TorrentManager(object):
    torrents = {}

    # Hardcoded for now
    FEED_URL = "http://www.nyaa.se/?page=rss&cats=1_37"

    def __init__(self, animelist, config):
        self.animelist = animelist
        utils.make_dir('')
        self.filename = utils.get_root_filename('torrents.dict')
        self._load()

    def _load(self):
        if utils.file_exists(self.filename):
            with open(self.filename, 'rb') as f:
                self.torrents = cPickle.load(f)

    def _save(self):
        with open(self.filename, 'wb') as f:
            cPickle.dump(self.torrents, f)
    
    def _download_feed(self, url):
        return ET.parse(urllib.urlopen(url)).getroot()

    def _parse_feed(self, dom):
        items = []
        for node in dom.iter('item'):
            item = {}
            for child in node:
                if child.tag == 'title':
                    item['title'] = child.text
                elif child.tag == 'link':
                    item['link'] = child.text
                elif child.tag == 'description':
                    item['description'] = child.text
                
            items.append(item)

        return items

    def get_torrents(self):
        torrents_keys = self.torrents.keys()

        print "Downloading list..."
        dom = self._download_feed(self.FEED_URL)
        print "Parsing..."
        matcher = difflib.SequenceMatcher()
        print "Successful matches:"
        items = self._parse_feed(dom)
        total_items = len(items)
        i = 1
        for item in items:
            print "Processing %d/%d..." % (i, total_items)
            i += 1

            if item['title'] in torrents_keys:
                print "Already cached." + item['title']
                continue

            torrent = {'show_id': None,
                       'show_title': None,
                       'show_episode': None,
                       'show_group': None,
                       'status': 'not found',
                      }

            highest_ratio = (None, 0)
            aie = tracker.AnimeInfoExtractor(item['title'])
            epStart, epEnd = aie.getEpisodeNumbers()
            ep = epStart if epEnd == '' else epEnd
            ep = ep if ep != '' else '1'
                       
            item_title = aie.getName()
            item_episode = int(ep)
            item_group = aie.subberTag
            
            torrent['show_title'] = item_title
            torrent['show_episode'] = item_episode
            torrent['show_group'] = item_group

            if not item_title:
                #print "Not recognized: %s\n  %s" % (item['title'], repr(anal))
                torrent['status'] = 'not recognized'
                continue
            
            matcher.set_seq1(item_title.lower())
            for show in self.animelist.itervalues():
                matcher.set_seq2(show['title'].lower())
                ratio = matcher.ratio()
                if ratio > highest_ratio[1]:
                    highest_ratio = (show, ratio)

            if highest_ratio[1] > 0.7:
                # This is the show
                the_show = highest_ratio[0]
                
                torrent['show_id'] = the_show['id']
               
                if item_episode == (the_show['my_progress'] + 1):
                    # Show found!
                    #print "Found!: %s\n  (%d) %s [%d - %s]" % (item['title'], the_show['id'], the_show['title'], item_episode, item_group)
                    torrent['status'] = 'next_episode'
                elif item_episode > (the_show['my_progress'] + 1):
                    torrent['status'] = 'too_next_episode'
                else:
                    # The show was found but this episode was already watched
                    #print "Found but already watched: %s\n  (%d) %s" % (item['title'], the_show['id'], the_show['title'])
                    torrent['status'] = 'already_watched'
            else:
                # This show isn't in the list
                print "Not found: %s" % (item['title'])
                pass

            # Add to the list
            self.torrents[item['title']] = torrent

        self._save()
        print "Done!"
        return self.torrents

with open('/home/z411/.wmal/z411.mal/anime.list') as f:
    animelist = cPickle.load(f)
man = TorrentManager(animelist, None)
d = man.get_torrents()

from operator import itemgetter
sortedlist = sorted(d, key=itemgetter('status'))

for item in sortedlist:
    print repr(item)
