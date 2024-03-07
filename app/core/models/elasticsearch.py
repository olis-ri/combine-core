# -*- coding: utf-8 -*-
from __future__ import unicode_literals

# generic imports
import json
import logging
import time

# django imports
from django.conf import settings

# import elasticsearch and handles
from core.es import es_handle
from elasticsearch_dsl import Search, A, Q

# Get an instance of a LOGGER
LOGGER = logging.getLogger(__name__)

# Set logging levels for 3rd party modules
logging.getLogger("requests").setLevel(logging.WARNING)



class ESIndex():

    '''
    Model to aggregate methods useful for accessing and analyzing ElasticSearch indices
    '''

    def __init__(self, es_index):

        # convert single index to list
        if isinstance(es_index, str):
            self.es_index = [es_index]
        else:
            self.es_index = es_index

        # also, save as string
        self.es_index_str = str(self.es_index)


    def get_index_fields(self):

        '''
        Get list of all fields for index

        Args:
            None

        Returns:
            (list): list of field names
        '''

        if es_handle.indices.exists(index=self.es_index) and es_handle.search(index=self.es_index)['hits']['total']['value'] > 0:

            # get mappings for job index
            es_r = es_handle.indices.get(index=self.es_index)

            # loop through indices and build field names
            field_names = []
            for _, index_properties in es_r.items():
                LOGGER.debug(index_properties['mappings']['properties'])
                fields = index_properties['mappings']['properties']
                # get fields as list and extend list
                field_names.extend(list(fields.keys()))
            # get unique list
            field_names = list(set(field_names))

            # remove uninteresting fields
            field_names = [field for field in field_names if field not in [
                'db_id',
                'combine_id',
                'xml2kvp_meta',
                'fingerprint']]

            # sort alphabetically that influences results list
            field_names.sort()

            return field_names


    @staticmethod
    def _calc_field_metrics(
            sr_dict,
            field_name,
            one_per_doc_offset=settings.ONE_PER_DOC_OFFSET
        ):

        '''
        Calculate metrics for a given field.

        Args:
            sr_dict (dict): ElasticSearch search results dictionary
            field_name (str): Field name to analyze metrics for
            one_per_doc_offset (float): Offset from 1.0 that is used to guess if field is unique for all documents

        Returns:
            (dict): Dictionary of metrics for given field
        '''

        if sr_dict['aggregations']['%s_doc_instances' % field_name]['doc_count'] > 0:

            # add that don't require calculation
            field_dict = {
                'field_name':field_name,
                'doc_instances':sr_dict['aggregations']['%s_doc_instances' % field_name]['doc_count'],
                'val_instances':sr_dict['aggregations']['%s_val_instances' % field_name]['value'],
                'distinct':sr_dict['aggregations']['%s_distinct' % field_name]['value']
            }

            # documents without
            field_dict['doc_missing'] = sr_dict['hits']['total']['value'] - field_dict['doc_instances']

            # distinct ratio
            if field_dict['val_instances'] > 0:
                field_dict['distinct_ratio'] = round((field_dict['distinct'] / field_dict['val_instances']), 4)
            else:
                field_dict['distinct_ratio'] = 0.0

            # percentage of total documents with instance of this field
            field_dict['percentage_of_total_records'] = round(
                (field_dict['doc_instances'] / sr_dict['hits']['total']['value']), 4)

            # one, distinct value for this field, for this document
            if field_dict['distinct_ratio'] > (1.0 - one_per_doc_offset) \
             and field_dict['distinct_ratio'] < (1.0 + one_per_doc_offset) \
             and len(set([field_dict['doc_instances'], field_dict['val_instances'], sr_dict['hits']['total']['value']])) == 1:
                field_dict['one_distinct_per_doc'] = True
            else:
                field_dict['one_distinct_per_doc'] = False

            # return
            return field_dict

        # if no instances of field in results, return False
        return False


    def count_indexed_fields(
            self,
            cardinality_precision_threshold=settings.CARDINALITY_PRECISION_THRESHOLD,
            job_record_count=None
        ):

        '''
        Calculate metrics of fields across all document in a job's index:
            - *_doc_instances = how many documents the field exists for
            - *_val_instances = count of total values for that field, across all documents
            - *_distinct = count of distinct values for that field, across all documents

        Note: distinct counts rely on cardinality aggregations from ElasticSearch, but these are not 100 percent
        accurate according to ES documentation:
        https://www.elastic.co/guide/en/elasticsearch/guide/current/_approximate_aggregations.html

        Args:
            cardinality_precision_threshold (int, 0:40-000): Cardinality precision threshold (see note above)
            job_record_count (int): optional pre-count of records

        Returns:
            (dict):
                total_docs: count of total docs
                field_counts (dict): dictionary of fields with counts, uniqueness across index, etc.
        '''

        if self.es_index != [] and es_handle.indices.exists(index=self.es_index) and es_handle.search(index=self.es_index)['hits']['total']['value'] > 0:

            # DEBUG
            stime = time.time()

            # get field mappings for index
            field_names = self.get_index_fields()

            # loop through fields and query ES
            field_count = []
            for field_name in field_names:

                LOGGER.debug('analyzing mapped field %s', field_name)

                # init search
                search = Search(using=es_handle, index=self.es_index)

                # return no results, only aggs
                search = search[0]

                # add agg buckets for each field to count total and unique instances
                # for field_name in field_names:
                search.aggs.bucket('%s_doc_instances' % field_name, A('filter', Q('exists', field=field_name)))
                search.aggs.bucket('%s_val_instances' % field_name, A('value_count', field='%s.keyword' % field_name))
                search.aggs.bucket(
                    '%s_distinct' % field_name,
                    A(
                        'cardinality',
                        field='%s.keyword' % field_name,
                        precision_threshold=cardinality_precision_threshold
                    ))

                # execute search and capture as dictionary
                search_result = search.execute()
                sr_dict = search_result.to_dict()

                # get metrics and append if field metrics found
                field_metrics = self._calc_field_metrics(sr_dict, field_name)
                if field_metrics:
                    field_count.append(field_metrics)

            # DEBUG
            LOGGER.debug('count indexed fields elapsed: %s', (time.time()-stime))

            # prepare dictionary for return
            return_dict = {
                'total_docs':sr_dict['hits']['total']['value'],
                'fields':field_count
            }

            # if job record count provided, include percentage of indexed records to that count
            if job_record_count:
                indexed_percentage = round((float(return_dict['total_docs']) / float(job_record_count)), 4)
                return_dict['indexed_percentage'] = indexed_percentage

            # return
            return return_dict

        return False


    def field_analysis(
            self,
            field_name,
            cardinality_precision_threshold=settings.CARDINALITY_PRECISION_THRESHOLD,
            metrics_only=False,
            terms_limit=10000
        ):

        '''
        For a given field, return all values for that field across a job's index

        Note: distinct counts rely on cardinality aggregations from ElasticSearch, but these are not 100 percent
        accurate according to ES documentation:
        https://www.elastic.co/guide/en/elasticsearch/guide/current/_approximate_aggregations.html

        Args:
            field_name (str): field name
            cardinality_precision_threshold (int, 0:40,000): Cardinality precision threshold (see note above)
            metrics_only (bool): If True, return only field metrics and not values

        Returns:
            (dict): dictionary of values for a field
        '''

        # init search
        search = Search(using=es_handle, index=self.es_index)

        # add aggs buckets for field metrics
        search.aggs.bucket('%s_doc_instances' % field_name, A('filter', Q('exists', field=field_name)))
        search.aggs.bucket('%s_val_instances' % field_name, A('value_count', field='%s.keyword' % field_name))
        search.aggs.bucket(
            '%s_distinct' % field_name,
            A(
                'cardinality',
                field='%s.keyword' % field_name,
                precision_threshold=cardinality_precision_threshold
            ))

        # add agg bucket for field values
        if not metrics_only:
            search.aggs.bucket(field_name, A('terms', field='%s.keyword' % field_name, size=terms_limit))

        # return zero
        search = search[0]

        # execute and return aggs
        search_result = search.execute()

        # get metrics
        field_metrics = self._calc_field_metrics(search_result.to_dict(), field_name)

        # prepare and return
        if not metrics_only:
            values = search_result.aggs[field_name]['buckets']
        else:
            values = None

        return {
            'metrics':field_metrics,
            'values':values
        }


    def query(self, query_body):

        '''
        Method to run query against Job's ES index
        '''

        # init query
        query = Search(using=es_handle, index=self.es_index)

        # update with query_body
        if isinstance(query_body, dict):
            query = query.update_from_dict(query_body)
        elif isinstance(query_body, str):
            query = query.update_from_dict(json.loads(query_body))

        # execute and return
        results = query.execute()
        return results
