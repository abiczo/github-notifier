import os
import sys
import time
import socket
import urllib2
import httplib
import Queue
import threading
import hashlib
import optparse
import logging
try:
    import json
except ImportError:
    import simplejson as json
import feedparser

import webbrowser
import pygtk
pygtk.require('2.0')
import gobject
import gtk
import pynotify

__version__ = '0.1'

SOCKET_TIMEOUT = 30

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
        try:
            # Fetch userinfo from github
            url = 'http://github.com/api/v1/json/' + username
            resp = urllib2.urlopen(url).read()
            obj = json.loads(resp)
            user = obj['user']

            # Cache the userinfo
            fp = open(info_cache, 'w')
            fp.write(json.dumps(user))
            fp.close()
        except (urllib2.URLError, httplib.HTTPException):
            # Create a 'fake' user object in case of network errors
            user = {'login': username}

    else:
        # Use cached userinfo
        fp = open(info_cache, 'r')
        info = fp.read()
        user = json.loads(info)

    user['avatar_path'] = os.path.abspath(os.path.join(CACHE_DIR,
                                                       username + '.jpg'))
    if not os.path.exists(user['avatar_path']):
        # Fetch the user's gravatar
        if 'email' in user:
            hexdig = hashlib.md5(user['email'].lower()).hexdigest()
            gravatar_url = 'http://www.gravatar.com/avatar/%s.jpg?s=48' % hexdig
        else:
            gravatar_url = 'http://www.gravatar.com/avatar/?s=48'

        try:
            avatar_data = urllib2.urlopen(gravatar_url).read()

            # Cache the image
            fp = open(user['avatar_path'], 'wb')
            fp.write(avatar_data)
            fp.close()
        except (urllib2.URLError, httplib.HTTPException):
            pass

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
    def __init__(self, user, token, interval, max_items, hyperlinks):
        threading.Thread.__init__(self)

        self.feeds = [
            'http://github.com/%s.private.atom?token=%s' % (user, token),
            'http://github.com/%s.private.actor.atom?token=%s' % (user, token),
        ]
        self.interval = interval
        self.max_items = max_items
        self.hyperlinks = hyperlinks
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
        notifications = notifications[-self.max_items:]

        users = {}
        l = []
        for item in notifications:
            if not item['author'] in users:
                users[item['author']] = get_github_user_info(item['author'])

            user = users[item['author']]
            if self.hyperlinks and 'link' in item:
                # simple heuristic: use the second word for the link
                parts = item['title'].split(' ')
                if len(parts) > 1:
                    parts[1] = '<a href="%s">%s</a>' % (item['link'], parts[1])
                message = ' '.join(parts)
            else:
                message = item['title']
            n = {'title': user.get('name', user['login']),
                 'message': message,
                 'icon': user['avatar_path']}
            l.append(n)

        notification_queue.put(l)


def display_notifications(display_timeout=None):
    while True:
        try:
            items = notification_queue.get_nowait()
            for i in items:
                n = pynotify.Notification(i['title'], i['message'], i['icon'])
                if display_timeout is not None:
                    n.set_timeout(display_timeout * 1000)
                n.show()

            notification_queue.task_done()
        except Queue.Empty:
            break

    return True

def main():
    socket.setdefaulttimeout(SOCKET_TIMEOUT)

    parser = optparse.OptionParser()
    parser.add_option('--no-systray-icon', dest='systray_icon',
                      action='store_false', default=True,
                      help='don\'t show the systray icon')
    parser.add_option('-i', '--update-interval',
                      action='store', type='int', dest='interval', default=300,
                      help='set the feed update interval (in seconds)')
    parser.add_option('-m', '--max-items',
                      action='store', type='int', dest='max_items', default=3,
                      help='maximum number of items to be displayed per update')
    parser.add_option('-t', '--display-timeout',
                      action='store', type='int', dest='timeout',
                      help='set the notification display timeout (in seconds)')
    parser.add_option('-v', '--verbose',
                      action='store_true', dest='verbose', default=False,
                      help='enable verbose logging')
    (options, args) = parser.parse_args()

    if options.interval <= 0:
        print >>sys.stderr, 'Error: the update interval must be > 0.'
        sys.exit(1)

    if options.max_items <= 0:
        print >>sys.stderr, 'Error: the maximum number of items must be > 0.'
        sys.exit(1)

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

    server_caps = pynotify.get_server_caps()

    if 'body-hyperlinks' in server_caps:
        hyperlinks = True
    else:
        hyperlinks = False

    (user, token) = get_github_config()
    if not user or not token:
        print >>sys.stderr, 'Error: couldn\'t get github config.'
        sys.exit(1)

    if options.systray_icon:
        gtk.gdk.threads_init()

    # Start a new thread to check for feed updates
    upd = GithubFeedUpdatherThread(user, token, options.interval,
                                   options.max_items, hyperlinks)
    upd.setDaemon(True)
    upd.start()

    DISPLAY_INTERVAL = 1 # seconds
    if options.systray_icon:
        gui = GtkGui()
        gobject.timeout_add(DISPLAY_INTERVAL * 1000, display_notifications,
                            options.timeout)
        gtk.main()
    else:
        while True:
            display_notifications(options.timeout)
            time.sleep(DISPLAY_INTERVAL)


if __name__ == '__main__':
    main()
