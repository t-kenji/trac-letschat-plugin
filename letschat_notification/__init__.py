# -*- coding: utf8 -*-

import json
import requests
import re
import difflib

from trac.core import Component, implements
from trac.config import ListOption, Option
from trac.util.datefmt import format_date, format_datetime, get_timezone
from trac.util.text import wrap
from trac.ticket.api import TicketSystem, ITicketChangeListener
from trac.wiki.api import IWikiChangeListener

try:
    from tracfullblog.api import IBlogChangeListener
    from tracfullblog.model import BlogPost, BlogComment
except:
    IBlogChangeListener = None

try:
    from tracjanusgateway.api import IVideocallListener
except:
    IVideocallListener = None

def diff_cleanup(gen):
    """
    """

    for piece in gen:
        if piece.startswith('---'):
            continue
        if piece.startswith('+++'):
            continue
        if piece.startswith('@@'):
            yield '\n'
        else:
            yield piece

class LetschatTicketNotifcationModule(Component):
    """
    """

    implements(ITicketChangeListener)

    webapi = Option('letschat', 'webapi', '',
                    doc="REST-like API for let's chat")
    token = Option('letschat', 'token', '',
                   doc="Authentication Token for let's chat")
    room = Option('letschat', 'ticket_room', '',
                  doc="room name on let's chat")
    ticket_fields = Option('letschat', 'ticket_fields', 'type,priority,component,resolution',
                           doc="Fields that should be reported")

    def _prepare_ticket_values(self, ticket):
        values = ticket.values.copy()
        values['id'] = '#' + str(ticket.id)
        values['url'] = ticket.env.abs_href.ticket(ticket.id)
        values['project'] = ticket.env.project_name.encode('utf-8').strip()
        return values

    def _format_date_field(self, value, date_type, date_format):
        tzinfo = get_timezone(self.config.get('trac', 'default_timezone'))
        if date_type == 'date':
            return format_date(value, tzinfo=tzinfo, format=date_format) \
                   if value else u''
        else:
            return format_datetime(value, tzinfo=tzinfo, format=date_format) \
                   if value else u''

    def _ticket_notify(self, action, values):
        values['author'] = values['author'].title()
        values['type'] = values['type'].title()

        if (values.get('owner') != None) and (values.get('owner') != "") and (values.get('owner').lower() != values.get('author').lower()):
            text = u'@{} '.format(values['owner'])
        else:
            text = ''
        add_author = ('comment' not in values)
        if action == 'new':
            text += u'New '
            add_author = True

        text += u'{type} {id}: {summary}'.format(**values)

        if 'new_status' in values:
            text += u' ⇒ {}'.format(values['new_status'])
            add_author = True

        if add_author:
            text += u' (by {})'.format(values['author'])

        text += u'\n'

        fields = TicketSystem(self.env).get_ticket_fields()
        fields = dict((f['name'], f) for f in fields)
        for k, v in values.get('attrib', {}).items():
            text += u' * {field}: {value}\n'.format(field=fields.get(k, {}).get('label', k.title()),
                                                    value=v)

        if (('changes' in values) and (len(values.get('changes', {})) > 0)):
            text += u'Changes (by {})\n'.format(values['author'])
            for k, v in values.get('changes', {}).items():
                text += u' * {field}: '.format(field=fields.get(k, {}).get('label', k.title()))
                if k in ('description', 'comment'):
                    text += u'see below\n'
                else:
                    v0 = v[0] if v[0] else u''
                    v1 = v[1] if v[1] else u'Deleted'
                    if v0:
                        text += u'{} -> {}\n'.format(v0, v1)
                    else:
                        text += u'{}\n'.format(v1)
            add_author = True

        if 'description' in values:
            description = values['description']
            if len(description) > 500:
                truncated = description[498:]
                mensions = re.findall(r'\s@[0-9a-zA-Z]+', truncated)
                description = description[:497] + ' ... (truncated)' + ' '.join(mensions)
            description = re.sub(r'({{{(#![a-z]+)*|}}})', '', description)
            text += u'<<Description>>\n' + description + u'\n'
        else:
            desc_changeset= values.get('changes', {}).get('description', ())
            if len(desc_changeset) > 0:
                desc_diff = '\n'.join(diff_cleanup(difflib.unified_diff(
                        wrap(desc_changeset[0], cols = 80).split('\n'),
                        wrap(desc_changeset[1], cols = 80).split('\n'),
                        lineterm = '',n = 3
                )))
                if len(desc_diff) > 500:
                    truncated = desc_diff[498:]
                    mensions = re.findall(r'\s@[0-9a-zA-Z]+', truncated)
                    desc_diff = desc_diff[:497] + ' ... (truncated)' + ' '.join(mensions)
                text += u'<<Description>>\n' + desc_diff[2:] + u'\n'

        if 'comment' in values:
            comment = values['comment']
            if len(comment) > 500:
                truncated = comment[498:]
                mensions = re.findall(r'\s@[0-9a-zA-Z]+', truncated)
                comment = comment[:497] + ' ... (truncated)' + ' '.join(mensions)
            comment = re.sub(r'({{{(#![a-z]+)*|}}})', '', comment)
            text += u'<<Comment'
            if not add_author:
                text += u' by {}'.format(values['author'])
            text += u'>>\n' + comment + u'\n'
        else:
            comment_changeset= values.get('changes', {}).get('comment', ())
            if len(comment_changeset) > 0:
                comment_diff = '\n'.join(diff_cleanup(difflib.unified_diff(
                        wrap(comment_changeset[0], cols = 80).split('\n'),
                        wrap(comment_changeset[1], cols = 80).split('\n'),
                        lineterm = '',n = 3
                )))
                if len(comment_diff) > 500:
                    truncated = comment_diff[498:]
                    mensions = re.findall(r'\s@[0-9a-zA-Z]+', truncated)
                    comment_diff = comment_diff[:497] + ' ... (truncated)' + ' '.join(mensions)
                text += u'<<Comment>>\n' + comment_diff[2:] + u'\n'

        text += u'Ticket URL: {url}\n'.format(**values)
        if ('cc' in values) and (len(values['cc']) > 0):
            cc = u''
            for mentor in values['cc'].split(', '):
                if mentor.lower() != values.get('author').lower():
                    if len(cc) == 0:
                        cc += mentor
                    else:
                        cc = ', '.join([cc, mentor])

            cc = re.sub(r'([0-9a-z]+)', r'@\1', cc)
            text += u'Cc: {}\n'.format(cc)

        #room = self._detect_room(values) or self.room
        room = self.room

        try:
            requests.post(self.webapi + '/' + room + '/messages',
                          data={'text': text},
                          auth=(self.token, 'dummy'),
                          timeout=1.0)
        except requests.exceptions.RequestException:
            return False
        return True

    def _detect_room(self, values):
        if values.get('milestone'):
            if 'yourfirm' in values['milestone'].lower():
                room_name = 'yourfirm'
            else:
                room_name = values['milestone'].lower()
            return "" + room_name
        if values.get('component') == 'support':
            return 'support'
        return None

    def ticket_created(self, ticket):
        values = self._prepare_ticket_values(ticket)
        values['author'] = values['reporter']
        fields = self.ticket_fields.split(',')
        attrib = {}

        if 'description' in fields:
            fields.remove('description')

        for field in fields:
            if (ticket[field] is not None) and (ticket[field] != ''):
                if field in ticket.time_fields:
                    date_type = ticket.fields.by_name(field).get('format')
                    val = self._format_date_field(ticket[field], date_type, '%Y/%m/%d')
                else:
                    val = ticket[field]
                attrib[field] = val

        values['attrib'] = attrib

        self._ticket_notify('new', values)

    def ticket_changed(self, ticket, comment, author, old_values):
        values = self._prepare_ticket_values(ticket)

        if values['changetime']:
            cnum = ticket.get_comment_number(values['changetime'])
            if cnum is not None:
                values['url'] += '#comment:{}'.format(cnum)

        if comment:
            values['comment'] = comment

        values['author'] = author or 'unknown'
        if 'status' in old_values:
            if ticket.values.get('status') != old_values['status']:
                values['new_status'] = ticket.values['status']
                if 'resolution' in old_values:
                    values['new_status'] += ' [{}]'.format(ticket['resolution'])
                    del old_values['resolution']  # prevent this from appearing in changes

        del values['description']

        fields = self.ticket_fields.split(',')
        changes = {}

        for field in fields:
            if field in old_values:
                if field in ticket.time_fields:
                    date_type = ticket.fields.by_name(field).get('format')
                    old_val = self._format_date_field(old_values[field], date_type, '%Y/%m/%d')
                    new_val = self._format_date_field(ticket[field], date_type, '%Y/%m/%d')
                else:
                    old_val = old_values[field]
                    new_val = ticket[field]
                changes[field] = (old_val, new_val)

        if (len(changes) > 0) or ('comment' in values):
            values['changes'] = changes

            self._ticket_notify('edit', values)

    def ticket_deleted(self, ticket):
        pass

    def ticket_comment_modified(self, ticket, cdate, author, comment, old_comment):
        values = self._prepare_ticket_values(ticket)
        values['author'] = author or 'unknown'
        cnum = ticket.get_comment_number(cdate)
        if cnum is not None:
            values['url'] += '#comment:{}'.format(cnum)

        del values['description']

        changes = {}
        changes['comment'] = ( old_comment, comment )

        values['changes'] = changes

        self._ticket_notify('edit', values)

