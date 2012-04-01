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
import ConfigParser
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
CONFIG_FILE = os.path.join(os.getenv('HOME'), '.githubnotifier', 'config.cfg')

GITHUB_BLOG_URL = 'https://github.com/blog.atom'
GITHUB_BLOG_USER = 'GitHub Blog'
GITHUB_URL = 'https://github.com/'

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

def get_github_user_organizations(user):
    organizations_cache = os.path.abspath(os.path.join(CACHE_DIR, user + '_orgs.json'))
    if not os.path.exists(organizations_cache):
        try:
            # Fetch userinfo from github
            url = 'https://api.github.com/users/' + user + '/orgs'
            resp = urllib2.urlopen(url).read()
            obj = json.loads(resp)
            organizations = obj

            # Cache the userinfo
            fp = open(organizations_cache, 'w')
            fp.write(json.dumps(organizations))
            fp.close()
        except (urllib2.URLError, httplib.HTTPException):
            # Create a 'fake' user object in case of network errors
            organizations = []

    else:
        # Use cached userinfo
        fp = open(organizations_cache, 'r')
        info = fp.read()
        organizations = json.loads(info)

    # Get all organizations and return the logins of the organizations in an array
    orgs = []
    for item in organizations:
         orgs.append(item['login'])
    return orgs

