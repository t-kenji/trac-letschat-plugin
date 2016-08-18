# trac-letschat-plugin

Plugin to announce Trac changes in [letschat](https://sdelements.github.io/lets-chat/) service.


## Updating on mustafar
As `www-trac`, activate the venvt, and then in `~/trac-letschat-plugin` run:
```
git fetch origin master
git reset --hard FETCH_HEAD
rm -r dist
python setup.py bdist_egg
cp dist/LetschatNotificationPlugin-0.2-py2.7.egg   ../trac/plugins/
```

Then restart uwsgi by running `sudo service uwsgi restart`

## Installation

Requirements:

    Requests library: https://pypi.python.org/pypi/requests
    $ pip install requests

Deploy to a specific Trac environment:

    $ cd /path/to/pluginsource
    $ python setup.py bdist_egg
    $ cp dist/*.egg /path/to/projenv/plugins

Enable plugin in trac.ini:

    [components]
    letschat_notification.* = enabled

Configuration in trac.ini:

    [letschat]
    webapi = http://<servcer ip>/rooms
	token = <letschat authentication token>
    ticket_room = trac_ticket_update_notifier
    ticket_fields = type,component,resolution
	wiki_room = trac_wiki_update_notifier
	blog_room = trac_blog_update_notifier



## License

Copyright (c) 2016, Takahashi Kenji  
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions
are met:

1. Redistributions of source code must retain the above copyright
   notice, this list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright
   notice, this list of conditions and the following disclaimer in
   the documentation and/or other materials provided with the
   distribution.
3. The name of the author may not be used to endorse or promote
   products derived from this software without specific prior
   written permission.

THIS SOFTWARE IS PROVIDED BY THE AUTHOR `AS IS'' AND ANY EXPRESS
OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE
GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
