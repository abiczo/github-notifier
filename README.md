Github-notifier
===============

This is a Linux/Python port of miyagawa's [github-growler][github-growler].

It fetches your Github dashboard feeds and displays a notification
for new items.

Install
-------

As PyGTK can't be installed using setuptools you'll have to install PyGTK
from your distribution. On Ubuntu you can do this using the following command:

    apt-get install python-gtk2

Then clone the repository and install the module:

    git clone git://github.com/abiczo/github-notifier.git
    cd github-notifier
    python setup.py install

Now you can run github-notifier like this:

    github-notifier

TODO
----

* Make the update interval configurable
* Display systray icon

[github-growler]: http://github.com/miyagawa/github-growler
