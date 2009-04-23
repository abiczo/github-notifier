Github-notifier
===============

This is a Linux/Python port of miyagawa's [github-growler][github-growler].

It fetches your Github dashboard feeds and displays a notification
for new items.

Install
-------

### From source

As PyGTK can't be installed using setuptools you'll have to install PyGTK
from your distribution. On Ubuntu you can do this using the following command:

    apt-get install python-gtk2

Then install the required dependencies:

    easy_install feedparser simplejson

Then clone the repository and install the module:

    git clone git://github.com/abiczo/github-notifier.git
    cd github-notifier
    python setup.py install

Now you can run github-notifier like this:

    github-notifier

Use `--help` for a list of available command line options.

### Packages

An Arch Linux package is available [here][arch-package].

Screenshot
----------

Screenshot using [notify-osd][notify-osd]:

![Screenshot](http://cloud.github.com/downloads/abiczo/github-notifier/github-notifier.png)

TODO
----

* Expire the user info and avatar caches after some time
* Notify-osd has problems when the notification message contains
  an '&' character

Notes
-----

The Octocat logo is taken from <http://github.com/mojombo/github-media>.

[github-growler]: http://github.com/miyagawa/github-growler
[arch-package]: http://aur.archlinux.org/packages.php?ID=25385
[notify-osd]: https://wiki.ubuntu.com/NotifyOSD
