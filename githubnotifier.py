import os
import sys
import time
import urllib2
import Queue
import threading
import md5
import optparse
import logging
import simplejson as json
import feedparser

import webbrowser
import pygtk
pygtk.require('2.0')
import gobject
import gtk
import pynotify

__version__ = '0.1'

INTERVAL = 300 # feed checking interval (seconds)
MAX = 3 # max number of notifications to be displayed

CACHE_DIR = os.path.join(os.getenv('HOME'), '.githubnotifier', 'cache')

notification_queue = Queue.Queue()

def get_github_config():
    fp = os.popen('git config --get github.user')
    user = fp.readline().strip()
    fp.close()

    fp = os.popen('git config --get github.token')
    token = fp.readline().strip()
    fp.close()

    return (user, token)

def get_github_user_info(username):
    info_cache = os.path.abspath(os.path.join(CACHE_DIR, username + '.json'))
    if not os.path.exists(info_cache):
        # Fetch userinfo from github
        url = 'http://github.com/api/v1/json/' + username
        resp = urllib2.urlopen(url).read()
        obj = json.loads(resp)
        user = obj['user']
        user['avatar_path'] = os.path.abspath(os.path.join(CACHE_DIR,
                                                           username + '.jpg'))

        # Cache the userinfo
        fp = open(info_cache, 'w')
        fp.write(json.dumps(user))
        fp.close()
    else:
        # Use cached userinfo
        fp = open(info_cache, 'r')
        info = fp.read()
        user = json.loads(info)

    if not os.path.exists(user['avatar_path']):
        # Fetch the user's gravatar
        if 'email' in user:
            hexdig = md5.new(user['email'].lower()).hexdigest()
            gravatar_url = 'http://www.gravatar.com/avatar/%s.jpg?s=48' % hexdig
        else:
            gravatar_url = 'http://www.gravatar.com/avatar/?s=48'

        avatar_data = urllib2.urlopen(gravatar_url).read()

        # Cache the image
        fp = open(user['avatar_path'], 'wb')
        fp.write(avatar_data)
        fp.close()

    return user


class GtkGui(object):
    def __init__(self):
        icon_path = os.path.join(os.path.dirname(__file__), 'octocat.png')
        self.systray_icon = gtk.status_icon_new_from_file(
            os.path.abspath(icon_path))

        self.menu = gtk.Menu()

        menu_about = gtk.ImageMenuItem(gtk.STOCK_ABOUT)
        menu_about.connect('activate', self.show_about)
        menu_about.show()
        self.menu.append(menu_about)

        menu_quit = gtk.ImageMenuItem(gtk.STOCK_QUIT)
        menu_quit.connect('activate', gtk.main_quit)
        menu_quit.show()
        self.menu.append(menu_quit)

        self.systray_icon.connect('popup_menu', self.show_menu)

    def show_menu(self, icon, button, time):
        self.menu.popup(None, None, gtk.status_icon_position_menu, button,
                        time, icon)

    def show_about(self, item):
        dlg = gtk.AboutDialog()
        dlg.set_name('GitHub Notifier')
        dlg.set_version(__version__)
        dlg.set_authors(['Andras Biczo <abiczo@gmail.com>'])
        dlg.set_copyright('Copyright %s 2009 Andras Biczo' % unichr(169).encode('utf-8'))
        gtk.about_dialog_set_url_hook(lambda widget, link: webbrowser.open(link))
        dlg.set_website('http://github.com/abiczo/github-notifier')
        dlg.set_website_label('Homepage')
        dlg.run()
        dlg.destroy()


class GithubFeedUpdatherThread(threading.Thread):
    def __init__(self, user, token, interval):
        threading.Thread.__init__(self)

        self.feeds = [
            'http://github.com/%s.private.atom?token=%s' % (user, token),
            'http://github.com/%s.private.actor.atom?token=%s' % (user, token),
        ]
        self.interval = interval
        self._seen = {}

    def run(self):
        while True:
            self.update_feeds(self.feeds)
            time.sleep(self.interval)

    def process_feed(self, feed_url):
        log = logging.getLogger('github-notifier')
        log.info('Fetching feed %s' % feed_url)
        feed = feedparser.parse(feed_url)

        notifications = []
        for entry in feed.entries:
            if not entry['id'] in self._seen:
                notifications.append(entry)
                self._seen[entry['id']] = 1

        return notifications

    def update_feeds(self, feeds):
        notifications = []
        for feed_url in feeds:
            notifications.extend(self.process_feed(feed_url))

        notifications.sort(key=lambda e: e['updated'])
        notifications = notifications[-MAX:]

        users = {}
        l = []
        for item in notifications:
            if not item['author'] in users:
                users[item['author']] = get_github_user_info(item['author'])

            user = users[item['author']]
            n = {'title': user.get('name', user['login']),
                 'message': item['title'],
                 'icon': user['avatar_path']}
            l.append(n)

        notification_queue.put(l)


def display_notifications():
    while True:
        try:
            items = notification_queue.get_nowait()
            for i in items:
                n = pynotify.Notification(i['title'], i['message'], i['icon'])
                n.show()

            notification_queue.task_done()
        except Queue.Empty:
            break

    return True

def main():
    parser = optparse.OptionParser()
    parser.add_option('--no-systray-icon', dest='systray_icon',
                      action='store_false', default=True,
                      help='don\'t show the systray icon')
    parser.add_option('-v', '--verbose',
                      action='store_true', dest='verbose', default=False,
                      help='enable verbose logging')
    (options, args) = parser.parse_args()

    log = logging.getLogger('github-notifier')
    log.addHandler(logging.StreamHandler())
    if options.verbose:
        log.setLevel(logging.INFO)
    else:
        log.setLevel(logging.ERROR)

    if not os.path.isdir(CACHE_DIR):
        os.makedirs(CACHE_DIR)

    if not pynotify.init('github-notifier'):
        print >>sys.stderr, 'Error: couldn\'t initialize pynotify.'
        sys.exit(1)

    (user, token) = get_github_config()
    if not user or not token:
        print >>sys.stderr, 'Error: couldn\'t get github config.'
        sys.exit(1)

    if options.systray_icon:
        gtk.gdk.threads_init()

    # Start a new thread to check for feed updates
    upd = GithubFeedUpdatherThread(user, token, INTERVAL)
    upd.setDaemon(True)
    upd.start()

    DISPLAY_INTERVAL = 1 # seconds
    if options.systray_icon:
        gui = GtkGui()
        gobject.timeout_add(DISPLAY_INTERVAL * 1000, display_notifications)
        gtk.main()
    else:
        while True:
            display_notifications()
            time.sleep(DISPLAY_INTERVAL)


if __name__ == '__main__':
    main()
