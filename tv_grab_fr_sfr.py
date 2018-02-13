#!/usr/bin/python3
# -*- coding: utf-8 -*-

# Copyright 2017-2018 Mohamed El Morabity
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU
# General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
# even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with this program. If not,
# see <http://www.gnu.org/licenses/>.


"""tv_grab_fr_sfr.py - Grab French television listings from SFR STB EPG sources in XMLTV format."""

import argparse
import datetime
import gzip
import logging
import os
import re
import sys
import urllib
import urllib.parse
from urllib.request import Request

import lxml.etree
from lxml.etree import Element, ElementTree, SubElement
import pytz.reference


class SFRXMLTVGrabber:
    """Implements grabbing and processing functionalities required to generate XMLTV data from SFR
    STB EPG sources.
    """

    _API_URL = 'http://data.stb.neuf.fr/epg/data/xmltv'
    _API_USER_AGENT = 'Mozilla/4.0 (compatible; MSIE 5.01; Windows 98; Linux 2.4.32-tango2) ' \
                      '[Netgem; 4.7.13; i-Player; netbox; neuftelecom]; neuftelecom;'
    _XMLTV_DATETIME_FORMAT = '%Y%m%d%H%M%S %z'

    _SFR_TIMEZONE = pytz.timezone('Europe/Paris')
    _SFR_START_TIME = datetime.time(5, 0)

    _MAX_DAYS = 14

    _PROGRAM_URL = 'http://tv.sfr.fr/prog'

    _ETSI_PROGRAM_CATEGORIES = {
        'Autre': '',
        'Cinéma': 'Movie / Drama',
        'Documentaire': 'Documentary',
        'Jeunesse': "Children's / Youth programmes",
        'Magazine': 'Magazines / Reports / Documentary',
        'Série TV': 'Movie / Drama',
        'Spectacle': 'Performing arts',
        'Sport': 'Sports',
        'Téléfilm': 'Movie / Drama'
    }

    def __init__(self, generator=None, generator_url=None, logger=None):
        self._logger = logger or logging.getLogger(__name__)

        self._channels = self._retrieve_available_channels()
        self._generator = generator
        self._generator_url = generator_url

    def _get_programs(self, date=datetime.date.today()):
        """Get SFR programs for a given day as a XML Element object."""

        self._logger.debug('Getting SFR programs on %s', date)

        url = '{}/{:%Y%m%d}.gz'.format(self._API_URL, date)

        self._logger.debug('Retrieveing URL %s', url)
        request = Request(url, headers={'User-agent': self._API_USER_AGENT})
        with urllib.request.urlopen(request) as response:
            data = gzip.decompress(response.read())
            return lxml.etree.fromstring(data)

    @staticmethod
    def _sfr_to_xmltv_id(sfr_id):
        """Convert a SFR channel ID to a valid XMLTV channel ID."""

        xmltv_id = sfr_id.replace('_', '-').replace('+', 'PLUS')
        xmltv_id += '.tv.sfr.fr'

        return xmltv_id

    def _retrieve_available_channels(self):
        """Retrieve all available channels, identified by their XMLTV ID, from SFR."""

        self._logger.debug('Getting available channels')
        # Extract channels from today's program
        program_xml = self._get_programs()

        channels = {}
        for channel in program_xml.iter(tag='channel'):
            sfr_id = channel.get('id')
            display_name = channel.findtext('display-name')
            if sfr_id is not None and display_name is not None:
                xmltv_id = self._sfr_to_xmltv_id(sfr_id)
                channels[xmltv_id] = {'sfr_id': sfr_id, 'display_name': display_name}

        return channels

    def get_available_channels(self):
        """Return the list of all available channels from SFR, as a dictionary."""

        return self._channels

    def _etsi_category(self, category):
        """Translate SFR program category to ETSI EN 300 468 category."""

        etsi_category = self._ETSI_PROGRAM_CATEGORIES.get(category)
        if etsi_category is None:
            self._logger.warning('SFR category %s has no defined ETSI equivalent', category)

        return etsi_category

    def _parse_channel_xmltv(self, xmltv_id):
        """Convert a channel identified by its XMLTV ID to a XMLTV Element object."""

        display_name = self._channels[xmltv_id]['display_name']

        channel_xml = Element('channel', id=xmltv_id)
        display_name_xml = SubElement(channel_xml, 'display-name')
        display_name_xml.text = display_name

        return channel_xml

    def _parse_program_xmltv(self, sfr_xml):
        """Convert a SFR program XML Element to a "real" XMLTV Element object."""

        program_xml = Element(
            'programme',
            channel=self._sfr_to_xmltv_id(sfr_xml.get('channel')),
            start=sfr_xml.get('start'),
            stop=sfr_xml.get('stop')
        )

        # Title
        title = sfr_xml.findtext('title').strip()
        title_xml = SubElement(program_xml, 'title')
        title_xml.text = title

        # Sub-title
        sub_title = sfr_xml.findtext('sub-title', '').strip()
        if sub_title != '':
            sub_title_xml = SubElement(program_xml, 'sub-title')
            sub_title_xml.text = sub_title

        # Desc
        desc = sfr_xml.findtext('desc', '').strip()
        if desc != '':
            desc_xml = SubElement(program_xml, 'desc', lang='fr')
            desc_xml.text = desc

        # Categories
        category = sfr_xml.findtext('category', '').strip()
        if category != '':
            etsi_category = self._etsi_category(category)
            if etsi_category is not None and etsi_category != '':
                category_xml = SubElement(program_xml, 'category')
                category_xml.text = etsi_category
            # Keep original category in French
            if category != '':
                category_xml = SubElement(program_xml, 'category', lang='fr')
                category_xml.text = category
            # Add SFR meta-categories as categories
            meta_category = sfr_xml.findtext('metacategory', '').strip()
            if meta_category != '' and meta_category != category:
                category_xml = SubElement(program_xml, 'category', lang='fr')
                category_xml.text = meta_category

        # Program URL
        program_id = sfr_xml.get('id', '').strip()
        if program_id != '':
            url_xml = SubElement(program_xml, 'url')
            url_xml.text = '{}/{}-{}'.format(self._PROGRAM_URL, title, program_id)

        # Star rating
        star_rating_xml = sfr_xml.find('star-rating')
        if star_rating_xml is not None:
            star_rating = star_rating_xml.findtext('value', '').strip()
            if star_rating != '':
                star_rating_xml = SubElement(program_xml, 'star-rating', system='SFR')
                star_rating_value_xml = SubElement(star_rating_xml, 'value')
                star_rating_value_xml.text = star_rating

        return program_xml

    def _get_xmltv_data(self, xmltv_ids, days=1, offset=0):
        """Get SFR program data in XMLTV format as XML ElementTree object."""

        if days + offset > self._MAX_DAYS:
            self._logger.warning('Grabber can only fetch programs up to %i days in the future.',
                                 self._MAX_DAYS)
            days = min(self._MAX_DAYS - offset, self._MAX_DAYS)

        root_xml = Element('tv', attrib={'source-info-name': 'SFR',
                                         'source-info-url': 'http://tv.sfr.fr/epg',
                                         'source-data-url': self._API_URL})
        if self._generator is not None:
            root_xml.set('generator-info-name', self._generator)
        if self._generator_url is not None:
            root_xml.set('generator-info-url', self._generator_url)

        start = datetime.datetime.combine(datetime.date.today(), datetime.time(0),
                                          tzinfo=pytz.reference.LocalTimezone())
        start = start + datetime.timedelta(days=offset)
        stop = start + datetime.timedelta(days=days)

        # Dates to fetch from the SFR API
        sfr_fetch_dates = [start.date() + datetime.timedelta(days=d) for d in range(days)]
        # SFR data for a given day contain programs starting between 5:00 AM and 4:59 AM the
        # next day (Paris time)
        if start < self._SFR_TIMEZONE.localize(datetime.datetime.combine(start,
                                                                         self._SFR_START_TIME)):
            sfr_fetch_dates.insert(0, start.date() - datetime.timedelta(days=1))
        elif stop > self._SFR_TIMEZONE.localize(datetime.datetime.combine(stop,
                                                                          self._SFR_START_TIME)):
            sfr_fetch_dates.append(stop.date())

        programs_xml = []
        valid_xmltv_ids = set()
        # SFR data contain programs starting between 5:00 AM and 4:59 AM the next day. Get
        # programs before the first selected day to get all programs for this day.
        for date in sfr_fetch_dates:
            for sfr_program_xml in self._get_programs(date).iter(tag='programme'):
                # Only keep programs for selected channels
                sfr_id = sfr_program_xml.get('channel')
                if self._sfr_to_xmltv_id(sfr_id) not in xmltv_ids:
                    continue

                program_xml = self._parse_program_xmltv(sfr_program_xml)
                program_start = datetime.datetime.strptime(program_xml.get('start'),
                                                           self._XMLTV_DATETIME_FORMAT)
                program_stop = datetime.datetime.strptime(program_xml.get('stop'),
                                                          self._XMLTV_DATETIME_FORMAT)

                # Skip programs outside the fetch period
                if program_stop < start or program_start >= stop:
                    continue

                program_xml = self._parse_program_xmltv(sfr_program_xml)

                xmltv_id = program_xml.get('channel')
                valid_xmltv_ids.add(xmltv_id)

                programs_xml.append(program_xml)

        # Keep only channels which have programs actually in the XMLTV result
        for xmltv_id in valid_xmltv_ids:
            root_xml.append(self._parse_channel_xmltv(xmltv_id))

        root_xml.extend(programs_xml)

        return ElementTree(root_xml)

    def write_xmltv(self, xmltv_ids, output_file, days=1, offset=0):
        """Grab SFR programs in XMLTV format and write them to file."""

        self._logger.debug('Writing XMLTV program to file %s', output_file)

        xmltv_data = self._get_xmltv_data(xmltv_ids, days, offset)
        xmltv_data.write(output_file, encoding='UTF-8', xml_declaration=True, pretty_print=True)


