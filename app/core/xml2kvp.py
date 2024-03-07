# xml2kvp

import ast
from collections import OrderedDict
from copy import deepcopy
import dashtable
import hashlib
import json
from lxml import etree
import logging
import re
import time
import xmltodict

# init logger
logger = logging.getLogger(__name__)

# sibling hash regex
sibling_hash_regex = re.compile(r'(.+?)\(([0-9a-zA-Z]+)\)|(.+)')



class XML2kvp():
    '''
    Class to handle the parsing of XML into Key/Value Pairs

            - utilizes xmltodict (https://github.com/martinblech/xmltodict)
            - static methods are designed to be called without user instantiating
            instance of XML2kvp
    '''

    # test xml
    test_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<root xmlns:internet="http://internet.com">
	<foo>
		<bar>88888888888</bar>
	</foo>
	<foo>
		<bar>42</bar>
		<baz>109</baz>
	</foo>
	<foo>
		<bar>42</bar>
		<baz>109</baz>
	</foo>
	<foo>
		<bar>9393943</bar>
		<baz>3489234893</baz>
	</foo>
	<alligator>
		<tail>
			<quality>medium</quality>
		</tail>
	</alligator>
	<alligator>
		<tail>
			<quality>long</quality>
		</tail>
		<legs>
			<quality>short</quality>
		</legs>
	</alligator>
	<alligator>
		<tail>
			<quality>very long</quality>
		</tail>
		<legs>
			<quality>very short</quality>
		</legs>
	</alligator>
	<tronic type='tonguetwister'>Sally sells seashells by the seashore.</tronic>
	<tronic type='tonguetwister'>Red leather, yellow leather.</tronic>
	<tronic>You may disregard</tronic>
	<goober scrog='true' tonk='false'>
		<people>
			<plunder>Willy Wonka</plunder>
		</people>
		<cities>
			<plunder>City of Atlantis</plunder>
		</cities>
	</goober>
	<nested_attribs type='first'>
		<another type='second'>paydirt</another>
	</nested_attribs>
	<nested>
		<empty></empty>
	</nested>
	<internet:url url='http://example.com'>see my url</internet:url>
	<beat type="4/4">four on the floor</beat>
	<beat type="3/4">waltz</beat>
	<ordering>
		<duck>100</duck>
		<duck>101</duck>
		<goose>102</goose>
		<it>run!</it>
	</ordering>
	<ordering>
		<duck>200</duck>
		<duck>201</duck>
		<goose>202</goose>
		<it>run!</it>
	</ordering>
	<pattern pattern_type="striped">
		<application>streets</application>
		<dizzying>true</dizzying>
	</pattern>