class GtkGui(object):
    def __init__(self, upd):
        self.upd = upd
        self.logger = logging.getLogger('github-notifier')

        icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'octocat.png'))
        self.systray_icon = gtk.status_icon_new_from_file(icon_path)

        self.menu = gtk.Menu()

        menu_github = gtk.MenuItem('Open GitHub')
        menu_github.connect('activate', self.show_github)
        menu_github.show()
        self.menu.append(menu_github)

        menu_organizations = gtk.CheckMenuItem('Feeds organizations')
        menu_organizations.connect('activate', self.organizations)
        menu_organizations.show()
        if self.upd.organizations:
          menu_organizations.set_active(True)
        self.menu.append(menu_organizations)

        menu_important_authors = gtk.CheckMenuItem('Only Important Authors')
        menu_important_authors.connect('activate', self.important_authors)
        menu_important_authors.show()
        self.menu.append(menu_important_authors)

        menu_important_projects = gtk.CheckMenuItem('Only Important Projects')
        menu_important_projects.connect('activate', self.important_projects)
        menu_important_projects.show()
        self.menu.append(menu_important_projects)

        menu_blacklist_authors = gtk.CheckMenuItem('Exclude Blacklisted Authors')
        menu_blacklist_authors.connect('activate', self.blacklist_authors)
        menu_blacklist_authors.show()
        self.menu.append(menu_blacklist_authors)

        menu_blacklist_projects = gtk.CheckMenuItem('Exclude Blacklisted Projects')
        menu_blacklist_projects.connect('activate', self.blacklist_projects)
        menu_blacklist_projects.show()
        self.menu.append(menu_blacklist_projects)

    
        menu_blacklist_organizations= gtk.CheckMenuItem('Exclude Blacklisted Organizations')
        menu_blacklist_organizations.connect('activate', self.blacklist_organizations)
        menu_blacklist_organizations.show()
        if self.upd.blacklist_organizations:
          menu_blacklist_organizations.set_active(True)
        self.menu.append(menu_blacklist_organizations)


        menu_about = gtk.ImageMenuItem(gtk.STOCK_ABOUT)
        menu_about.connect('activate', self.show_about)
        menu_about.show()
        self.menu.append(menu_about)

        menu_quit = gtk.ImageMenuItem(gtk.STOCK_QUIT)
        menu_quit.connect('activate', gtk.main_quit)
        menu_quit.show()
        self.menu.append(menu_quit)

        # References to the CheckMenuItems
        self.menu_important_authors = menu_important_authors
        self.menu_important_projects = menu_important_projects
        self.menu_blacklist_authors = menu_blacklist_authors
        self.menu_blacklist_projects = menu_blacklist_projects
        self.menu_organizations = menu_organizations
        self.menu_blacklist_organizations= menu_blacklist_organizations



        self.systray_icon.connect('popup_menu', self.show_menu)

        # Initialize the CheckMenuItems
        if self.upd.important_authors:
            menu_important_authors.set_active(True)
        if self.upd.important_projects:
            menu_important_projects.set_active(True)
        if self.upd.blacklist_authors:
            menu_blacklist_authors.set_active(True)
        if self.upd.blacklist_projects:
            menu_blacklist_projects.set_active(True)

    def show_menu(self, icon, button, time):
        self.logger.info('Opening menu')
        self.menu.popup(None, None, gtk.status_icon_position_menu, button,
                        time, icon)

    def important_authors(self, item):
        if item.active:
            self.logger.info('Enabling important authors')
            config = ConfigParser.ConfigParser()
            config.read(CONFIG_FILE)
            items = self.upd.acquire_items(config, "important", "authors")
            if items:
                self.upd.important_authors = True
                self.upd.list_important_authors = items
            else:
                self.menu_important_authors.set_active(False)
        else:
            self.logger.info('Disabling important authors')
            self.upd.important_authors = False

    def important_projects(self, item):
        if item.active:
            self.logger.info('Enabling important projects')
            config = ConfigParser.ConfigParser()
            config.read(CONFIG_FILE)
            items = self.upd.acquire_items(config, "important", "projects")
            if items:
                self.upd.important_projects = True
                self.upd.list_important_projects = items
            else:
                self.menu_important_projects.set_active(False)
        else:
            self.logger.info('Disabling important projects')
            self.upd.important_projects = False

    def blacklist_authors(self, item):
        if item.active:
            self.logger.info('Enabling blacklist authors')
            config = ConfigParser.ConfigParser()
            config.read(CONFIG_FILE)
            items = self.upd.acquire_items(config, "blacklist", "authors")
            if items:
                self.upd.blacklist_authors = True
                self.upd.list_blacklist_authors = items
            else:
                self.menu_blacklist_authors.set_active(False)
        else:
            self.logger.info('Disabling blacklist authors')
            self.upd.blacklist_authors = False

    def blacklist_projects(self, item):
        if item.active:
            self.logger.info('Enabling blacklist projects')
            config = ConfigParser.ConfigParser()
            config.read(CONFIG_FILE)
            items = self.upd.acquire_items(config, "blacklist", "projects")
            if items:
                self.upd.blacklist_projects = True
                self.upd.list_blacklist_projects = items
            else:
                self.menu_blacklist_projects.set_active(False)
        else:
            self.logger.info('Disabling blacklist projects')
            self.upd.blacklist_projects = False

    def organizations(self, item):
        if item.active:
            self.logger.info('Enabling feeds organizations')
            self.upd.organizations = True
        else:
            self.logger.info('Disabling feeds organizations')
            self.upd.organizations = False


    def blacklist_organizations(self, item):
        if item.active:
            self.logger.info('Enabling blacklist organizations')
            config = ConfigParser.ConfigParser()
            config.read(CONFIG_FILE)
            items = self.upd.acquire_items(config, "blacklist", "organizations")
            if items:
                self.upd.blacklist_organizations = True
                self.upd.list_blacklist_organizations= items
            else:
                self.menu_blacklist_organizations.set_active(False)
        else:
            self.logger.info('Disabling blacklist projects')
            self.upd.blacklist_organizations= False

    def show_github(self, item):
        self.logger.info('Opening GitHub website')
        webbrowser.open(GITHUB_URL)

    def show_about(self, item):
        self.logger.info('Showing about dialog')
        dlg = gtk.AboutDialog()
        dlg.set_name('GitHub Notifier')
        dlg.set_version(__version__)
        dlg.set_authors(['Andras Biczo <abiczo@gmail.com>','Hermes Ojeda Ruiz <hermes.ojeda@logicalbricks.com> Organizations feature'])
        dlg.set_copyright('Copyright %s 2009 Andras Biczo' % unichr(169).encode('utf-8'))
        gtk.about_dialog_set_url_hook(lambda widget, link: webbrowser.open(link))
        dlg.set_website('http://github.com/abiczo/github-notifier')
        dlg.set_website_label('Homepage')
        dlg.run()
        dlg.destroy()


