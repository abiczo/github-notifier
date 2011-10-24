Github-notifier
===============

This is a Linux/Python port of miyagawa's [github-growler][github-growler].

It fetches your Github dashboard feeds and displays a notification for new
items. There is additional features like filtering only notifications from
important authors and/or projects. The GitHub blog entries can also be seen in
the notifications if desired.

Requirements
------------

* python 2.5, 2.6 or 2.7
* feedparser
* simplejson (not needed for python 2.6)

Install
-------

First install the package dependencies (using Ubuntu)

    sudo apt-get install python-gtk2 python-feedparser python-simplejson

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

### Filtering Feature

Authors are filtered when using the `-a` flag. Projects are filtered when using
the `-p` flag. A *config.cfg* file is present within your *~/.githubnotifier/*
directory. The file will be generated if it is not present at run-time.

The *config.cfg* format is as follows:
    
    [important]
    authors=bob,fred,mary
    projects=github-notifier,rails,bob/my-project
    
This configuration will only show notifications that have *bob*, *fred* or
*mary* as the authors. The projects can either be in a general format (ex:
*github-notifier* or *rails*) to only show notifications that deal with either
of those projects. The general format will show notifications that match the
project name, regardless of who is the owner of the repository. The stricter
format (ex: *bob/my-project*) will only show notifications of the *my-project*
repository if the owner if *bob*.

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