</root>
	'''

    # custom exception for delimiter collision

    class DelimiterCollision(Exception):
        pass

    # schema for validation
    schema = {
        "$id": "xml2kvp_config_schema",
        "title": "XML2kvp configuration options schema",
        "type": "object",
        "properties": {
                "add_literals": {
                    "description": "Key/value pairs for literals to mixin, e.g. ``foo``:``bar`` would create field ``foo`` with value ``bar`` [Default: ``{}``]",
                    "type": "object"
                },
            "capture_attribute_values": {
                    "description": "Array of attributes to capture values from and set as standalone field, e.g. if [``age``] is provided and encounters ``<foo age='42'/>``, a field ``foo_@age@`` would be created (note the additional trailing ``@`` to indicate an attribute value) with the value ``42``. [Default: ``[]``, Before: ``copy_to``, ``copy_to_regex``]",
                    "type": "array"
                    },
            "concat_values_on_all_fields": {
                    "description": "Boolean or String to join all values from multivalued field on [Default: ``false``]",
                    "type": ["boolean", "string"]
                    },
            "concat_values_on_fields": {
                    "description": "Key/value pairs for fields to concat on provided value, e.g. ``foo_bar``:``-`` if encountering ``foo_bar``:[``goober``,``tronic``] would concatenate to ``foo_bar``:``goober-tronic`` [Default: ``{}``]",
                    "type": "object"
                    },
            "copy_to": {
                    "description": "Key/value pairs to copy one field to another, optionally removing original field, e.g. ``foo``:``bar`` would create field ``bar`` and copy all values when encountered for ``foo`` to ``bar``, removing ``foo``.  However, the original field can be retained by setting ``remove_copied_key`` to ``true``.  Note: Can also be used to remove fields by setting the target field as false, e.g. 'foo':``false``, would remove field ``foo``. [Default: ``{}``]",
                    "type": "object"
                    },
            "copy_to_regex": {
                    "description": "Key/value pairs to copy one field to another, optionally removing original field, based on regex match of field, e.g. ``.*foo``:``bar`` would copy create field ``bar`` and copy all values fields ``goober_foo`` and ``tronic_foo`` to ``bar``.  Note: Can also be used to remove fields by setting the target field as false, e.g. ``.*bar``:``false``, would remove fields matching regex ``.*bar`` [Default: ``{}``]",
                    "type": "object"
                    },
            "copy_value_to_regex": {
                    "description": "Key/value pairs that match values based on regex and copy to new field if matching, e.g. ``http.*``:``websites`` would create new field ``websites`` and copy ``http://exampl.com`` and ``https://example.org`` to new field ``websites`` [Default: ``{}``]",
                    "type": "object"
                    },
            "error_on_delims_collision": {
                    "description": "Boolean to raise ``DelimiterCollision`` exception if delimiter strings from either ``node_delim`` or ``ns_prefix_delim`` collide with field name or field value (``false`` by default for permissive mapping, but can be helpful if collisions are essential to detect) [Default: ``false``]",
                    "type": "boolean"
                    },
            "exclude_attributes": {
                    "description": "Array of attributes to skip when creating field names, e.g. [``baz``] when encountering XML ``<foo><bar baz='42' goober='1000'>tronic</baz></foo>`` would create field ``foo_bar_@goober=1000``, skipping attribute ``baz`` [Default: ``[]``]",
                    "type": "array"
                    },
            "exclude_elements": {
                    "description": "Array of elements to skip when creating field names, e.g. [``baz``] when encountering field ``<foo><baz><bar>tronic</bar></baz></foo>`` would create field ``foo_bar``, skipping element ``baz`` [Default: ``[]``, After: ``include_all_attributes``, ``include_attributes``]",
                    "type": "array"
                    },
            "include_attributes": {
                    "description": "Array of attributes to include when creating field names, despite setting of ``include_all_attributes``, e.g. [``baz``] when encountering XML ``<foo><bar baz='42' goober='1000'>tronic</baz></foo>`` would create field ``foo_bar_@baz=42`` [Default: ``[]``, Before: ``exclude_attributes``, After: ``include_all_attributes``]",
                    "type": "array"
                    },
            "include_all_attributes": {
                    "description": "Boolean to consider and include all attributes when creating field names, e.g. if ``false``, XML elements ``<foo><bar baz='42' goober='1000'>tronic</baz></foo>`` would result in field name ``foo_bar`` without attributes included.  Note: the use of all attributes for creating field names has the the potential to balloon rapidly, potentially encountering ElasticSearch field limit for an index, therefore ``false`` by default.  [Default: ``false``, Before: ``include_attributes``, ``exclude_attributes``]",
                    "type": "boolean"
                    },
            "include_sibling_id": {
                    "description": "Boolean to append matching identifiers, as part of key name, to sibling nodes, e.g. ``foo_bar`` and `foo_baz`` might become ``foo(abc123)_bar(def456)`` and ``foo(abc123)_baz(def456)``",
                    "type": "boolean"
                    },
            "include_meta": {
                    "description": "Boolean to include ``xml2kvp_meta`` field with output that contains all these configurations [Default: ``false``]",
                    "type": "boolean"
                    },
            "node_delim": {
                    "description": "String to use as delimiter between XML elements and attributes when creating field name, e.g. ``___`` will convert XML ``<foo><bar>tronic</bar></foo>`` to field name ``foo___bar`` [Default: ``_``]",
                    "type": "string"
                    },
            "ns_prefix_delim": {
                    "description": "String to use as delimiter between XML namespace prefixes and elements, e.g. ``|`` for the XML ``<ns:foo><ns:bar>tronic</ns:bar></ns:foo>`` will create field name ``ns|foo_ns:bar``.  Note: a ``|`` pipe character is used to avoid using a colon in ElasticSearch fields, which can be problematic. [Default: ``|``]",
                    "type": "string"
                    },
            "remove_copied_key": {
                    "description": "Boolean to determine if originating field will be removed from output if that field is copied to another field [Default: ``true``]",
                    "type": "boolean"
                    },
            "remove_copied_value": {
                    "description": "Boolean to determine if value will be removed from originating field if that value is copied to another field [Default: ``false``]",
                    "type": "boolean"
                    },
            "remove_ns_prefix": {
                    "description": "Boolean to determine if XML namespace prefixes are removed from field names, e.g. if ``false``, the XML ``<ns:foo><ns:bar>tronic</ns:bar></ns:foo>`` will result in field name ``foo_bar`` without ``ns`` prefix [Default: ``true``]",
                    "type": "boolean"
                    },
            "self_describing": {
                    "description": "Boolean to include machine parsable information about delimeters used (reading right-to-left, delimeter and its length in characters) as suffix to field name, e.g. if ``true``, and ``node_delim`` is ``___`` and ``ns_prefix_delim`` is ``|``, suffix will be ``___3|1``.  Can be useful to reverse engineer field name when not re-parsed by XML2kvp. [Default: ``false``]",
                    "type": "boolean"
                    },
            "split_values_on_all_fields": {
                    "description": "If present, string to use for splitting values from all fields, e.g. `` `` will convert single value ``a foo bar please`` into the array of values [``a``,``foo``,``bar``,``please``] for that field [Default: ``false``]",
                    "type": ["boolean", "string"]
                    },
            "split_values_on_fields": {
                    "description": "Key/value pairs of field names to split, and the string to split on, e.g. ``foo_bar``:``,`` will split all values on field ``foo_bar`` on comma ``,`` [Default: ``{}``]",
                    "type": "object"
                    },
            "skip_attribute_ns_declarations": {
                    "description": "Boolean to remove namespace declarations as considered attributes when creating field names [Default: ``true``]",
                    "type": "boolean"
                    },
            "skip_repeating_values": {
                    "description": "Boolean to determine if a field is multivalued, if those values are allowed to repeat, e.g. if set to ``false``, XML ``<foo><bar>42</bar><bar>42</bar></foo>`` would map to ``foo_bar``:``42``, removing the repeating instance of that value. [Default: ``true``]",
                    "type": "boolean"
                    },
            "skip_root": {
                    "description": "Boolean to determine if the XML root element will be included in output field names [Default: ``false``]",
                    "type": "boolean"
                    },
            "repeating_element_suffix_count": {
                    "description": "Boolean to suffix field name with incrementing integer (after first instance, which does not receieve a suffix), e.g. XML ``<foo><bar>42</bar><bar>109</bar></foo>`` would map to ``foo_bar``:``42``, ``foo_bar_#1``:``109``  [Default: ``false``, Overrides: ``skip_repeating_values``]",
                    "type": "boolean"
                    },
            "add_element_root": {
                        "description": "xml tag with which to wrap each element as a root",
                        "type": "string"
                    }
        }
    }

    def __init__(self, **kwargs):
        '''
        Args
                kwargs (dict): Accepts named args from static methods
        '''

        # defaults, overwritten by methods
        self.add_literals = {}
        self.as_tuples = True
        self.capture_attribute_values = []
        self.concat_values_on_all_fields = False
        self.concat_values_on_fields = {}
        self.copy_to = {}
        self.copy_to_regex = {}
        self.copy_value_to_regex = {}
        self.error_on_delims_collision = False
        self.exclude_attributes = []
        self.exclude_elements = []
        self.include_attributes = []
        self.include_all_attributes = False
        self.include_meta = False
        self.include_sibling_id = False
        self.include_xml_prop = False
        self.multivalue_delim = '|'
        self.node_delim = '_'
        self.ns_prefix_delim = '|'
        self.remove_copied_key = True
        self.remove_copied_value = False
        self.remove_ns_prefix = True
        self.self_describing = False
        self.split_values_on_all_fields = False
        self.split_values_on_fields = {}
        self.skip_attribute_ns_declarations = True
        self.skip_repeating_values = True
        self.skip_root = False
        self.repeating_element_suffix_count = False

        # list of properties that are allowed to be overwritten with None
        arg_none_allowed = []

        # overwrite with attributes from static methods
        for k, v in kwargs.items():
            if v is not None or k in arg_none_allowed:
                setattr(self, k, v)

        # set non-overwritable class attributes
        self.kvp_dict = {}
        self.k_xpath_dict = {}

        # sibling hash counter
        self.sibling_hash_counter = {}

    @property
    def schema_json(self):
        return json.dumps(self.schema)

    @property
    def config_json(self):

        config_dict = {k: v for k, v in self.__dict__.items() if k in [
            'add_literals',
            'capture_attribute_values',
            'concat_values_on_all_fields',
            'concat_values_on_fields',
            'copy_to',
            'copy_to_regex',
            'copy_value_to_regex',
            'error_on_delims_collision',
            'exclude_attributes',
            'exclude_elements',
            'include_attributes',
            'include_all_attributes',
            'include_sibling_id',
            'multivalue_delim',
            'node_delim',
            'ns_prefix_delim',
            'remove_copied_key',
            'remove_copied_value',
            'remove_ns_prefix',
            'self_describing',
            'split_values_on_all_fields',
            'split_values_on_fields',
            'skip_attribute_ns_declarations',
            'skip_repeating_values',
            'skip_root',
            'repeating_element_suffix_count',
        ]}

        return json.dumps(config_dict, indent=2, sort_keys=True)

    def _xml_dict_parser(self, in_k, in_v, hops=[]):

        # handle Dictionary
        if type(in_v) == OrderedDict:

            # set sibling hash
            if in_k != None:
                hash_val = in_k
            else:
                hash_val = hash(frozenset(in_v.keys()))
            if hash_val not in self.sibling_hash_counter.keys():
                self.sibling_hash_counter[hash_val] = 1
            else:
                self.sibling_hash_counter[hash_val] += 1
            sibling_hash = '%s%s' % (hashlib.md5(str(hash_val).encode('utf-8')).hexdigest()[:4],
                                     str(self.sibling_hash_counter[hash_val]).zfill(2))

            # handle all attributes for node first
            for k, v in in_v.items():
                if k.startswith('@'):

                    # handle capture_attribute_values
                    if len(self.capture_attribute_values) > 0 and k.lstrip('@') in self.capture_attribute_values:
                        temp_hops = hops.copy()
                        temp_hops.append("%s@" % k)
                        self._process_kvp(temp_hops, v)

                    # format and append if including
                    if self.include_all_attributes or (
                            len(self.include_attributes) > 0 and k.lstrip('@') in self.include_attributes):
                        hops = self._format_and_append_hop(hops, 'attribute', k, v)

            # set hop length that will be returned to
            hop_len = len(hops)

            # loop through remaining element and/or text nodes
            for k, v in in_v.items():

                # add key to hops
                if k == '#text':
                    self._process_kvp(hops, v)

                else:

                    # recurse with non attribute nodes (element or text)
                    if not k.startswith('@'):
                        hops = self._format_and_append_hop(hops, 'element', k, None, sibling_hash=sibling_hash)

                        # recurse
                        self._xml_dict_parser(k, v, hops=hops)

                        # reset hops
                        hops = hops[:hop_len]

        # handle list
        elif type(in_v) == list:

            hop_len = len(hops)
            for d in in_v:
                # recurse
                self._xml_dict_parser(None, d, hops=hops)

                # drop hops back one
                hops = hops[:hop_len]

        # handle str or int, a value
        elif type(in_v) in [str, int]:

            if in_k != '#text':
                self._process_kvp(hops, in_v)

    def _format_and_append_hop(self, hops, hop_type, k, v, sibling_hash=None):

        # handle elements
        if hop_type == 'element':

            # if erroring on collision
            if self.error_on_delims_collision:
                self._check_delims_collision(k)

            # if skipping elements
            if len(self.exclude_elements) > 0:
                if k in self.exclude_elements:
                    return hops

            # apply namespace delimiter
            if not self.remove_ns_prefix:
                hop = k.replace(':', self.ns_prefix_delim)
            else:
                if ':' in k:
                    hop = k.split(':')[1]
                else:
                    hop = k

            # if include_sibling_id, append
            if self.include_sibling_id:
                # if not first entry, but repeating
                if int(sibling_hash[-2:]) >= 1:
                    hop = '%s(%s)' % (hop, sibling_hash)

        # handle elements
        if hop_type == 'attribute':

            # skip attribute namespace declarations
            if self.skip_attribute_ns_declarations:
                if k.startswith(('@xmlns', '@xsi')):
                    return hops

            # if excluded attributes
            if len(self.exclude_attributes) > 0:
                if k.lstrip('@') in self.exclude_attributes:
                    return hops

            # if erroring on collision
            if self.error_on_delims_collision:
                self._check_delims_collision(k)
                self._check_delims_collision(v)

            # apply namespace delimiter
            k = k.replace(':', self.ns_prefix_delim)

            # combine
            hop = '%s=%s' % (k, v)

        # append and return
        hops.append(hop)
        return hops

    def _check_delims_collision(self, value):

        if any(delim in value for delim in [self.node_delim, self.ns_prefix_delim]):
            raise self.DelimiterCollision('collision for key value: "%s", collides with a configured delimiter: %s' %
                                          (value,
                                           {'node_delim': self.node_delim, 'ns_prefix_delim': self.ns_prefix_delim}))

    def _process_kvp(self, hops, value):
        '''
        method to add key/value pairs to saved dictionary,
        appending new values to pre-existing keys
        '''

        # sanitize value

        value = self._sanitize_value(value)

        # join on node delimiter
        k = self.node_delim.join(hops)

        # add delims suffix
        if self.self_describing:
            k = "%(k)s%(node_delim)s%(node_delim_len)s%(ns_prefix_delim)s%(ns_prefix_delim_len)s" % {
                'k': k,
                'node_delim': self.node_delim,
                'node_delim_len': len(self.node_delim),
                'ns_prefix_delim': self.ns_prefix_delim,
                'ns_prefix_delim_len': len(self.ns_prefix_delim)
            }

        # init k_list
        k_list = [k]

        # handle copy_to mixins
        if len(self.copy_to) > 0:
            slen = len(k_list)
            k_list.extend([cv for ck, cv in self.copy_to.items() if ck == k])
            if self.remove_copied_key:
                if slen != len(k_list) and k in k_list:
                    k_list.remove(k)

        # handle copy_to_regex mixins
        if len(self.copy_to_regex) > 0:

            # key list prior to copies
            slen = len(k_list)

            # loop through copy_to_regex
            for rk, rv in self.copy_to_regex.items():

                # if False, check for match and remove
                if rv == False:
                    if re.match(rk, k):
                        k_list.append(False)

                # attempt sub
                else:
                    try:
                        sub = re.sub(rk, rv, k)
                        if sub != k:
                            k_list.append(sub)
                    except:
                        pass

            if self.remove_copied_key:
                if slen != len(k_list) and k in k_list:
                    k_list.remove(k)

        # handle copy_value_to_regex mixins
        if len(self.copy_value_to_regex) > 0:

            # key list prior to copies
            slen = len(k_list)

            # loop through copy_value_to_regex
            for rk, rv in self.copy_value_to_regex.items():

                # attempt sub
                try:
                    if re.match(r'%s' % rk, value):
                        k_list.append(rv)
                except:
                    pass

            if self.remove_copied_value:
                if slen != len(k_list) and k in k_list:
                    k_list.remove(k)

        # loop through keys
        for k in k_list:

            # if k is false, treat like /dev/null
            if k == False:
                pass

            # new key, new value
            elif k not in self.kvp_dict.keys():
                self.kvp_dict[k] = value

            # pre-existing, but not yet list, convert
            elif not self.repeating_element_suffix_count and k in self.kvp_dict.keys() and type(
                    self.kvp_dict[k]) != list:

                if self.skip_repeating_values and value == self.kvp_dict[k]:
                    pass
                else:
                    tval = self.kvp_dict[k]
                    self.kvp_dict[k] = [tval, value]

            # suffix key with incrementing int
            elif self.repeating_element_suffix_count and k in self.kvp_dict.keys():

                # check for other numbers
                suffix_count = 1
                while True:
                    if '%s%s#%s' % (k, self.node_delim, suffix_count) in self.kvp_dict.keys():
                        suffix_count += 1
                    else:
                        break
                self.kvp_dict['%s%s#%s' %
                              (k, self.node_delim, suffix_count)] = value

            # already list, append
            else:
                if not self.skip_repeating_values or value not in self.kvp_dict[k]:
                    self.kvp_dict[k].append(value)

    def _split_and_concat_fields(self):
        '''
        Method to group actions related to splitting and concatenating field values
        '''

        # concat values on all fields
        if self.concat_values_on_all_fields:
            for k, v in self.kvp_dict.items():
                if type(v) == list:
                    self.kvp_dict[k] = self.concat_values_on_all_fields.join(v)

        # concat values on select fields
        if not self.concat_values_on_all_fields and len(self.concat_values_on_fields) > 0:
            for k, v in self.concat_values_on_fields.items():
                if k in self.kvp_dict.keys() and type(self.kvp_dict[k]) == list:
                    self.kvp_dict[k] = v.join(self.kvp_dict[k])

        # split values on all fields
        if self.split_values_on_all_fields:
            for k, v in self.kvp_dict.items():
                if type(v) == str:
                    self.kvp_dict[k] = v.split(self.split_values_on_all_fields)

        # split values on select fields
        if not self.split_values_on_all_fields and len(self.split_values_on_fields) > 0:
            for k, v in self.split_values_on_fields.items():
                if k in self.kvp_dict.keys() and type(self.kvp_dict[k]) == str:
                    self.kvp_dict[k] = self.kvp_dict[k].split(v)

    def _parse_xml_input(self, xml_input):
        '''
        Note: self may be handler instance passsed
        '''

        # if string, save
        if type(xml_input) == str:
            if self.include_xml_prop:
                try:
                    self.xml = etree.fromstring(xml_input)
                except:
                    self.xml = etree.fromstring(xml_input.encode('utf-8'))
                self._parse_nsmap()
            return xml_input

        # if etree object, to string and save
        if type(xml_input) in [etree._Element, etree._ElementTree]:
            if self.include_xml_prop:
                self.xml = xml_input
                self._parse_nsmap()
            return etree.tostring(xml_input).decode('utf-8')

    def _parse_nsmap(self):
        '''
        Note: self may be handler instance passsed
        '''

        # get namespace map, popping None values
        _nsmap = self.xml.nsmap.copy()
        try:
            global_ns = _nsmap.pop(None)
            # TODO: global_ns on below line was 'ns0' which doesn't exist...
            _nsmap['global_ns'] = global_ns
        except:
            pass
        self.nsmap = _nsmap

    def _sanitize_value(self, value):
        '''
        Method to sanitize value before storage in ElasticSearch

        Current sanitations:
            - length: Lucene index limited to 32,766, limiting to 32,000
        '''

        # limit length
        if len(value) > 32000:
            value = value[:32000]

        # return
        return value

    @staticmethod
    def xml_to_kvp(xml_input, handler=None, return_handler=False, **kwargs):
        '''
        Static method to create key/value pairs (kvp) from XML string input

        Args:

        Returns:

        '''

        # init handler, overwriting defaults if not None
        if not handler:
            handler = XML2kvp(**kwargs)

        # clean kvp_dict
        handler.kvp_dict = OrderedDict()

        # parse xml input
        handler.xml_string = handler._parse_xml_input(xml_input)

        # parse as dictionary
        handler.xml_dict = xmltodict.parse(
            handler.xml_string, xml_attribs=True)

        # walk xmltodict parsed dictionary
        handler._xml_dict_parser(None, handler.xml_dict, hops=[])

        # handle literal mixins
        if len(handler.add_literals) > 0:
            for k, v in handler.add_literals.items():
                handler.kvp_dict[k] = v

        # handle split and concatenations
        handler._split_and_concat_fields()

        # convert list to tuples if flagged
        if handler.as_tuples:
            # convert all lists to tuples
            for k, v in handler.kvp_dict.items():
                if type(v) == list:
                    handler.kvp_dict[k] = tuple(v)

        # include metadata about delimeters
        if handler.include_meta:

            # set delimiters
            meta_dict = {
                'node_delim': handler.node_delim,
                'ns_prefix_delim': handler.ns_prefix_delim
            }

            # if nsmap exists, include
            if handler.nsmap:
                meta_dict['nsmap'] = handler.nsmap

            # set as json
            handler.kvp_dict['xml2kvp_meta'] = json.dumps(meta_dict)

        # return
        if return_handler:
            return handler
        return handler.kvp_dict

    @staticmethod
    def kvp_to_xml(kvp, handler=None, return_handler=False, serialize_xml=False, **kwargs):
        '''
        Method to generate XML from KVP

        Args:
                kvp (dict): Dictionary of key value pairs
                handler (XML2kvp): Instance of XML2kvp client
                return_handler (boolean): Return XML if False, handler if True
        '''

        # DEBUG
        # stime = time.time()

        # init handler, overwriting defaults if not None
        if not handler:
            handler = XML2kvp(**kwargs)

        # init XMLRecord
        xml_record = XMLRecord()
        if hasattr(handler, 'add_element_root'):
            root_node = handler.add_element_root
            if handler.ns_prefix_delim in root_node:
                prefix, tag_name = root_node.split(handler.ns_prefix_delim)
                tag_name = '{%s}%s' % (handler.nsmap[prefix], tag_name)
            else:
                tag_name = root_node
            xml_record.root_node = etree.Element(tag_name, nsmap=handler.nsmap)

        # loop through items
        for k, v in kvp.items():

            # split on delim
            nodes = k.split(handler.node_delim)

            # loop through nodes and create XML element nodes
            hops = []
            for i, node in enumerate(nodes):

                # write hops
                if not node.startswith('@'):

                    # init attributes
                    attribs = {}

                    # handle namespaces for tag name
                    if handler.ns_prefix_delim in node:

                        # get prefix and tag name
                        prefix, tag_name = node.split(handler.ns_prefix_delim)

                        # write
                        tag_name = '{%s}%s' % (handler.nsmap[prefix], tag_name)

                    # else, handle non-namespaced
                    else:
                        tag_name = node

                    # handle sibling hashes
                    if handler.include_sibling_id:

                        # run tag_name through sibling_hash_regex
                        matches = re.match(sibling_hash_regex, tag_name)
                        if matches != None:
                            groups = matches.groups()

                            # if tag_name and sibling hash, append to attribs
                            if groups[0] and groups[1]:
                                tag_name = groups[0]
                                sibling_hash = groups[1]
                                attribs['sibling_hash_id'] = sibling_hash

                            # else, assume sibling hash not present, get tag name
                            elif groups[2]:
                                tag_name = groups[2]

                    # init element
                    node_ele = etree.Element(tag_name, nsmap=handler.nsmap)

                    # check for attributes
                    if i+1 < len(nodes) and nodes[i+1].startswith('@'):
                        while True:
                            for attrib in nodes[i+1:]:
                                if attrib.startswith('@'):
                                    attrib_name, attrib_value = attrib.split(
                                        '=')
                                    attribs[attrib_name.lstrip(
                                        '@')] = attrib_value
                                else:
                                    break
                            break

                    # write to element
                    node_ele.attrib.update(attribs)

                    # append to hops
                    hops.append(node_ele)

            # write values and number of nodes
            # # convert with ast.literal_eval to circumvent lists/tuples record as strings in pyspark
            # # https://github.com/MI-DPLA/combine/issues/361#issuecomment-442510950
            if type(v) == str:

                # evaluate to expose lists or tuples
                try:
                    v_eval = ast.literal_eval(v)
                    if type(v_eval) in [list, tuple]:
                        v = v_eval
                except:
                    pass

                # split based on handler.multivalue_delim
                if handler.multivalue_delim != None and type(v) == str and handler.multivalue_delim in v:
                    v = [val.strip()
                         for val in v.split(handler.multivalue_delim)]

            # handle single value
            if type(v) == str:

                # write value
                hops[-1].text = str(v)

                # append single list of nodes to xml_record
                xml_record.node_lists.append(hops)

            # handle multiple values
            elif type(v) in [list, tuple]:

                # loop through values
                for value in v:
                    # copy hops
                    hops_copy = deepcopy(hops)

                    # write value
                    hops_copy[-1].text = str(value)

                    # append single list of nodes to xml_record
                    xml_record.node_lists.append(hops_copy)

        # tether parent and child nodes
        xml_record.tether_node_lists()

        # merge all root nodes
        xml_record.merge_root_nodes()

        # if sibling hashes included, attempt to merge
        if handler.include_sibling_id:
            xml_record.merge_siblings()

        # return
        if serialize_xml:
            return xml_record.serialize()
        return xml_record

    @staticmethod
    def k_to_xpath(k, handler=None, return_handler=False, **kwargs):
        '''
        Method to derive xpath from kvp key
        '''

        # init handler
        if not handler:
            handler = XML2kvp(**kwargs)

        # for each column, reconstitue columnName --> XPath
        k_parts = k.split(handler.node_delim)

        # if skip root
        if handler.skip_root:
            k_parts = k_parts[1:]

        # if include_sibling_id, strip 6 char id from end
        if handler.include_sibling_id:
            k_parts = [
                part[:-8] if not part.startswith('@') else part for part in k_parts]

        # set initial on_attrib flag
        on_attrib = False

        # init path string
        if not handler.skip_root:
            xpath = ''
        else:
            xpath = '/'  # begin with single slash, will get appended to

        # determine if mixing of namespaced and non-namespaced elements
        ns_used = False
        for part in k_parts:
            if handler.ns_prefix_delim in part:
                ns_used = True

        # loop through pieces and build xpath
        for i, part in enumerate(k_parts):

            # if not attribute, assume node hop
            if not part.startswith('@'):

                # handle closing attrib if present
                if on_attrib:
                    xpath += ']/'
                    on_attrib = False

                # close previous element
                else:
                    xpath += '/'

                # handle parts without namespace, mingled among namespaced elements
                if ns_used and handler.ns_prefix_delim not in part:
                    part = '*[local-name() = "%s"]' % part
                else:
                    # replace delimiter with colon for prefix
                    part = part.replace(handler.ns_prefix_delim, ':')

                # if part not followed by attribute, append no attribute qualifier
                if ((i + 1) < len(k_parts) and not k_parts[(i + 1)].startswith('@')) or (
                        (i + 1) == len(k_parts) and not part.startswith('@')):
                    part += '[not(@*)]'

                # append to xpath
                xpath += part

            # if attribute, assume part of previous element and build
            else:

                # handle attribute
                attrib, value = part.split('=')

                # if not on_attrib, open xpath for attribute inclusion
                if not on_attrib:
                    xpath += "[%s='%s'" % (attrib, value)

                # else, currently in attribute write block, continue
                else:
                    xpath += " and %s='%s'" % (attrib, value)

                # set on_attrib flag for followup
                on_attrib = True

        # cleanup after loop
        if on_attrib:
            # close attrib brackets
            xpath += ']'

        # finally, avoid matching descandants
        xpath += '[not(*)]'

        # save to handler
        handler.k_xpath_dict[k] = xpath

        # return
        if return_handler:
            return handler
        return xpath

    @staticmethod
    def kvp_to_xpath(
            kvp,
            node_delim=None,
            ns_prefix_delim=None,
            skip_root=None,
            handler=None,
            return_handler=False):

        # init handler
        if not handler:
            handler = XML2kvp(
                node_delim=node_delim,
                ns_prefix_delim=ns_prefix_delim,
                skip_root=skip_root)

        # handle forms of kvp
        if type(kvp) == str:
            handler.kvp_dict = json.loads(kvp)
        if type(kvp) == dict:
            handler.kvp_dict = kvp

        # loop through and append to handler
        for k, _v in handler.kvp_dict.items():
            XML2kvp.k_to_xpath(k, handler=handler)

        # return
        if return_handler:
            return handler
        return handler.k_xpath_dict

    def test_kvp_to_xpath_roundtrip(self):

        # check for self.xml and self.nsmap
        if not hasattr(self, 'xml'):
            try:
                self.xml = etree.fromstring(self.xml_string)
            except:
                self.xml = etree.fromstring(self.xml_string.encode('utf-8'))
        if not hasattr(self, 'nsmap'):
            self._parse_nsmap()

        # generate xpaths values
        # TODO: why are we assigning to self here? does that even work?
        self = XML2kvp.kvp_to_xpath(
            self.kvp_dict, handler=self, return_handler=True)

        # check instances and report
        for k, v in self.k_xpath_dict.items():
            try:
                matched_elements = self.xml.xpath(v, namespaces=self.nsmap)
                values = self.kvp_dict[k]
                if type(values) == str:
                    values_len = 1
                elif type(values) in [tuple, list]:
                    values_len = len(values)
                if len(matched_elements) != values_len:
                    logger.debug('mismatch on %s --> %s, matched elements:values --> %s:%s',
                    k, v, values_len, len(matched_elements))
            except etree.XPathEvalError:
                logger.debug('problem with xpath statement: %s', v)
                logger.debug('could not calculate %s --> %s', k, v)

    @staticmethod
    def test_xml_to_kvp_speed(iterations, kwargs):

        stime = time.time()
        for _ in range(0, iterations):
            XML2kvp.xml_to_kvp(XML2kvp.test_xml, **kwargs)
        print("avg for %s iterations: %s" % (iterations, (time.time() - stime) / float(iterations)))

    def schema_as_table(self, table_format='rst'):
        '''
        Method to export schema as tabular table
                - converts list of lists into ASCII table

        Args:
                table_format (str) ['rst','md']
        '''

        # init table
        table = []

        # set headers
        table.append(['Parameter', 'Type', 'Description'])

        # loop through schema properties and add
        props = self.schema['properties']
        for k, v in props.items():
            table.append([
                "``%s``" % k,
                self._table_format_type(v['type']),
                self._table_format_desc(v['description'])
            ])

        # sort by property name
        table.sort(key=lambda x: x[0])

        # return as table based on table_format
        if table_format == 'rst':
            return dashtable.data2rst(table, use_headers=True)
        elif table_format == 'md':
            return dashtable.data2md(table)
        # else if table format is 'html' or anything else
        return None

    def _table_format_type(self, prop_type):
        '''
        Method to format XML2kvp configuration property type for table
        '''

        # handle single
        if type(prop_type) == str:
            return "``%s``" % prop_type
        # handle list
        elif type(prop_type) == list:
            return "[" + ",".join(["``%s``" % t for t in prop_type]) + "]"
        return ""

    def _table_format_desc(self, desc):
        '''
        Method to format XML2kvp configuration property description for table
        '''

        return desc

    @staticmethod
    def k_to_human(k, handler=None, return_handler=False, **kwargs):
        '''
        Method to humanize k's with sibling hashes and attributes
        '''

        # remove sibling hash
        if handler.include_sibling_id:
            k = re.sub(r'\(.+?\)', '', k)

        # rewrite namespace
            k = re.sub(r'\%s' % handler.ns_prefix_delim, ':', k)

        # return
        return k



class XMLRecord():
    '''
    Class to scaffold and create XML records from XML2kvp kvp
    '''

    def __init__(self):

        self.root_node = None
        self.node_lists = []
        self.nodes = []
        self.merge_metrics = {}

    def tether_node_lists(self):
        '''
        Method to tether nodes from node_lists as parent/child

        Returns:
                writes parent node to self.nodes
        '''

        for node_list in self.node_lists:

            # loop through nodes
            parent_node = None
            for i, node in enumerate(node_list):

                # append to parent
                if i > 0:
                    parent_node.append(node)

                # set as new parent and continue
                parent_node = node

            # add root node from each list to self.nodes
            self.nodes.append(node_list[0])

    def merge_root_nodes(self):
        '''
        Method to merge all nodes from self.nodes
        '''

        node_list = self.nodes
        # set root with arbitrary first node
        if self.root_node is None:
            self.root_node = self.nodes[0]
            node_list = self.nodes[1:]

        # loop through others, add children to root node
        for node in node_list:

            # get children
            children = node.getchildren()

            # loop through and add to root node
            for child in children:
                self.root_node.append(child)
            if len(children) == 0 and node.tag != self.root_node.tag:
                self.root_node.append(node)

    def merge_siblings(self, remove_empty_nodes=True, remove_sibling_hash_attrib=True):
        '''
        Method to merge all siblings if sibling_hash provided
        '''

        # init list of finished hashes
        finished_sibling_hashes = []

        # loop through root children
        for node_path in self.root_node.getchildren():

            # get all descendents (should be simple hierarchy)
            nodes = list(node_path.iterdescendants())

            # reverse, to deal with most granular first
            nodes.reverse()

            # loop through nodes
            for node in nodes:

                # check if sibling hash present as attribute, and not already completed
                if 'sibling_hash_id' in node.attrib and node.attrib.get(
                        'sibling_hash_id') not in finished_sibling_hashes:
                    # get hash
                    sibling_hash = node.attrib.get('sibling_hash_id')

                    # group siblings
                    self.merge_metrics[sibling_hash] = self._siblings_xpath_merge(sibling_hash,
                                                                                  remove_empty_nodes=remove_empty_nodes)

        # remove sibling_hash_id
        if remove_sibling_hash_attrib:
            all_siblings = self.root_node.xpath(
                '//*[@sibling_hash_id]', namespaces=self.root_node.nsmap)
            for sibling in all_siblings:
                sibling.attrib.pop('sibling_hash_id')

    def _siblings_xpath_merge(self, sibling_hash, remove_empty_nodes=True):
        '''
        Internal method to handle the actual movement of sibling nodes
                - performs XPath query
                - moves siblings to parent of 0th result

        Args:
                sibling_hash (str): Sibling has to perform Xpath query with
                remove_empty_nodes (bool): If True, remove nodes that no longer contain children

        Returns:

        '''

        # xpath query to find all siblings in tree
        siblings = self.root_node.xpath(
            '//*[@sibling_hash_id="%s"]' % sibling_hash, namespaces=self.root_node.nsmap)

        # metrics
        removed = 0
        moved = 0

        # if results
        if len(siblings) > 0:

            # establish arbitrary target parent node as 0th parent
            target_parent = siblings[0].getparent()

            # loop through remainders and move there
            for sibling in siblings[1:]:

                # get parent
                parent = sibling.getparent()

                # move to target parent
                target_parent.append(sibling)

                # if flagged, remove parent if now empty
                if remove_empty_nodes:
                    if len(parent.getchildren()) == 0:
                        parent.getparent().remove(parent)
                        removed += 1

                # bump counter
                moved += 1

        # return metrics
        metrics = {'sibling_hash': sibling_hash,
                   'removed': removed, 'moved': moved}
        return metrics

    def serialize(self, pretty_print=True):
        '''
        Method to serialize self.root_node to XML
        '''

        return etree.tostring(self.root_node, pretty_print=pretty_print, xml_declaration=True, encoding="UTF-8").decode('utf-8')