class GithubFeedUpdatherThread(threading.Thread):
    def __init__(self, user, token, interval, max_items, hyperlinks, blog,
                 important_authors, important_projects, blacklist_authors,
                 blacklist_projects, organizations, blacklist_organizations):
        threading.Thread.__init__(self)

        self.logger = logging.getLogger('github-notifier')

        self.feeds = [
            'http://github.com/%s.private.atom?token=%s' % (user, token),
            'http://github.com/%s.private.actor.atom?token=%s' % (user, token),
        ]

                
        if blog:
            self.logger.info('Observing the GitHub Blog')
            self.feeds.append(GITHUB_BLOG_URL)

        self.interval = interval
        self.max_items = max_items
        self.hyperlinks = hyperlinks
        self._seen = {}
        self.important_authors = important_authors
        self.important_projects = important_projects
        self.blacklist_authors = blacklist_authors
        self.blacklist_projects = blacklist_projects
        self.organizations = organizations
        self.blacklist_organizations = blacklist_organizations
        self.list_important_authors = []
        self.list_important_projects = []
        self.list_blacklist_authors = []
        self.list_blacklist_projects = []
        self.list_blacklist_organizations = []
        self.users_organizations = get_github_user_organizations(user)
      
        list_organizations = self.users_organizations
        # Blacklist the organizations
        if self.organizations and self.blacklist_organizations:
            list_organizations = filter(lambda x:x not in self.list_blacklist_organizations,self.users_organizations)

        # Add all the organizations feeds to the feeds
        for organization in list_organizations:
            self.feeds.append('https://github.com/organizations/%s/%s.private.atom?token=%s' % (organization, user, token))

    def acquire_items(self, config, category, items):
        config_items = config.get(category, items)
        aquired_items = [item for item in config_items.split(',') if item]
        self.logger.info(
            "Items in {0} {1}: {2}".format(category, items, aquired_items))
        return aquired_items

    def run(self):
        while True:
            self.update_feeds(self.feeds)
            time.sleep(self.interval)

    def process_feed(self, feed_url):
        self.logger.info('Fetching feed %s' % feed_url)


        ####### This is necessary to allow real-time changes
        # Don't allow fetch organizations when is disabled
        if not self.organizations and feed_url.find("organizations") >= 0:
            return []
            
        # Don't allow fetching blacklisted organizations
        if self.organizations and self.blacklist_organizations:
            for organization in self.list_blacklist_organizations:
                if feed_url.find("organizations/%s" % organization) >= 0:
                    return [] 
        ####
        feed = feedparser.parse(feed_url)

        notifications = []
        for entry in feed.entries:
            if not entry['id'] in self._seen:

                if feed_url is GITHUB_BLOG_URL:
                    entry['author'] = GITHUB_BLOG_USER

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
        found_author = False
        found_project = False

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

            # Check for GitHub Blog entry
            if item['author'] == GITHUB_BLOG_USER:
                self.logger.info('Found GitHub Blog item entry')
                n['icon'] = os.path.abspath('octocat.png')

            # Check for important project entry
            if self.important_projects:
                for project in self.list_important_projects:
                    found_project = self.important_repository(item['link'],
                                                              project)
                    if found_project:
                        break

            # Check for important author entry
            if self.important_authors:
                found_author = item['authors'][0]['name'] in self.list_important_authors

            # Report and add only relevant entries
            if self.important_authors and found_author:
                self.logger.info('Found important author item entry')
                l.append(n)
            elif self.important_projects and found_project:
                self.logger.info('Found important project item entry')
                l.append(n)
            elif not self.important_authors and not self.important_projects:

                ignore_author = False
                ignore_project = False

                # Check to see if entry is a blacklisted author
                if self.blacklist_authors and item['authors'][0]['name'] in self.list_blacklist_authors:
                  self.logger.info('Ignoring blacklisted author entry')
                  ignore_author = True

                # Check to see if entry is a blacklisted project
                if self.blacklist_projects:
                    for project in self.list_blacklist_projects:
                        ignore_project = self.important_repository(item['link'],
                                                                  project)
                        if ignore_project:
                            self.logger.info('Ignoring blacklisted project entry')
                            break

                if not ignore_author and not ignore_project:
                    self.logger.info('Found item entry')
                    l.append(n)
            else:
                self.logger.info('Ignoring non-important item entry')

        notification_queue.put(l)

    def important_repository(self, link, project):
        link_parts = link.split('/')

        if len(link_parts) > 4:  # Ensures that the link has enough information
            project_parts = project.split('/')

            # Acquire the parts of the project (account for unique/global repo)
            project_owner = None
            if len(project_parts) == 2:
                project_owner = project_parts[0]
                project = project_parts[1]
            owner_from_link = link_parts[3]
            project_from_link = link_parts[4]

            # True if projects match when there is no owner, or if all match
            return project == project_from_link and (not project_owner or
                   project_owner == owner_from_link)
        else:
            return False


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
                      action='store', type='int', dest='interval', default=5,
                      help='set the feed update interval (in seconds)')
    parser.add_option('-m', '--max-items',
                      action='store', type='int', dest='max_items', default=3,
                      help='maximum number of items to be displayed per update')
    parser.add_option('-t', '--display-timeout',
                      action='store', type='int', dest='timeout',
                      help='set the notification display timeout (in seconds)')
    parser.add_option('-b', '--blog',
                      action='store_true', dest='blog', default=False,
                      help='enable notifications from GitHub\'s blog')
    parser.add_option('-a', '--important_authors',
                      action='store_true', dest='important_authors', default=False,
                      help='only consider notifications from important authors')
    parser.add_option('-o', '--organizations',
                      action='store_true', dest='organizations', default=True,
                      help='consider notifications of all user\'s organizations')
    parser.add_option('-k', '--blacklist_organizations',
                      action='store_true', dest='blacklist_organizations', default=False,
                      help='filter out blacklisted user\'s organizations')
    parser.add_option('-p', '--important_projects',
                      action='store_true', dest='important_projects', default=False,
                      help='only consider notifications from important projects')
    parser.add_option('-u', '--blacklist_authors',
                      action='store_true', dest='blacklist_authors', default=False,
                      help='filter out blacklisted authors')
    parser.add_option('-r', '--blacklist_projects',
                      action='store_true', dest='blacklist_projects', default=False,
                      help='filter out blacklisted projects')
    parser.add_option('-n', '--new-config',
                      action='store_true', dest='new_config', default=False,
                      help='create a new config.cfg at ~/.githubnotifier/')
    parser.add_option('-v', '--verbose',
                      action='store_true', dest='verbose', default=False,
                      help='enable verbose logging')
    (options, args) = parser.parse_args()

    # Create logger
    logger = logging.getLogger('github-notifier')
    handler = logging.StreamHandler()

    if options.verbose:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.WARNING)

    formatter = logging.Formatter('[%(levelname)s] %(asctime)s\n%(message)s',
                                    datefmt='%d %b %H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    if options.interval <= 0:
        logger.error('The update interval must be > 0')
        sys.exit(1)

    if options.max_items <= 0:
        logger.error('The maximum number of items must be > 0')
        sys.exit(1)

    if not os.path.isdir(CACHE_DIR):
        logger.warning('Making the cache directory {0}'.format(CACHE_DIR))
        os.makedirs(CACHE_DIR)

    if not os.path.isfile(CONFIG_FILE) or options.new_config:
        logger.warning('Making the config file {0}'.format(CONFIG_FILE))
        config_file = open(CONFIG_FILE, 'w')
        config_file.write('[important]  # Separated by commas, projects (can' \
                          ' be either <user>/<project> or <project>)\n')
        config_file.write('authors=\nprojects=')
        config_file.write('\n[blacklist]  # Separated by commas, projects (can' \
                          ' be either <user>/<project> or <project>)\n')
        config_file.write('authors=\nprojects=')
        config_file.write('\norganizations=')
        config_file.close()

    if not pynotify.init('github-notifier'):
        logger.error('Couldn\'t initialize pynotify')
        sys.exit(1)

    server_caps = pynotify.get_server_caps()
    if 'body-hyperlinks' in server_caps:
        logger.info('github-notifier is capable of using hyperlinks')
        hyperlinks = True
    else:
        logger.info('github-notifier is not capable of using hyperlinks')
        hyperlinks = False

    (user, token) = get_github_config()
    if not user or not token:
        logger.error('Could not get GitHub username and token from git config')
        sys.exit(1)

    if options.systray_icon:
        logger.info('Creating system tray icon')
        gtk.gdk.threads_init()

    # Start a new thread to check for feed updates
    upd = GithubFeedUpdatherThread(user, token, options.interval,
                                   options.max_items, hyperlinks, options.blog,
                                   options.important_authors,
                                   options.important_projects,
                                   options.blacklist_authors,
                                   options.blacklist_projects,
                                   options.organizations,
                                   options.blacklist_organizations)
    upd.setDaemon(True)
    upd.start()

    DISPLAY_INTERVAL = 1  # In seconds
    if options.systray_icon:
        gui = GtkGui(upd)
        gobject.timeout_add(DISPLAY_INTERVAL * 1000, display_notifications,
                            options.timeout)
        gtk.main()
    else:
        while True:
            display_notifications(options.timeout)
            time.sleep(DISPLAY_INTERVAL)


if __name__ == '__main__':
    main()
