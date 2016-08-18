# -*- coding: utf8 -*-

import json
import requests
import re
from trac.core import Component, implements
from trac.config import ListOption, Option
from trac.ticket.api import ITicketChangeListener
from trac.wiki.api import IWikiChangeListener

from tracfullblog.api import IBlogChangeListener
from tracfullblog.model import BlogPost, BlogComment


def prepare_ticket_values(ticket):
    values = ticket.values.copy()
    values['id'] = '#' + str(ticket.id)
    values['url'] = ticket.env.abs_href.ticket(ticket.id)
    values['project'] = ticket.env.project_name.encode('utf-8').strip()
    return values


class LetschatNotifcationPlugin(Component):
    implements(ITicketChangeListener)
    implements(IWikiChangeListener)
    implements(IBlogChangeListener)

    webapi = Option('letschat', 'webapi', '',
                     doc="REST-like API for let's chat")
    token = Option('letschat', 'token', '',
                   doc="Authentication Token for let's chat")
    ticket_room = Option('letschat', 'ticket_room', '',
                  doc="room name on let's chat")
    ticket_fields = Option('letschat', 'ticket_fields', 'type,priority,component,resolution',
                    doc="Fields that should be reported")
    ignore_tickets = ListOption('letschat', 'ignore_tickets', '',
                                doc="Comma separated list of tickets that should be ignored")
    wiki_room = Option('letschat', 'wiki_room', '',
                       doc="room name on let's chat")
    blog_room = Option('letschat', 'blog_room', '',
                       doc="room name on let's chat")

    def __init__(self, *args, **kwargs):
        super(Component, self).__init__(*args, **kwargs)

    def ticket_notify(self, action, values):
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

        for k, v in values.get('attrib', {}).items():
            text += u' * ' + k.title() + u': {}\n'.format(v)

        if (('changes' in values) and (len(values.get('changes', {})) > 0)):
            text += u'Changes (by {})\n'.format(values['author'])
            for k, v in values.get('changes', {}).items():
                text += u' * ' + k.title() + u': '
                text += u'{} ⇒ {}\n'.format(v[0], v[1]) if v[0] else u'{}\n'.format(v[1])
            add_author = True

        if 'description' in values:
            description = values['description']
            if len(description) > 500:
                truncated = description[498:]
                mensions = re.findall(r'[ \t]@[0-9a-zA-Z]+', truncated)
                description = description[:497] + ' ... ' + ' '.join(mensions)
            description = re.sub(r'({{{(#![a-z]+)*|}}})', '', description)
            text += u'<<Description>>\n' + description + u'\n'

        if 'comment' in values:
            comment = values['comment']
            if len(comment) > 500:
                truncated = comment[498:]
                mensions = re.findall(r'[ \t]@[0-9a-zA-Z]+', truncated)
                comment = comment[:497] + ' ... ' + ' '.join(mensions)
            comment = re.sub(r'({{{(#![a-z]+)*|}}})', '', comment)
            text += u'<<Comment'
            if not add_author:
                text += u' by {}'.format(values['author'])
            text += u'>>\n' + comment + u'\n'

        text += u'Ticket URL: {url}'.format(**values)

        #room = self.detect_room(values) or self.ticket_room
        room = self.ticket_room

        try:
            requests.post(self.webapi + '/' + room + '/messages', data={'text': text}, auth=(self.token, 'dummy'))
        except requests.exceptions.RequestException:
            return False
        return True

    def detect_room(self, values):
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
        values = prepare_ticket_values(ticket)
        values['author'] = values['reporter']
        fields = self.ticket_fields.split(',')
        attrib = {}

        for field in fields:
            if ticket[field] != '':
                attrib[field] = ticket[field]

        values['attrib'] = attrib

        self.ticket_notify('new', values)

    def ticket_changed(self, ticket, comment, author, old_values):
        if str(ticket.id) in self.ignore_tickets:
            return
        values = prepare_ticket_values(ticket)

        if values['changetime']:
            cnum = ticket.get_comment_number(values['changetime'])
            if cnum is not None:
                values['url'] += '#comment:{}'.format(cnum)

        if comment:
            # Ignore timesheet entries
            if comment in ['Timesheet2Track', 'hamster sum added']:
                return
            values['comment'] = comment
        values['author'] = author or 'unknown'
        if 'status' in old_values:
            if ticket.values.get('status') != old_values['status']:
                values['new_status'] = ticket.values['status']
                if 'resolution' in old_values:
                    values['new_status'] += ' [{}]'.format(ticket['resolution'])
                    del old_values['resolution']  # prevent this from appearing in changes

        if 'description' not in old_values.keys():
            del values['description']

        fields = self.ticket_fields.split(',')
        changes = {}

        for field in fields:
            if field in old_values:
                changes[field] = (old_values[field], ticket[field])

        values['changes'] = changes

        self.ticket_notify('edit', values)

    def ticket_deleted(self, ticket):
        pass

    def ticket_comment_modified(self, ticket, cdate, author, comment, old_comment):
        values = prepare_ticket_values(ticket)
        values['author'] = author or 'unknown'
        cnum = ticket.get_comment_number(cdate)
        if cnum is not None:
            values['url'] += '#comment:{}'.format(cnum)

        values['comment'] = comment
        del values['description']
        new_summary = comment
        old_summary = old_comment
        if len(new_summary) > 10:
            new_summary = new_summary[:10] + '...'
        if len(old_summary) > 10:
            old_summary = old_summary[:10] + '...'
        changes = {}
        changes['comment'] = (old_summary, new_summary)

        values['changes'] = changes

        self.ticket_notify('edit', values)

    def prepare_wiki_values(self, page):
        values = {}
        values['name'] = page.name
        values['url'] = self.env.abs_href.wiki(page.name)
        return values

    def wiki_notify(self, action, values):
        text = ''
        add_author = ('comment' not in values)
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

        room = self.wiki_room

        try:
            requests.post(self.webapi + '/' + room + '/messages', data={'text': text}, auth=(self.token, 'dummy'))
        except requests.exceptions.RequestException:
            return False
        return True

    def wiki_page_added(self, page):
        version, time, author, comment, ipnr = page.get_history().next()
        values = self.prepare_wiki_values(page)
        values['author'] = author
        if (len(comment) > 0):
            values['comment'] = comment

        self.wiki_notify('new', values)

    def wiki_page_changed(self, page, version, time, comment, author, ipnr):
        values = self.prepare_wiki_values(page)
        values['author'] = author
        if (len(comment) > 0):
            values['comment'] = comment

        changes = {}
        changes['version'] = version
        changes['time'] = time
        self.wiki_notify('edit', values)

    def wiki_page_deleted(self, page):
        pass

    def wiki_page_version_deleted(self, page):
        pass

    def wiki_page_renamed(self, page, old_name):
        pass

    def blog_notify(self, action, values):
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

        room = self.blog_room

        try:
            requests.post(self.webapi + '/' + room + '/messages', data={'text': text}, auth=(self.token, 'dummy'))
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
        values['url'] = 'http://10.75.13.152/trac/blog/{}'.format(postname)
        values['title'] = bp.title
        values['name'] = bp.name
        values['author'] = bp.version_author
        values['body'] = bp.body
        if len(bp.version_comment) > 0:
            values['comment'] = bp.version_comment

        self.blog_notify(action, values)

    def blog_post_deleted(self, postname, version, fields):
        pass

    def blog_comment_added(self, postname, number):
        bp = BlogPost(self.env, postname, 0)
        bc = BlogComment(self.env, postname, number)
        values = {}
        values['url'] = 'http://10.75.13.152/trac/blog/{}'.format(postname)
        values['title'] = bp.title
        values['name'] = bp.name
        values['author'] = bc.author
        values['comment'] = bc.comment
        self.blog_notify('edit', values)

    def blog_comment_deleted(self, postname, number, fields):
        pass