_PROGRAM = 'tv_grab_fr_sfr'
__version__ = '1.0'
__url__ = 'https://github.com/melmorabity/tv_grab_fr_sfr'

_DESCRIPTION = 'France (SFR)'
_CAPABILITIES = ['baseline', 'manualconfig']

_DEFAULT_DAYS = 1
_DEFAULT_OFFSET = 0

_DEFAULT_CONFIG_FILE = os.path.join(os.environ['HOME'], '.xmltv', _PROGRAM + '.conf')

_DEFAULT_OUTPUT = '/dev/stdout'


def _print_description():
    """Print the description for the grabber."""

    print(_DESCRIPTION)


def _print_version():
    """Print the grabber version."""

    print('This is {} version {}'.format(_PROGRAM, __version__))


def _print_capabilities():
    """Print the capabilities for the grabber."""

    print('\n'.join(_CAPABILITIES))


def _parse_cli_args():
    """Command line argument processing."""

    parser = argparse.ArgumentParser(
        description='get French television listings from SFR STB EPG sources '
                    'in XMLTV format'
    )
    parser.add_argument('--description', action='store_true',
                        help='print the description for this grabber')
    parser.add_argument('--version', action='store_true', help='show the version of this grabber')
    parser.add_argument('--capabilities', action='store_true',
                        help='show the capabilities this grabber supports')
    parser.add_argument(
        '--configure', action='store_true',
        help='generate the configuration file by asking the users which channels to grab'
    )
    parser.add_argument('--days', type=int, default=_DEFAULT_DAYS,
                        help='grab DAYS days of TV data (default: %(default)s)')
    parser.add_argument(
        '--offset', type=int, default=_DEFAULT_OFFSET,
        help='grab TV data starting at OFFSET days in the future (default: %(default)s)'
    )
    parser.add_argument('--output', default=_DEFAULT_OUTPUT,
                        help='write the XML data to OUTPUT instead of the standard output')
    parser.add_argument(
        '--config-file', default=_DEFAULT_CONFIG_FILE,
        help='file name to write/load the configuration to/from (default: %(default)s)'
    )

    log_level_group = parser.add_mutually_exclusive_group()
    log_level_group.add_argument('--quiet', action='store_true',
                                 help='only print error-messages on STDERR')
    log_level_group.add_argument(
        '--debug', action='store_true',
        help='provide more information on progress to stderr to help in debugging'
    )

    return parser.parse_args()


