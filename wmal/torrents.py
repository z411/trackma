import utils
import cPickle
import difflib
import urllib
import xml.etree.ElementTree as ET

class TorrentManager(object):
    torrents = list()

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
        for node in dom.iter('item'):
            item = {}
            for child in node:
                if child.tag == 'title':
                    item['title'] = child.text
                elif child.tag == 'link':
                    item['link'] = child.text
                elif child.tag == 'description':
                    item['description'] = child.text
                
            yield item

    def get_torrents(self):
        print "Downloading list..."
        dom = self._download_feed(self.FEED_URL)
        print "Parsing..."
        matcher = difflib.SequenceMatcher()
        print "Successful matches:"
        for item in self._parse_feed(dom):
            highest_ratio = (None, 0)
            anal = utils.analyze(item['title'])
            (item_title, item_episode) = anal
            if not item_title:
                #print "Not recognized: %s\n  %s" % (item['title'], repr(anal))
                continue
            
            matcher.set_seq1(item_title.lower())
            for show in self.animelist.itervalues():
                matcher.set_seq2(show['title'].lower())
                ratio = matcher.ratio()
                if ratio > highest_ratio[1]:
                    highest_ratio = (show, ratio)

            if highest_ratio[1] > 0.7:
                the_show = highest_ratio[0]
                if item_episode > the_show['my_progress']:
                    # Show found!
                    print "Found!: %s\n  (%d) %s" % (item['title'], the_show['id'], the_show['title'])
                else:
                    # The show was found but this episode was already watched
                    #print "Found but already watched: %s\n  (%d) %s" % (item['title'], the_show['id'], the_show['title'])
                    pass
            else:
                # This show isn't in the list
                #print "Not found: %s\n  %s" % (item['title'], repr(anal))
                pass

        print "Done!"

with open('/home/z411/.wmal/z411.mal/anime.list') as f:
    animelist = cPickle.load(f)
man = TorrentManager(animelist, None)
man.get_torrents()
