import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from core.models import Transformation, OAIEndpoint, ValidationScenario, FieldMapper,\
    RecordIdentifierTransformation, DPLABulkDataDownload, DPLABulkDataClient
from core.mongo import settings

from .view_helpers import breadcrumb_parser

LOGGER = logging.getLogger(__name__)


@login_required
def configuration(request):
    # get all transformations
    transformations = Transformation.objects.all()

    # get all OAI endpoints
    oai_endpoints = OAIEndpoint.objects.all()

    # get all validation scenarios
    validation_scenarios = ValidationScenario.objects.all()

    # get record identifier transformation scenarios
    rits = RecordIdentifierTransformation.objects.all()

    # get all bulk downloads
    bulk_downloads = DPLABulkDataDownload.objects.all()

    # get field mappers
    field_mappers = FieldMapper.objects.all()

    # return
    return render(request, 'core/configuration.html', {
        'transformations': transformations,
        'oai_endpoints': oai_endpoints,
        'validation_scenarios': validation_scenarios,
        'rits': rits,
        'field_mappers': field_mappers,
        'bulk_downloads': bulk_downloads,
        'breadcrumbs': breadcrumb_parser(request)
    })


@login_required
def dpla_bulk_data_download(request):
    """
    View to support the downloading of DPLA bulk data
    """

    if request.method == 'GET':

        # if S3 credentials set
        if settings.AWS_ACCESS_KEY_ID and \
                settings.AWS_SECRET_ACCESS_KEY and \
                settings.AWS_ACCESS_KEY_ID is not None and \
                settings.AWS_SECRET_ACCESS_KEY is not None:

            # get DPLABulkDataClient and keys from DPLA bulk download
            dbdc = DPLABulkDataClient()
            bulk_data_keys = dbdc.retrieve_keys()

        else:
            bulk_data_keys = False

        # return
        return render(request, 'core/dpla_bulk_data_download.html', {
            'bulk_data_keys': bulk_data_keys,
            'breadcrumbs': breadcrumb_parser(request)
        })

    if request.method == 'POST':
        # OLD ######################################################################
        LOGGER.debug('initiating bulk data download')

        # get DPLABulkDataClient
        dbdc = DPLABulkDataClient()

        # initiate download
        dbdc.download_and_index_bulk_data(request.POST.get('object_key', None))

        # return to configuration screen
        return redirect('configuration')