class LetschatWikiNotifcationModule(Component):
    """
    """

    implements(IWikiChangeListener)

    webapi = Option('letschat', 'webapi', '',
                    doc="REST-like API for let's chat")
    token = Option('letschat', 'token', '',
                   doc="Authentication Token for let's chat")
    room = Option('letschat', 'wiki_room', '',
                  doc="room name on let's chat")

    def _prepare_wiki_values(self, page):
        values = {}
        values['name'] = page.name
        values['url'] = self.env.abs_href.wiki(page.name)
        return values

    def _wiki_notify(self, action, values):
        text = ''
        add_author = False
        if action == 'new':
            text += u'New '
            add_author = True
        elif action == 'delete':
            text += u'Deleted '
            add_author = True

        text += u'{}'.format(values['name'])
        if add_author:
            text += u' (by {})'.format(values['author'])

        text += u'\n'

        if action == 'edit':
            text += u'Changes (by {})\n'.format(values['author'])
            for k, v in values.get('changes', {}).items():
                text += u' * ' + k.title() + u': {}\n'.format(v)
            add_author = True

        if 'comment' in values:
            text += u'<<Comment'
            if not add_author:
                text += u' by {}'.format(values['author'])
            text += u'>>\n' + values['comment'] + u'\n'

        text += u'Wiki URL: {url}'.format(**values)

        room = self.room

        try:
            requests.post(self.webapi + '/' + room + '/messages',
                          data={'text': text},
                          auth=(self.token, 'dummy'),
                          timeout=1.0)
        except requests.exceptions.RequestException:
            return False
        return True

    def wiki_page_added(self, page):
        version, time, author, comment, ipnr = page.get_history().next()
        values = self._prepare_wiki_values(page)
        values['author'] = author
        if (len(comment) > 0):
            values['comment'] = comment

        self._wiki_notify('new', values)

    def wiki_page_changed(self, page, version, time, comment, author, ipnr):
        values = self._prepare_wiki_values(page)
        values['author'] = author
        if (len(comment) > 0):
            values['comment'] = comment

        changes = {}
        changes['version'] = version
        changes['changeset'] = self.env.abs_href.wiki(page.name, action='diff', version=version)
        values['changes'] = changes

        self._wiki_notify('edit', values)

    def wiki_page_deleted(self, page):
        pass

    def wiki_page_version_deleted(self, page):
        pass

    def wiki_page_renamed(self, page, old_name):
        pass

