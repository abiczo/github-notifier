import os
import sys
import time
import urllib2
import md5
import simplejson as json
import feedparser

import pygtk
pygtk.require('2.0')
import gobject
import gtk
import pynotify

INTERVAL = 300 # feed checking interval (seconds)
MAX = 3 # max number of notifications to be displayed

CACHE_DIR = os.path.join(os.getenv('HOME'), '.githubnotifier', 'cache')

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

seen = {}
def process_feed(feed_url):
    print 'Fetching feed %s' % feed_url
    feed = feedparser.parse(feed_url)

    notifications = []
    for entry in feed.entries:
        if entry['id'] not in seen:
            notifications.append(entry)
            seen[entry['id']] = 1

    return notifications

def update_feeds(feeds):
    notifications = []
    for feed_url in feeds:
        notifications.extend(process_feed(feed_url))

    notifications.sort(key=lambda e: e['updated'])
    notifications = notifications[-MAX:]

    users = {}
    for item in notifications:
        user = get_github_user_info(item['author'])
        users[item['author']] = user

    for item in notifications:
        user = users[item['author']]
        # default to login name if the user's name is not set
        name = user.get('name', user['login'])
        n = pynotify.Notification(name,
                                  item['title'],
                                  user['avatar_path'])
        n.show()

    return True

def main():
    if not os.path.isdir(CACHE_DIR):
        os.makedirs(CACHE_DIR)

    (user, token) = get_github_config()
    if not user or not token:
        print >>sys.stderr, 'Error: couldn\'t get github config.'
        sys.exit(1)

    github_feeds = (
        'http://github.com/%s.private.atom?token=%s' % (user, token),
        'http://github.com/%s.private.actor.atom?token=%s' % (user, token),
    )

    if not pynotify.init('github-notifier'):
        print >>sys.stderr, 'Error: couldn\'t initialize pynotify.'
        sys.exit(1)

    while True:
        update_feeds(github_feeds)
        time.sleep(INTERVAL)

if __name__ == '__main__':
    main()