def _read_configuration(config_file=_DEFAULT_CONFIG_FILE):
    """Load channel XMLTV IDs from the configuration file."""

    xmltv_ids = []
    with open(config_file, 'r') as config:
        for line in config:
            match = re.search(r'^\s*channel\s*=\s*(.+)\s*$', line)
            if match is not None:
                xmltv_ids.append(match.group(1))

    return xmltv_ids


def _write_configuration(xmltv_ids, config_file=_DEFAULT_CONFIG_FILE):
    """Write specified channels to the specified configuration file."""

    config_dir = os.path.dirname(os.path.abspath(config_file))
    if not os.path.exists(config_dir):
        os.mkdir(config_dir)

    with open(config_file, 'w') as config:
        for xmltv_id in xmltv_ids:
            print('channel={}'.format(xmltv_id), file=config)


def _configure(available_channels, config_file=_DEFAULT_CONFIG_FILE):
    """Prompt channels to configure and write them into the configuration file."""

    xmltv_ids = []
    answers = ['yes', 'no', 'all', 'none']
    select_all = False
    select_none = False
    print('Select the channels that you want to receive data for.',
          file=sys.stderr)
    for xmltv_id in available_channels:
        display_name = available_channels[xmltv_id]['display_name']
        if not select_all and not select_none:
            while True:
                prompt = '{} [{} (default=no)] '.format(display_name, ','.join(answers))
                answer = input(prompt).strip()
                if answer in answers or answer == '':
                    break
                print('invalid response, please choose one of {}'.format(','.join(answers)),
                      file=sys.stderr)
            select_all = answer == 'all'
            select_none = answer == 'none'
        if select_all or answer == 'yes':
            xmltv_ids.append(xmltv_id)
        if select_all:
            print('{} yes'.format(display_name), file=sys.stderr)
        elif select_none:
            print('{} no'.format(display_name), file=sys.stderr)

    _write_configuration(xmltv_ids, config_file)


def _main():
    """Main execution path."""

    logger = logging.getLogger(__name__)
    logger.addHandler(logging.StreamHandler())

    args = _parse_cli_args()

    if args.version:
        _print_version()
        sys.exit()

    if args.description:
        _print_description()
        sys.exit()

    if args.capabilities:
        _print_capabilities()
        sys.exit()

    if args.debug:
        log_level = logging.DEBUG
    elif args.quiet:
        log_level = logging.ERROR
    else:
        log_level = logging.INFO

    logger.setLevel(log_level)

    sfr = SFRXMLTVGrabber(generator=_PROGRAM, generator_url=__url__, logger=logger)
    available_channels = sfr.get_available_channels()

    logger.info('Using configuration file %s', args.config_file)

    if args.configure:
        _configure(available_channels, args.config_file)
        sys.exit()

    if not os.path.isfile(args.config_file):
        logger.error('You need to configure the grabber by running it with --configure')
        sys.exit(1)

    xmltv_ids = _read_configuration(args.config_file)
    if not xmltv_ids:
        logger.error('Configuration file %s is empty, delete and run with --configure',
                     args.config_file)

    sfr.write_xmltv(xmltv_ids, args.output, days=args.days, offset=args.offset)

if __name__ == '__main__':
    _main()