class LetschatBlogNotifcationModule(Component):
    """
    """

    if IBlogChangeListener:
        implements(IBlogChangeListener)

    webapi = Option('letschat', 'webapi', '',
                    doc="REST-like API for let's chat")
    token = Option('letschat', 'token', '',
                   doc="Authentication Token for let's chat")
    room = Option('letschat', 'blog_room', '',
                  doc="room name on let's chat")

    def _blog_notify(self, action, values):
        values['author'] = values['author'].title()

        text = ''
        add_author = ('comment' not in values)
        if action == 'new':
            text += u'New '
            add_author = True
        elif action =='edit':
            text += u'Update '
        elif action == 'delete':
            text += u'Deleted '

        text += u'{name}: {title}'.format(**values)
        if add_author:
            text += u' (by {})'.format(values['author'])

        text += u'\n'

        if 'body' in values:
            body = values['body']
            if len(body) > 500:
                truncated = body[498:]
                mensions = re.findall(r'@[a-z]+', truncated)
                body = body[:497] + ' ... ' + ' '.join(mensions)
            body = re.sub(r'({{{(#![a-z]+)*|}}})', '', body)
            text += u'<<body>>\n' + body + u'\n'

        if 'comment' in values:
            comment = values['comment']
            if len(comment) > 500:
                truncated = comment[498:]
                mensions = re.findall(r'@[a-z]+', truncated)
                comment = comment[:497] + ' ... ' + ' '.join(mensions)
            comment = re.sub(r'({{{(#![a-z]+)*|}}})', '', comment)
            text += u'<<Comment'
            if not add_author:
                text += u' by {}'.format(values['author'])
            text += u'>>\n' + comment + u'\n'

        text += u'Blog URL: {url}'.format(**values)

        room = self.room

        try:
            requests.post(self.webapi + '/' + room + '/messages',
                          data={'text': text},
                          auth=(self.token, 'dummy'),
                          timeout=1.0)
        except requests.exceptions.RequestException:
            return False
        return True

    def blog_post_changed(self, postname, version):
        if version == 1:
            action = 'new'
        else:
            action = 'edit'

        bp = BlogPost(self.env, postname, version)
        values = {}
        values['url'] = '{}/blog/{}'.format(self.env.abs_href(), postname)
        values['title'] = bp.title
        values['name'] = bp.name
        values['author'] = bp.version_author
        values['body'] = bp.body
        if len(bp.version_comment) > 0:
            values['comment'] = bp.version_comment

        self._blog_notify(action, values)

    def blog_post_deleted(self, postname, version, fields):
        pass

    def blog_comment_added(self, postname, number):
        bp = BlogPost(self.env, postname, 0)
        bc = BlogComment(self.env, postname, number)
        values = {}
        values['url'] = '{}/blog/{}'.format(self.env.abs_href(), postname)
        values['title'] = bp.title
        values['name'] = bp.name
        values['author'] = bc.author
        values['comment'] = bc.comment
        self._blog_notify('edit', values)

    def blog_comment_deleted(self, postname, number, fields):
        pass

class LetschatJanusgwNotificationModule(Component):
    """
    """

    if IVideocallListener:
        implements(IVideocallListener)

    webapi = Option('letschat', 'webapi', '',
                    doc="REST-like API for let's chat")
    token = Option('letschat', 'token', '',
                   doc="Authentication Token for let's chat")
    room = Option('letschat', 'janusgw_room', '',
                  doc="room name on let's chat")

    def _videocall_notify(self, event, values):
        text = ''
        if event == 'missedcall':
            text += 'Missed call from {caller} to @{callee}.'.format(**values)

        if 'comment' in values:
            text += u'\n<<Comment>>\n{}'.format(values.get('comment'))

        room = self.room

        try:
            requests.post(self.webapi + '/' + room + '/messages',
                          data={'text': text},
                          auth=(self.token, 'dummy'),
                          timeout=1.0)
        except requests.exceptions.RequestException:
            return False
        return True

    def videocall_missedcall(self, callee, caller, comment):
        values = {
            'callee': callee,
            'caller': caller,
        }
        if comment and len(comment) > 0:
            values['comment'] = comment

        self._videocall_notify('missedcall', values)
